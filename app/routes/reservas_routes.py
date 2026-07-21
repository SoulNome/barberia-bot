import re
import time
from collections import deque
from datetime import datetime, timedelta

from flask import Blueprint, request, jsonify, render_template

from app.models.barberia import Barberia
from app.models.barbero import Barbero
from app.services.barbero_service import obtener_barberos
from app.services.disponibilidad_service import obtener_horarios_disponibles, FESTIVOS
from app.services.agenda_service import crear_cita

reservas_bp = Blueprint("reservas", __name__)

# Ventana de reserva pública: hoy + N días
DIAS_ADELANTE = 14

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

    if not barbero_id or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", fecha):
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
    return jsonify({"slots": [s["hora"] for s in slots if s["disponible"]]})


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

    # El slot debe existir dentro del horario de atención y estar libre
    # (crear_cita valida colisiones, pero no que la hora sea de atención)
    slots = obtener_horarios_disponibles(barbero_id, fecha, barberia.id)
    if not isinstance(slots, list) or not any(s["hora"] == hora and s["disponible"] for s in slots):
        return jsonify({"ok": False, "mensaje": "Ese horario ya no está disponible. Elige otro."})

    ok, msg = crear_cita(
        nombre, telefono, barbero_id, fecha, hora, servicio,
        barberia_id=barberia.id,
    )
    return jsonify({"ok": ok, "mensaje": msg})
