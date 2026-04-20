import json
import re
import time as time_module
from flask import Blueprint, request, render_template, Response, stream_with_context, jsonify, session, redirect, url_for
from app.models import Cita, Cliente, Barbero
from app.models.barberia import Barberia
from app.extensions import db
from datetime import date, datetime, time, timedelta
import os

panel_bp = Blueprint("panel", __name__)

# Fallback global para compatibilidad con el cliente activo (1 sola barbería)
_PANEL_KEY_ENV = os.getenv("PANEL_KEY")


# ──────────────────────────────────────────────────────────────────────────────
# HELPER: obtener barbería desde la key del panel
# ──────────────────────────────────────────────────────────────────────────────

def _get_barberia(key):
    """
    Devuelve el objeto Barberia correspondiente a la key.
    1) Busca en la tabla barberias por panel_key.
    2) Fallback: si la key coincide con PANEL_KEY env-var, devuelve la primera barbería.
    """
    if not key:
        return None
    b = Barberia.query.filter_by(panel_key=key).first()
    if b:
        return b
    if _PANEL_KEY_ENV and key == _PANEL_KEY_ENV:
        return Barberia.query.order_by(Barberia.id).first()
    return None


def _check_auth(key=None):
    """
    Devuelve Barberia si el usuario está autenticado (sesión o key).
    Prioridad: sesión → key en URL/body.
    Si valida por key, guarda en sesión para futuras peticiones.
    """
    barberia_id = session.get("panel_barberia_id")
    if barberia_id:
        b = Barberia.query.get(barberia_id)
        if b:
            return b
        session.pop("panel_barberia_id", None)
        session.pop("panel_key", None)

    if key:
        b = _get_barberia(key)
        if b:
            session["panel_barberia_id"] = b.id
            session["panel_key"] = b.panel_key or ""
            return b

    return None


def _get_barberia_api():
    """Para endpoints de API: verifica sesión, luego key en args o body JSON."""
    key = request.args.get("key") or (request.get_json(silent=True) or {}).get("key")
    return _check_auth(key)


def _colombia_today():
    return (datetime.utcnow() - timedelta(hours=5)).date()


from app.models.barberia import DEFAULT_HORARIOS as _DEFAULT_HORARIOS

_DIAS_NUM_PANEL = {
    "lunes": 0, "martes": 1, "miércoles": 2, "miercoles": 2,
    "jueves": 3, "viernes": 4, "sábado": 5, "sabado": 5
}


def _parsear_horario_fijo_panel(horario_str, dia_semana):
    if not horario_str:
        return None
    texto = horario_str.lower()
    partes = re.split(r'\s+y\s+', texto)
    for parte in partes:
        dia_encontrado = None
        for nombre, num in _DIAS_NUM_PANEL.items():
            if nombre in parte:
                dia_encontrado = num
                break
        if dia_encontrado != dia_semana:
            continue
        m = re.search(r'(\d{1,2}):(\d{2})\s*(am|pm)?', parte)
        if not m:
            continue
        h, mins, ampm = int(m.group(1)), int(m.group(2)), m.group(3)
        if ampm == "pm" and h != 12:
            h += 12
        elif ampm == "am" and h == 12:
            h = 0
        elif ampm is None and 1 <= h <= 8:
            h += 12
        return f"{h:02d}:{mins:02d}"
    return None


def obtener_horarios_dia(dia_semana, barberia=None):
    """Devuelve los bloques horarios del día para la barbería (o los defaults)."""
    config = barberia.get_horarios() if barberia else _DEFAULT_HORARIOS
    bloques_str = config.get(dia_semana, [])
    result = []
    for inicio_str, fin_str in bloques_str:
        h_i, m_i = map(int, inicio_str.split(":"))
        h_f, m_f = map(int, fin_str.split(":"))
        result.append((time(h_i, m_i), time(h_f, m_f)))
    return result


# ──────────────────────────────────────────────────────────────────────────────
# BUILD PANEL DATA
# ──────────────────────────────────────────────────────────────────────────────

