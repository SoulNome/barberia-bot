import re
import time
from collections import deque
from datetime import datetime, timedelta

from flask import Blueprint, request, jsonify, render_template, redirect

from app.models.barberia import Barberia
from app.models.barbero import Barbero
from app.services.barbero_service import obtener_barberos
from app.services.disponibilidad_service import obtener_horarios_disponibles, FESTIVOS
from app.services.agenda_service import crear_cita

reservas_bp = Blueprint("reservas", __name__)

# Ventana de reserva pública: hoy + N días
DIAS_ADELANTE = 15

# Turnos consecutivos máximos por reserva (misma lógica de grupos del bot)
MAX_PERSONAS = 7

# Rate limit en memoria: máx 5 intentos de reserva por IP por hora.
# Válido porque gunicorn corre con 1 solo worker (ver Procfile).
_RATE_MAX     = 5
_RATE_VENTANA = 3600
_rate_buckets = {}

_DIAS_ES  = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
_MESES_ES = ["ene", "feb", "mar", "abr", "may", "jun",
             "jul", "ago", "sep", "oct", "nov", "dic"]


def _colombia_hoy():
    return (datetime.utcnow() - timedelta(hours=5)).date()


def _rate_ok(ip):
    ahora = time.time()
    q = _rate_buckets.setdefault(ip, deque())
    while q and ahora - q[0] > _RATE_VENTANA:
        q.popleft()
    if len(q) >= _RATE_MAX:
        return False
    q.append(ahora)
    return True


def _normalizar_telefono(tel):
    """Normaliza al formato +57XXXXXXXXXX que usa el resto del sistema
    (el bot guardaba los clientes como '+' + JID)."""
    tel = re.sub(r"[^\d+]", "", tel or "")
    if tel.startswith("+"):
        digitos = tel[1:]
    else:
        digitos = tel
    if not digitos.isdigit():
        return None
    if len(digitos) == 10 and digitos.startswith("3"):      # celular colombiano
        return "+57" + digitos
    if len(digitos) == 12 and digitos.startswith("57"):
        return "+" + digitos
    if 10 <= len(digitos) <= 15:                            # internacional genérico
        return "+" + digitos
    return None


def _horas_consecutivas(hora_inicio, cantidad):
    """['10:00', '10:30', ...]: la hora elegida + los turnos siguientes,
    en bloques de 30 min (igual que los grupos del bot de chat)."""
    base = datetime.strptime(hora_inicio, "%H:%M")
    return [(base + timedelta(minutes=30 * k)).strftime("%H:%M") for k in range(cantidad)]


def _inicios_validos(slots, cantidad):
    """Horas de inicio cuyos `cantidad` turnos consecutivos están todos libres.
    Réplica del filtro de conversation_service para citas grupales."""
    libres = {s["hora"] for s in slots if s["disponible"]}
    inicios = []
    for s in slots:
        if not s["disponible"]:
            continue
        if all(h in libres for h in _horas_consecutivas(s["hora"], cantidad)):
            inicios.append(s["hora"])
    return inicios


def _dias_abiertos(barberia):
    """Próximos DIAS_ADELANTE días en los que la barbería atiende."""
    horarios   = barberia.get_horarios()
    bloqueados = barberia.get_dias_bloqueados()
    hoy        = _colombia_hoy()
    dias = []
    for i in range(DIAS_ADELANTE):
        f    = hoy + timedelta(days=i)
        fstr = f.strftime("%Y-%m-%d")
        if f.weekday() not in horarios:
            continue
        if fstr in FESTIVOS or fstr in bloqueados:
            continue
        dias.append({
            "fecha":  fstr,
            "dia":    "Hoy" if i == 0 else ("Mañana" if i == 1 else _DIAS_ES[f.weekday()]),
            "num":    f.day,
            "mes":    _MESES_ES[f.month - 1],
        })
    return dias


@reservas_bp.route("/reservar")
def pagina_reserva_default():
    """URL corta para la barbería principal (cliente legacy, igual que /bot
    sin slug). Redirige a /reservar/<slug>; la migración de startup garantiza
    que la primera barbería siempre tenga slug."""
    barberia = Barberia.query.order_by(Barberia.id).first()
    if not barberia or not barberia.slug:
        return "Barbería no encontrada", 404
    return redirect(f"/reservar/{barberia.slug}")


@reservas_bp.route("/reservar/<slug>")
def pagina_reserva(slug):
    barberia = Barberia.query.filter_by(slug=slug).first()
    if not barberia:
        return "Barbería no encontrada", 404

    return render_template(
        "reservar.html",
        barberia  = barberia,
        barberos  = obtener_barberos(barberia.id),
        servicios = barberia.get_servicios(),
        dias      = _dias_abiertos(barberia),
    )