def _build_panel_data(barberia_id, fecha=None):
    hoy = fecha or _colombia_today()

    # Cargar objeto barbería para acceder a su config (precios, horarios)
    barberia_obj = Barberia.query.get(barberia_id) if barberia_id else None
    precios      = barberia_obj.get_precios() if barberia_obj else {}

    q_citas = Cita.query.filter(Cita.fecha == hoy, Cita.estado != "cancelada")
    if barberia_id:
        q_citas = q_citas.filter(Cita.barberia_id == barberia_id)
    citas = q_citas.all()

    citas_hoy      = len(citas)
    clientes_count = Cliente.query.filter_by(barberia_id=barberia_id).count() if barberia_id else Cliente.query.count()
    barberos_count = Barbero.query.filter_by(barberia_id=barberia_id).count() if barberia_id else Barbero.query.count()

    clientes_dict = {c.id: c for c in Cliente.query.all()}
    barberos_dict = {b.id: b.nombre for b in Barbero.query.all()}

    ingresos_hoy = sum(precios.get(c.servicio, 0) for c in citas)
    conteo = {}
    for cita in citas:
        if cita.servicio:
            conteo[cita.servicio] = conteo.get(cita.servicio, 0) + 1
    servicio_top = max(conteo, key=conteo.get) if conteo else None

    # Slots virtuales de clientes fijos para este día
    dia_semana = hoy.weekday()
    fijo_slots = {}  # time -> nombre cliente
    clientes_fijos_lista = []

    q_fijos = Cliente.query.filter_by(fijo=True)
    if barberia_id:
        q_fijos = q_fijos.filter_by(barberia_id=barberia_id)

    for cf in q_fijos.all():
        clientes_fijos_lista.append({
            "nombre": cf.nombre,
            "telefono": cf.telefono,
            "horario_fijo": cf.horario_fijo or ""
        })
        hora_fija_str = _parsear_horario_fijo_panel(cf.horario_fijo, dia_semana)
        if hora_fija_str:
            try:
                h, m_val = [int(x) for x in hora_fija_str.split(":")]
                t = time(h, m_val)
                fijo_slots[t] = cf.nombre
            except Exception:
                pass

    # Excluir de fijo_slots a los clientes fijos que cancelaron hoy
    q_canceladas = Cita.query.filter(Cita.fecha == hoy, Cita.estado == "cancelada")
    if barberia_id:
        q_canceladas = q_canceladas.filter(Cita.barberia_id == barberia_id)
    citas_canceladas_hoy = q_canceladas.all()

    for cc in citas_canceladas_hoy:
        cli_c = clientes_dict.get(cc.cliente_id)
        if cli_c and cli_c.fijo and cc.hora in fijo_slots:
            del fijo_slots[cc.hora]

    agenda = []
    bloques = obtener_horarios_dia(dia_semana, barberia_obj)
    total_slots = 0

    for inicio, fin in bloques:
        actual = datetime.combine(hoy, inicio)
        while actual.time() < fin:
            total_slots += 1
            hora = actual.time()
            cita = next((c for c in citas if c.hora == hora), None)
            if cita:
                cli_obj    = clientes_dict.get(cita.cliente_id)
                nombre_cli = cli_obj.nombre if cli_obj else None
                es_fijo    = bool(cli_obj and cli_obj.fijo)
                agenda.append({
                    "hora":      hora.strftime("%H:%M"),
                    "cita_id":   cita.id,
                    "cliente":   nombre_cli,
                    "barbero":   barberos_dict.get(cita.barbero_id),
                    "servicio":  cita.servicio,
                    "cumpleanos": bool(cita.servicio and "🎂" in cita.servicio),
                    "fijo":      es_fijo
                })
            elif hora in fijo_slots:
                agenda.append({
                    "hora":      hora.strftime("%H:%M"),
                    "cita_id":   None,
                    "cliente":   fijo_slots[hora],
                    "barbero":   None,
                    "servicio":  "📌 Turno fijo",
                    "cumpleanos": False,
                    "fijo":      True
                })
            else:
                agenda.append({
                    "hora":      hora.strftime("%H:%M"),
                    "cita_id":   None,
                    "cliente":   None,
                    "barbero":   None,
                    "servicio":  None,
                    "cumpleanos": False,
                    "fijo":      False
                })
            actual += timedelta(minutes=30)

    # Citas fuera del horario estándar
    horas_en_agenda = {row["hora"] for row in agenda}
    for cita in citas:
        hora_str = cita.hora.strftime("%H:%M")
        if hora_str not in horas_en_agenda:
            cli_obj    = clientes_dict.get(cita.cliente_id)
            nombre_cli = cli_obj.nombre if cli_obj else None
            es_fijo    = bool(cli_obj and cli_obj.fijo)
            agenda.append({
                "hora":      hora_str,
                "cita_id":   cita.id,
                "cliente":   nombre_cli,
                "barbero":   barberos_dict.get(cita.barbero_id),
                "servicio":  cita.servicio,
                "cumpleanos": bool(cita.servicio and "🎂" in cita.servicio),
                "fijo":      es_fijo
            })
            horas_en_agenda.add(hora_str)

    # Fijos fuera del rango normal
    for t_fijo, nombre_fijo in sorted(fijo_slots.items()):
        hora_str = t_fijo.strftime("%H:%M")
        if hora_str not in horas_en_agenda:
            agenda.append({
                "hora":      hora_str,
                "cita_id":   None,
                "cliente":   nombre_fijo,
                "barbero":   None,
                "servicio":  "📌 Turno fijo (excepcional)",
                "cumpleanos": False,
                "fijo":      True
            })

    agenda.sort(key=lambda r: r["hora"])

    ocupacion   = int((citas_hoy / total_slots) * 100) if total_slots > 0 else 0
    q_barberos  = Barbero.query
    if barberia_id:
        q_barberos = q_barberos.filter_by(barberia_id=barberia_id)
    barberos_lista = [{"id": b.id, "nombre": b.nombre} for b in q_barberos.order_by(Barbero.nombre).all()]

    return {
        "citas_hoy":       citas_hoy,
        "clientes":        clientes_count,
        "barberos":        barberos_count,
        "barberos_lista":  barberos_lista,
        "ingresos_hoy":    ingresos_hoy,
        "servicio_top":    servicio_top,
        "ocupacion":       ocupacion,
        "agenda":          agenda,
        "clientes_fijos":  clientes_fijos_lista,
        "fecha_iso":       hoy.isoformat()
    }


# ──────────────────────────────────────────────────────────────────────────────
# RUTAS DEL PANEL
# ──────────────────────────────────────────────────────────────────────────────

@panel_bp.route("/panel/login", methods=["GET", "POST"])
def panel_login():
    # Si ya está autenticado, ir directo al panel
    if session.get("panel_barberia_id"):
        b = Barberia.query.get(session["panel_barberia_id"])
        if b:
            return redirect(url_for("panel.panel"))

    error = None
    if request.method == "POST":
        key = (request.form.get("key") or "").strip()
        b = _get_barberia(key)
        if b:
            session["panel_barberia_id"] = b.id
            session["panel_key"] = b.panel_key or ""
            return redirect(url_for("panel.panel"))
        error = "Clave incorrecta. Intenta de nuevo."

    return render_template("login.html", error=error)


@panel_bp.route("/panel/logout")
def panel_logout():
    session.pop("panel_barberia_id", None)
    session.pop("panel_key", None)
    return redirect(url_for("panel.panel_login"))


@panel_bp.route("/panel")
def panel():
    # Soportar ?key= en URL para compatibilidad (sesión tiene prioridad)
    key = request.args.get("key")
    barberia = _check_auth(key)
    if not barberia:
        return redirect(url_for("panel.panel_login"))

    # Leer key desde sesión (para que el JS del template pueda hacer llamadas API)
    key = session.get("panel_key", "")

    fecha_str = request.args.get("fecha", "")
    try:
        fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date() if fecha_str else _colombia_today()
    except ValueError:
        fecha = _colombia_today()

    hoy      = _colombia_today()
    es_hoy   = fecha == hoy
    es_manana = fecha == hoy + timedelta(days=1)
    DIAS  = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
             "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    base_label = f"{DIAS[fecha.weekday()]} {fecha.day} de {MESES[fecha.month-1]}"
    if es_hoy:
        fecha_label = f"Hoy · {base_label}"
    elif es_manana:
        fecha_label = f"Mañana · {base_label}"
    else:
        fecha_label = f"{base_label} {fecha.year}"

    fecha_prev = (fecha - timedelta(days=1)).isoformat()
    fecha_next = (fecha + timedelta(days=1)).isoformat()
    data = _build_panel_data(barberia.id, fecha)
    return render_template("panel.html", **data,
                           key=key, es_hoy=es_hoy,
                           fecha_label=fecha_label,
                           fecha_prev=fecha_prev, fecha_next=fecha_next)