@reservas_bp.route("/reservar/<slug>/horarios")
def horarios_reserva(slug):
    barberia = Barberia.query.filter_by(slug=slug).first()
    if not barberia:
        return jsonify({"error": "not_found"}), 404

    barbero_id = request.args.get("barbero_id", type=int)
    fecha      = (request.args.get("fecha") or "").strip()
    cantidad   = request.args.get("cantidad", default=1, type=int)

    if not barbero_id or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", fecha):
        return jsonify({"slots": []})
    if not (1 <= cantidad <= MAX_PERSONAS):
        return jsonify({"slots": []})

    # El barbero debe pertenecer a esta barbería (aislamiento multi-tenant)
    barbero = Barbero.query.get(barbero_id)
    if not barbero or barbero.barberia_id != barberia.id:
        return jsonify({"slots": []})

    try:
        f = datetime.strptime(fecha, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"slots": []})
    hoy = _colombia_hoy()
    if f < hoy or f > hoy + timedelta(days=DIAS_ADELANTE):
        return jsonify({"slots": []})

    slots = obtener_horarios_disponibles(barbero_id, fecha, barberia.id)
    if not isinstance(slots, list):
        return jsonify({"slots": []})
    return jsonify({"slots": _inicios_validos(slots, cantidad)})


@reservas_bp.route("/reservar/<slug>/crear", methods=["POST"])
def crear_reserva(slug):
    barberia = Barberia.query.filter_by(slug=slug).first()
    if not barberia:
        return jsonify({"ok": False, "mensaje": "Barbería no encontrada."}), 404

    ip = request.headers.get("X-Forwarded-For", request.remote_addr or "?").split(",")[0].strip()
    if not _rate_ok(ip):
        return jsonify({"ok": False, "mensaje": "Demasiados intentos. Espera un momento e intenta de nuevo."}), 429

    data = request.get_json(silent=True) or {}

    # Honeypot: campo oculto que solo llenan los bots — responder como éxito
    if data.get("_web"):
        return jsonify({"ok": True, "mensaje": "✅ Cita creada correctamente."})

    nombre   = (data.get("nombre") or "").strip()[:60]
    telefono = _normalizar_telefono(data.get("telefono"))
    fecha    = (data.get("fecha") or "").strip()
    hora     = (data.get("hora") or "").strip()
    servicio = (data.get("servicio") or "").strip()

    if len(nombre) < 2:
        return jsonify({"ok": False, "mensaje": "Escribe tu nombre."})
    if not telefono:
        return jsonify({"ok": False, "mensaje": "El número de celular no es válido."})
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", fecha) or not re.fullmatch(r"\d{2}:\d{2}", hora):
        return jsonify({"ok": False, "mensaje": "Fecha u hora inválida."})

    barbero_id = data.get("barbero_id")
    try:
        barbero_id = int(barbero_id)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "mensaje": "Elige un barbero."})
    barbero = Barbero.query.get(barbero_id)
    if not barbero or barbero.barberia_id != barberia.id:
        return jsonify({"ok": False, "mensaje": "Elige un barbero."})

    if servicio not in {s["nombre"] for s in barberia.get_servicios()}:
        return jsonify({"ok": False, "mensaje": "Elige un servicio."})

    try:
        cantidad = int(data.get("cantidad", 1))
    except (TypeError, ValueError):
        cantidad = 1
    if not (1 <= cantidad <= MAX_PERSONAS):
        return jsonify({"ok": False, "mensaje": f"Máximo {MAX_PERSONAS} personas por reserva."})

    # Todos los turnos del grupo deben caer dentro del horario de atención y
    # estar libres (crear_cita valida colisiones, pero no horario de atención)
    slots = obtener_horarios_disponibles(barbero_id, fecha, barberia.id)
    if not isinstance(slots, list) or hora not in _inicios_validos(slots, cantidad):
        return jsonify({"ok": False, "mensaje": "Ese horario ya no está disponible. Elige otro."})

    horas = _horas_consecutivas(hora, cantidad)

    ok, msg = crear_cita(
        nombre, telefono, barbero_id, fecha, hora, servicio,
        barberia_id=barberia.id,
    )
    if not ok:
        return jsonify({"ok": False, "mensaje": msg})

    # Turnos extra del grupo: mismo cliente, servicio "X (persona k)" — formato
    # idéntico al del bot de chat, que el panel ya conoce.
    creadas = [hora]
    for k in range(2, cantidad + 1):
        ok_k, _ = crear_cita(
            nombre, telefono, barbero_id, fecha, horas[k - 1],
            f"{servicio} (persona {k})",
            skip_client_check=True, barberia_id=barberia.id,
        )
        if not ok_k:
            _deshacer_reserva(telefono, barbero_id, fecha, creadas, barberia.id)
            return jsonify({"ok": False, "mensaje": "Alguien tomó uno de los turnos justo ahora. Elige otra hora."})
        creadas.append(horas[k - 1])

    return jsonify({"ok": True, "mensaje": msg, "turnos": horas})


def _deshacer_reserva(telefono, barbero_id, fecha, horas, barberia_id):
    """Elimina las citas ya creadas de un grupo que no se pudo completar,
    para no dejar reservas a medias."""
    from datetime import time as time_t

    from app.extensions import db
    from app.models import Cita
    from app.services.agenda_service import _buscar_cliente

    try:
        cliente = _buscar_cliente(telefono, barberia_id)
        if not cliente:
            return
        horas_t = [time_t(*map(int, h.split(":"))) for h in horas]
        Cita.query.filter(
            Cita.cliente_id == cliente.id,
            Cita.barbero_id == barbero_id,
            Cita.fecha == datetime.strptime(fecha, "%Y-%m-%d").date(),
            Cita.hora.in_(horas_t),
        ).delete(synchronize_session=False)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"⚠ Error deshaciendo reserva grupal: {e}")