@panel_bp.route("/panel-stream")
def panel_stream():
    barberia = _get_barberia_api()
    if not barberia:
        return "No autorizado", 401

    from flask import current_app
    app         = current_app._get_current_object()
    barberia_id = barberia.id

    fecha_str = request.args.get("fecha", "")
    try:
        fecha_sse = datetime.strptime(fecha_str, "%Y-%m-%d").date() if fecha_str else None
    except ValueError:
        fecha_sse = None

    def generar():
        while True:
            try:
                with app.app_context():
                    payload = _build_panel_data(barberia_id, fecha_sse)
                yield f"event: update\ndata: {json.dumps(payload)}\n\n"
            except Exception as e:
                yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
            for _ in range(10):
                time_module.sleep(0.5)

    return Response(
        stream_with_context(generar()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )


@panel_bp.route("/run-import", methods=["POST"])
def run_import():
    barberia = _get_barberia_api()
    if not barberia:
        return jsonify({"success": False, "mensaje": "No autorizado"}), 401
    try:
        from scripts.importar_clientes import importar
        import sys
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from flask import current_app
        resultado = importar(app=current_app._get_current_object())
        return jsonify({"success": True, **resultado})
    except Exception as e:
        return jsonify({"success": False, "mensaje": str(e)})


@panel_bp.route("/crear-cliente", methods=["POST"])
def crear_cliente():
    barberia = _get_barberia_api()
    if not barberia:
        return jsonify({"success": False, "mensaje": "No autorizado"}), 401

    data     = request.get_json()
    telefono = (data.get("telefono") or "").strip()

    if not data.get("nombre") or not telefono:
        return jsonify({"success": False, "mensaje": "Nombre y teléfono son obligatorios"})

    if Cliente.query.filter_by(telefono=telefono, barberia_id=barberia.id).first():
        return jsonify({"success": False, "mensaje": "Ya existe un cliente con ese teléfono"})

    try:
        from datetime import datetime as dt
        fecha_cumple = None
        raw = (data.get("fecha_cumpleanos") or "").strip()
        if raw:
            fecha_cumple = dt.strptime(raw, "%Y-%m-%d").date()

        nombre = f"{data.get('nombre','').strip()} {data.get('apellido','').strip()}".strip()

        cliente = Cliente(
            nombre           = nombre,
            telefono         = telefono,
            fecha_cumpleanos = fecha_cumple,
            fijo             = bool(data.get("fijo", False)),
            horario_fijo     = (data.get("horario_fijo") or "").strip() or None,
            barberia_id      = barberia.id,
        )
        db.session.add(cliente)
        db.session.commit()
        return jsonify({"success": True, "mensaje": f"Cliente {nombre} registrado"})

    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "mensaje": str(e)})


@panel_bp.route("/editar-cliente", methods=["POST"])
def editar_cliente():
    barberia = _get_barberia_api()
    if not barberia:
        return jsonify({"success": False, "mensaje": "No autorizado"}), 401

    data     = request.get_json(silent=True) or {}
    telefono = (data.get("telefono") or "").strip()
    cliente  = Cliente.query.filter_by(telefono=telefono, barberia_id=barberia.id).first()
    if not cliente:
        return jsonify({"success": False, "mensaje": "Cliente no encontrado"})

    try:
        from datetime import datetime as dt
        if "nombre" in data:
            cliente.nombre = data["nombre"].strip()
        if "horario_fijo" in data:
            cliente.horario_fijo = (data["horario_fijo"] or "").strip() or None
        if "fijo" in data:
            cliente.fijo = bool(data["fijo"])
        if "fecha_cumpleanos" in data:
            raw = (data["fecha_cumpleanos"] or "").strip()
            cliente.fecha_cumpleanos = dt.strptime(raw, "%Y-%m-%d").date() if raw else None
        db.session.commit()
        return jsonify({"success": True, "mensaje": f"Cliente {cliente.nombre} actualizado"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "mensaje": str(e)})


@panel_bp.route("/crear-cita-panel", methods=["POST"])
def crear_cita_panel():
    barberia = _get_barberia_api()
    if not barberia:
        return jsonify({"success": False, "mensaje": "No autorizado"}), 401

    data       = request.get_json(silent=True) or {}
    nombre     = (data.get("nombre") or "").strip()
    telefono   = (data.get("telefono") or "").strip()
    barbero_id = data.get("barbero_id")
    fecha      = (data.get("fecha") or "").strip()
    hora       = (data.get("hora") or "").strip()
    servicio   = (data.get("servicio") or "").strip() or None

    if not all([nombre, telefono, barbero_id, fecha, hora]):
        return jsonify({"success": False, "mensaje": "Faltan datos"}), 400

    from app.services.agenda_service import crear_cita
    ok, mensaje = crear_cita(
        nombre, telefono, barbero_id, fecha, hora, servicio,
        skip_client_check=True, barberia_id=barberia.id
    )
    return jsonify({"success": ok, "mensaje": mensaje})


@panel_bp.route("/cancelar-cita-panel", methods=["POST"])
def cancelar_cita_panel():
    barberia = _get_barberia_api()
    if not barberia:
        return jsonify({"success": False, "mensaje": "No autorizado"}), 401

    data    = request.get_json(force=True, silent=True) or {}
    cita_id = data.get("cita_id")
    if not cita_id:
        return jsonify({"success": False, "mensaje": "cita_id requerido"})

    cita = Cita.query.filter_by(id=cita_id).first()
    if not cita:
        return jsonify({"success": False, "mensaje": f"Cita {cita_id} no encontrada"})

    cliente_obj = Cliente.query.filter_by(id=cita.cliente_id).first()
    nombre_cli  = cliente_obj.nombre if cliente_obj else "Desconocido"
    fecha_str2  = str(cita.fecha)
    hora_str    = cita.hora.strftime("%H:%M")

    try:
        # Si es cliente fijo, marcar como cancelada (no borrar) para liberar el slot en el panel.
        if cliente_obj and cliente_obj.fijo:
            cita.estado = "cancelada"
            db.session.commit()
        else:
            db.session.delete(cita)
            db.session.commit()
        try:
            from app.services.recordatorio_service import notificar_barbero
            notificar_barbero(
                nombre_cliente=nombre_cli, fecha=fecha_str2, hora=hora_str,
                accion="cancelada", barberia=barberia
            )
        except Exception:
            pass
        return jsonify({"success": True, "mensaje": "Cita cancelada",
                        "data": _build_panel_data(barberia.id)})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "mensaje": str(e)})


@panel_bp.route("/reparar-fijos", methods=["POST"])
def reparar_fijos():
    """Detecta y resuelve conflictos entre clientes regulares y slots de fijos."""
    barberia = _get_barberia_api()
    if not barberia:
        return jsonify({"success": False, "mensaje": "No autorizado"}), 401

    solo_preview = request.args.get("solo_preview") == "1"
    data         = request.get_json(silent=True) or {}
    hoy          = _colombia_today()
    dias_adelante = int(data.get("dias", 30))

    from app.services.recordatorio_service import _enviar_whatsapp
    from datetime import timedelta as td

    conflictos = []
    enviados   = 0
    canceladas = 0

    clientes_fijos = Cliente.query.filter_by(fijo=True, barberia_id=barberia.id).all()
    if not clientes_fijos:
        return jsonify({"success": True, "mensaje": "No hay clientes fijos registrados", "conflictos": []})

    for dias_ahead in range(dias_adelante + 1):
        fecha_check = hoy + td(days=dias_ahead)
        dia_semana  = fecha_check.weekday()
        if dia_semana == 6:
            continue
        fecha_str = fecha_check.strftime("%Y-%m-%d")

        for cf in clientes_fijos:
            hora_fija_str = _parsear_horario_fijo_panel(cf.horario_fijo, dia_semana)
            if not hora_fija_str:
                continue
            try:
                h, m_val = [int(x) for x in hora_fija_str.split(":")]
                hora_fija = time(h, m_val)
            except Exception:
                continue

            cita_conflicto = Cita.query.filter(
                Cita.fecha == fecha_check,
                Cita.hora == hora_fija,
                Cita.estado != "cancelada",
                Cita.barberia_id == barberia.id
            ).first()

            if not cita_conflicto:
                continue

            cli_conflicto = Cliente.query.get(cita_conflicto.cliente_id)
            if not cli_conflicto:
                continue

            def _ultimos_digitos(t):
                if not t:
                    return ""
                digits = "".join(c for c in t if c.isdigit())
                return digits[-10:] if len(digits) >= 10 else digits

            mismo_id  = cli_conflicto.id == cf.id
            mismo_tel = bool(
                cli_conflicto.telefono and cf.telefono and
                _ultimos_digitos(cli_conflicto.telefono) == _ultimos_digitos(cf.telefono)
            )
            mismo_nombre = (
                cli_conflicto.nombre and cf.nombre and
                cli_conflicto.nombre.strip().lower() == cf.nombre.strip().lower()
            )
            if mismo_id or mismo_tel or mismo_nombre:
                continue

            DIAS_ES   = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
            dia_nombre = DIAS_ES[dia_semana]

            conflictos.append({
                "fecha":               fecha_str,
                "dia":                 dia_nombre,
                "hora":                hora_fija_str,
                "cliente_fijo":        cf.nombre,
                "cliente_desplazado":  cli_conflicto.nombre,
                "telefono_desplazado": cli_conflicto.telefono,
                "cita_id":             cita_conflicto.id,
            })

            if not solo_preview:
                if cli_conflicto.telefono:
                    texto = (
                        f"💈 *BarberIA*\n\n"
                        f"Hola {cli_conflicto.nombre} 👋\n\n"
                        f"Tuvimos un problema con tu turno del *{dia_nombre} {fecha_check.day}* "
                        f"a las *{hora_fija_str}* — ese horario estaba reservado para otro cliente.\n\n"
                        f"Por favor escribe *reagendar* para elegir un nuevo horario.\n\n"
                        f"¡Disculpá las molestias!"
                    )
                    if _enviar_whatsapp(cli_conflicto.telefono, texto, barberia):
                        enviados += 1
                try:
                    db.session.delete(cita_conflicto)
                    db.session.commit()
                    canceladas += 1
                except Exception as e:
                    db.session.rollback()
                    print(f"⚠ Error cancelando cita conflictiva {cita_conflicto.id}: {e}")

    if solo_preview:
        return jsonify({
            "success": True, "preview": True,
            "total_conflictos": len(conflictos), "conflictos": conflictos
        })

    return jsonify({
        "success": True,
        "total_conflictos": len(conflictos),
        "canceladas": canceladas,
        "mensajes_enviados": enviados,
        "conflictos": conflictos,
        "mensaje": f"Se encontraron {len(conflictos)} conflicto(s). Canceladas: {canceladas}. Notificados: {enviados}."
    })


@panel_bp.route("/confirmar-citas", methods=["POST"])
def confirmar_citas():
    barberia = _get_barberia_api()
    if not barberia:
        return jsonify({"success": False, "mensaje": "No autorizado"}), 401

    data     = request.get_json(silent=True) or {}
    fecha_str = (data.get("fecha") or "").strip()

    try:
        fecha_obj = datetime.strptime(fecha_str, "%Y-%m-%d").date() if fecha_str else _colombia_today() + timedelta(days=1)
    except ValueError:
        fecha_obj = _colombia_today() + timedelta(days=1)

    DIAS_ES  = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    MESES_ES = ["enero", "febrero", "marzo", "abril", "mayo", "junio",
                "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
    dia_nombre   = DIAS_ES[fecha_obj.weekday()]
    fecha_bonita = f"{dia_nombre} {fecha_obj.day} de {MESES_ES[fecha_obj.month - 1]}"

    from app.services.recordatorio_service import _enviar_whatsapp

    enviados   = 0
    errores    = 0
    notificados = set()

    # Citas en BD
    citas_db = Cita.query.filter_by(fecha=fecha_obj, barberia_id=barberia.id).all()
    for cita in citas_db:
        cli = Cliente.query.get(cita.cliente_id)
        if not cli or not cli.telefono:
            errores += 1
            continue
        if cli.telefono in notificados:
            continue
        hora_fmt = cita.hora.strftime("%H:%M")
        texto = (
            f"💈 *BarberIA*\n\n"
            f"Hola {cli.nombre} 👋\n\n"
            f"✅ Tu cita está confirmada:\n\n"
            f"📅 {fecha_bonita}\n"
            f"⏰ {hora_fmt}\n\n"
            f"Por favor llegá 5 minutos antes.\n\n"
            f"Si no podés asistir escribí *cancelar*.\n\n"
            f"¡Te esperamos! 💈"
        )
        if _enviar_whatsapp(cli.telefono, texto, barberia):
            enviados += 1
        else:
            errores += 1
        notificados.add(cli.telefono)

    # Clientes fijos sin cita en BD para ese día
    dia_semana = fecha_obj.weekday()
    for cf in Cliente.query.filter_by(fijo=True, barberia_id=barberia.id).all():
        if not cf.telefono or cf.telefono in notificados:
            continue
        hora_fija_str = _parsear_horario_fijo_panel(cf.horario_fijo, dia_semana)
        if not hora_fija_str:
            continue
        texto = (
            f"💈 *BarberIA*\n\n"
            f"Hola {cf.nombre} 👋\n\n"
            f"✅ Tu turno habitual está confirmado:\n\n"
            f"📅 {fecha_bonita}\n"
            f"⏰ {hora_fija_str}\n\n"
            f"Por favor llegá 5 minutos antes.\n\n"
            f"Si no podés asistir escribí *cancelar*.\n\n"
            f"¡Te esperamos! 💈"
        )
        if _enviar_whatsapp(cf.telefono, texto, barberia):
            enviados += 1
        else:
            errores += 1
        notificados.add(cf.telefono)

    return jsonify({
        "success": True,
        "fecha": str(fecha_obj),
        "enviados": enviados,
        "errores": errores,
        "mensaje": f"Confirmaciones enviadas: {enviados}. Errores: {errores}."
    })


@panel_bp.route("/notificar-dia", methods=["POST"])
def notificar_dia():
    barberia = _get_barberia_api()
    if not barberia:
        return jsonify({"success": False, "mensaje": "No autorizado"}), 401

    data           = request.get_json(silent=True) or {}
    fecha_str      = (data.get("fecha") or "").strip()
    mensaje_custom = (data.get("mensaje") or "").strip()

    try:
        from datetime import datetime as dt
        fecha_obj = dt.strptime(fecha_str, "%Y-%m-%d").date() if fecha_str else None
    except ValueError:
        fecha_obj = None

    if not fecha_obj:
        return jsonify({"success": False, "mensaje": "Fecha inválida. Usar formato YYYY-MM-DD"})

    citas = Cita.query.filter_by(fecha=fecha_obj, barberia_id=barberia.id).all()
    if not citas:
        return jsonify({"success": False, "mensaje": f"No hay citas para el {fecha_str}"})

    from app.services.recordatorio_service import _enviar_whatsapp
    DIAS      = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    dia_nombre = DIAS[fecha_obj.weekday()]

    enviados = 0
    errores  = 0
    for cita in citas:
        cli = Cliente.query.get(cita.cliente_id)
        if not cli or not cli.telefono:
            errores += 1
            continue
        hora_fmt = cita.hora.strftime("%H:%M")
        if mensaje_custom:
            texto = (mensaje_custom
                     .replace("{nombre}", cli.nombre or "")
                     .replace("{hora}", hora_fmt)
                     .replace("{fecha}", str(fecha_obj)))
        else:
            texto = (
                f"💈 *BarberIA*\n\n"
                f"Hola {cli.nombre} 👋\n\n"
                f"Te avisamos que hubo un ajuste en el horario del *{dia_nombre} {fecha_obj.day}*.\n\n"
                f"Tu turno sigue registrado a las *{hora_fmt}* ✅\n\n"
                f"Si querés cancelar o cambiar tu turno escribinos por acá.\n\n"
                f"¡Te esperamos!"
            )
        ok = _enviar_whatsapp(cli.telefono, texto, barberia)
        if ok:
            enviados += 1
        else:
            errores += 1

    return jsonify({
        "success": True,
        "mensaje": f"Mensajes enviados: {enviados} / {len(citas)} citas. Errores: {errores}"
    })
