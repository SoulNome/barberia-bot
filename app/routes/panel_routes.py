import json
import re
import time as time_module
from flask import Blueprint, request, render_template, Response, stream_with_context, jsonify
from app.models import Cita, Cliente, Barbero
from app.extensions import db
from datetime import date, datetime, time, timedelta
import os

panel_bp = Blueprint("panel", __name__)
PANEL_KEY = os.getenv("PANEL_KEY")

def _colombia_today():
    """Fecha actual en Colombia (UTC-5). El servidor Railway corre en UTC."""
    return (datetime.utcnow() - timedelta(hours=5)).date()

PRECIOS = {
    "Corte niños": 15000,
    "Corte normal": 20000,
    "Corte + barba + tinte": 25000,
    "Corte + barba + tinte + alisadora": 30000,
    "Pigmentación cejas": 10000
}

_DIAS_NUM_PANEL = {
    "lunes": 0, "martes": 1, "miércoles": 2, "miercoles": 2,
    "jueves": 3, "viernes": 4, "sábado": 5, "sabado": 5
}

def _parsear_horario_fijo_panel(horario_str, dia_semana):
    """Retorna 'HH:MM' (24h) si el horario_fijo coincide con dia_semana, si no None.
    Soporta am/pm, múltiples entradas separadas por 'y', y horas ambiguas 1-8 (asume PM).
    """
    if not horario_str:
        return None
    texto = horario_str.lower()

    # Separar entradas como "Miercoles 6:00 am y Sabados 6:30 pm"
    partes = re.split(r'\s+y\s+', texto)

    for parte in partes:
        # Buscar si hay un nombre de día en esta parte
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
            # Sin indicador, horas 1-8 → asumir PM (tarde/noche)
            h += 12

        return f"{h:02d}:{mins:02d}"

    return None

def obtener_horarios_dia(dia_semana):
    if dia_semana in [0, 1, 2]:          # L-M-X: último turno 21:00
        return [(time(10,0), time(12,0)), (time(16,0), time(21,30))]
    if dia_semana == 3:                  # Jueves: hasta la 1, arranca 2, último 21:00
        return [(time(10,0), time(13,0)), (time(14,0), time(21,30))]
    if dia_semana == 4:                  # Viernes: hasta la 1, arranca 2, último 22:00
        return [(time(9,0), time(13,0)), (time(14,0), time(22,30))]
    if dia_semana == 5:                  # Sábado: hasta la 1, arranca 2, último 21:00
        return [(time(9,0), time(13,0)), (time(14,0), time(21,30))]
    return []

def _build_panel_data(fecha=None):
    hoy = fecha or _colombia_today()
    citas = Cita.query.filter_by(fecha=hoy).all()
    citas_hoy = len(citas)
    clientes = Cliente.query.count()
    barberos_count = Barbero.query.count()
    clientes_dict = {c.id: c for c in Cliente.query.all()}
    barberos_dict = {b.id: b.nombre for b in Barbero.query.all()}
    ingresos_hoy = sum(PRECIOS.get(c.servicio, 0) for c in citas)
    conteo = {}
    for cita in citas:
        if cita.servicio:
            conteo[cita.servicio] = conteo.get(cita.servicio, 0) + 1
    servicio_top = max(conteo, key=conteo.get) if conteo else None

    # Slots virtuales de clientes fijos para este día
    dia_semana = hoy.weekday()
    fijo_slots = {}  # time -> nombre cliente
    clientes_fijos_lista = []
    for cf in Cliente.query.filter_by(fijo=True).all():
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

    agenda = []
    bloques = obtener_horarios_dia(dia_semana)
    total_slots = 0
    for inicio, fin in bloques:
        actual = datetime.combine(hoy, inicio)
        while actual.time() < fin:
            total_slots += 1
            hora = actual.time()
            cita = next((c for c in citas if c.hora == hora), None)
            if cita:
                cli_obj = clientes_dict.get(cita.cliente_id)
                nombre_cli = cli_obj.nombre if cli_obj else None
                es_fijo = bool(cli_obj and cli_obj.fijo)
                agenda.append({
                    "hora": hora.strftime("%H:%M"),
                    "cita_id": cita.id,
                    "cliente": nombre_cli,
                    "barbero": barberos_dict.get(cita.barbero_id),
                    "servicio": cita.servicio,
                    "cumpleanos": bool(cita.servicio and "🎂" in cita.servicio),
                    "fijo": es_fijo
                })
            elif hora in fijo_slots:
                # Slot virtual de cliente fijo (sin cita en DB)
                agenda.append({
                    "hora": hora.strftime("%H:%M"),
                    "cita_id": None,
                    "cliente": fijo_slots[hora],
                    "barbero": None,
                    "servicio": "📌 Turno fijo",
                    "cumpleanos": False,
                    "fijo": True
                })
            else:
                agenda.append({
                    "hora": hora.strftime("%H:%M"),
                    "cita_id": None,
                    "cliente": None,
                    "barbero": None,
                    "servicio": None,
                    "cumpleanos": False,
                    "fijo": False
                })
            actual += timedelta(minutes=30)

    # Añadir citas que caen FUERA de los slots del horario actual (horario cambió después de agendar)
    horas_en_agenda = {row["hora"] for row in agenda}
    for cita in citas:
        hora_str = cita.hora.strftime("%H:%M")
        if hora_str not in horas_en_agenda:
            cli_obj = clientes_dict.get(cita.cliente_id)
            nombre_cli = cli_obj.nombre if cli_obj else None
            es_fijo = bool(cli_obj and cli_obj.fijo)
            agenda.append({
                "hora": hora_str,
                "cita_id": cita.id,
                "cliente": nombre_cli,
                "barbero": barberos_dict.get(cita.barbero_id),
                "servicio": cita.servicio,
                "cumpleanos": bool(cita.servicio and "🎂" in cita.servicio),
                "fijo": es_fijo
            })
            horas_en_agenda.add(hora_str)

    # Añadir fijos con horario FUERA del rango normal (casos excepcionales)
    for t_fijo, nombre_fijo in sorted(fijo_slots.items()):
        hora_str = t_fijo.strftime("%H:%M")
        if hora_str not in horas_en_agenda:
            agenda.append({
                "hora": hora_str,
                "cita_id": None,
                "cliente": nombre_fijo,
                "barbero": None,
                "servicio": "📌 Turno fijo (excepcional)",
                "cumpleanos": False,
                "fijo": True
            })
    # Reordenar agenda por hora
    agenda.sort(key=lambda r: r["hora"])

    ocupacion = int((citas_hoy / total_slots) * 100) if total_slots > 0 else 0
    barberos_lista = [{"id": b.id, "nombre": b.nombre} for b in Barbero.query.order_by(Barbero.nombre).all()]

    return {
        "citas_hoy": citas_hoy,
        "clientes": clientes,
        "barberos": barberos_count,
        "barberos_lista": barberos_lista,
        "ingresos_hoy": ingresos_hoy,
        "servicio_top": servicio_top,
        "ocupacion": ocupacion,
        "agenda": agenda,
        "clientes_fijos": clientes_fijos_lista,
        "fecha_iso": hoy.isoformat()
    }

@panel_bp.route("/panel")
def panel():
    key = request.args.get("key")
    if key != PANEL_KEY:
        return "No autorizado"
    fecha_str = request.args.get("fecha", "")
    try:
        fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date() if fecha_str else _colombia_today()
    except ValueError:
        fecha = _colombia_today()
    hoy = _colombia_today()
    es_hoy = fecha == hoy
    es_manana = fecha == hoy + timedelta(days=1)
    DIAS = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"]
    MESES = ["Enero","Febrero","Marzo","Abril","Mayo","Junio","Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]
    base_label = f"{DIAS[fecha.weekday()]} {fecha.day} de {MESES[fecha.month-1]}"
    if es_hoy:
        fecha_label = f"Hoy · {base_label}"
    elif es_manana:
        fecha_label = f"Mañana · {base_label}"
    else:
        fecha_label = f"{base_label} {fecha.year}"
    fecha_prev = (fecha - timedelta(days=1)).isoformat()
    fecha_next = (fecha + timedelta(days=1)).isoformat()
    data = _build_panel_data(fecha)
    return render_template("panel.html", **data,
                           key=key, es_hoy=es_hoy,
                           fecha_label=fecha_label,
                           fecha_prev=fecha_prev, fecha_next=fecha_next)

@panel_bp.route("/panel-stream")
def panel_stream():
    key = request.args.get("key")
    if key != PANEL_KEY:
        return "No autorizado", 401

    from flask import current_app
    app = current_app._get_current_object()

    fecha_str = request.args.get("fecha", "")
    try:
        fecha_sse = datetime.strptime(fecha_str, "%Y-%m-%d").date() if fecha_str else None
    except ValueError:
        fecha_sse = None

    def generar():
        while True:
            try:
                with app.app_context():
                    payload = _build_panel_data(fecha_sse)
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
    key = request.args.get("key")
    if key != PANEL_KEY:
        return jsonify({"success": False, "mensaje": "No autorizado"}), 401
    try:
        from scripts.importar_clientes import importar
        import sys, os
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from flask import current_app
        resultado = importar(app=current_app._get_current_object())
        return jsonify({"success": True, **resultado})
    except Exception as e:
        return jsonify({"success": False, "mensaje": str(e)})


@panel_bp.route("/crear-cliente", methods=["POST"])
def crear_cliente():
    key = request.args.get("key") or request.json.get("key")
    if key != PANEL_KEY:
        return jsonify({"success": False, "mensaje": "No autorizado"}), 401

    data = request.get_json()
    telefono = (data.get("telefono") or "").strip()

    if not data.get("nombre") or not telefono:
        return jsonify({"success": False, "mensaje": "Nombre y teléfono son obligatorios"})

    if Cliente.query.filter_by(telefono=telefono).first():
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
        )
        db.session.add(cliente)
        db.session.commit()
        return jsonify({"success": True, "mensaje": f"Cliente {nombre} registrado"})

    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "mensaje": str(e)})


@panel_bp.route("/editar-cliente", methods=["POST"])
def editar_cliente():
    key = request.args.get("key") or (request.get_json(silent=True) or {}).get("key")
    if key != PANEL_KEY:
        return jsonify({"success": False, "mensaje": "No autorizado"}), 401

    data = request.get_json(silent=True) or {}
    telefono = (data.get("telefono") or "").strip()
    cliente = Cliente.query.filter_by(telefono=telefono).first()
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


@panel_bp.route("/cancelar-cita-panel", methods=["POST"])
def cancelar_cita_panel():
    key = request.args.get("key")
    if not key or key != PANEL_KEY:
        return jsonify({"success": False, "mensaje": "No autorizado"}), 401
    data = request.get_json(force=True, silent=True) or {}
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
        db.session.delete(cita)
        db.session.commit()
        try:
            from app.services.recordatorio_service import notificar_barbero
            notificar_barbero(nombre_cliente=nombre_cli, fecha=fecha_str2, hora=hora_str, accion="cancelada")
        except Exception:
            pass
        return jsonify({"success": True, "mensaje": "Cita cancelada", "data": _build_panel_data()})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "mensaje": str(e)})


@panel_bp.route("/reparar-fijos", methods=["POST"])
def reparar_fijos():
    """
    Detecta citas de clientes NO-fijos que ocupan slots reservados para clientes fijos.
    - Envía WhatsApp al cliente desplazado pidiéndole reagendar.
    - Cancela la cita conflictiva para devolver el slot al cliente fijo.
    - Pasa ?solo_preview=1 para ver los conflictos SIN cancelar ni enviar mensajes.
    """
    key = request.args.get("key") or (request.get_json(silent=True) or {}).get("key")
    if key != PANEL_KEY:
        return jsonify({"success": False, "mensaje": "No autorizado"}), 401

    solo_preview = request.args.get("solo_preview") == "1"
    data = request.get_json(silent=True) or {}

    # Rango de fechas a revisar (por defecto: hoy + 30 días)
    from datetime import datetime as dt, timedelta as td
    hoy = _colombia_today()
    dias_adelante = int(data.get("dias", 30))

    from app.services.recordatorio_service import _enviar_whatsapp

    conflictos = []
    enviados = 0
    canceladas = 0

    clientes_fijos = Cliente.query.filter_by(fijo=True).all()
    if not clientes_fijos:
        return jsonify({"success": True, "mensaje": "No hay clientes fijos registrados", "conflictos": []})

    for dias_ahead in range(dias_adelante + 1):
        fecha_check = hoy + td(days=dias_ahead)
        dia_semana = fecha_check.weekday()
        if dia_semana == 6:  # domingo
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

            # Buscar cita en ese slot que NO pertenece al cliente fijo
            cita_conflicto = Cita.query.filter_by(
                fecha=fecha_check,
                hora=hora_fija
            ).first()

            if not cita_conflicto:
                continue

            cli_conflicto = Cliente.query.get(cita_conflicto.cliente_id)
            if not cli_conflicto:
                continue

            # Si la cita pertenece al mismo cliente fijo, no hay conflicto
            if cli_conflicto.id == cf.id:
                continue

            DIAS_ES = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
            dia_nombre = DIAS_ES[dia_semana]

            conflictos.append({
                "fecha": fecha_str,
                "dia": dia_nombre,
                "hora": hora_fija_str,
                "cliente_fijo": cf.nombre,
                "cliente_desplazado": cli_conflicto.nombre,
                "telefono_desplazado": cli_conflicto.telefono,
                "cita_id": cita_conflicto.id,
            })

            if not solo_preview:
                # Notificar al cliente desplazado
                if cli_conflicto.telefono:
                    texto = (
                        f"💈 *BarberIA*\n\n"
                        f"Hola {cli_conflicto.nombre} 👋\n\n"
                        f"Tuvimos un problema con tu turno del *{dia_nombre} {fecha_check.day}* "
                        f"a las *{hora_fija_str}* — ese horario estaba reservado para otro cliente.\n\n"
                        f"Por favor escribe *reagendar* para elegir un nuevo horario.\n\n"
                        f"¡Disculpá las molestias!"
                    )
                    if _enviar_whatsapp(cli_conflicto.telefono, texto):
                        enviados += 1

                # Cancelar la cita conflictiva
                try:
                    db.session.delete(cita_conflicto)
                    db.session.commit()
                    canceladas += 1
                except Exception as e:
                    db.session.rollback()
                    print(f"⚠ Error cancelando cita conflictiva {cita_conflicto.id}: {e}")

    if solo_preview:
        return jsonify({
            "success": True,
            "preview": True,
            "total_conflictos": len(conflictos),
            "conflictos": conflictos
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
    """
    Envía mensajes de confirmación a TODOS los clientes con cita en una fecha.
    Por defecto usa mañana. Incluye clientes fijos aunque no tengan cita en BD.
    Body JSON opcional: {"fecha": "YYYY-MM-DD"}
    """
    key = request.args.get("key") or (request.get_json(silent=True) or {}).get("key")
    if key != PANEL_KEY:
        return jsonify({"success": False, "mensaje": "No autorizado"}), 401

    data = request.get_json(silent=True) or {}
    fecha_str = (data.get("fecha") or "").strip()

    try:
        fecha_obj = datetime.strptime(fecha_str, "%Y-%m-%d").date() if fecha_str else _colombia_today() + timedelta(days=1)
    except ValueError:
        fecha_obj = _colombia_today() + timedelta(days=1)

    DIAS_ES = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    MESES_ES = ["enero", "febrero", "marzo", "abril", "mayo", "junio",
                "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
    dia_nombre = DIAS_ES[fecha_obj.weekday()]
    fecha_bonita = f"{dia_nombre} {fecha_obj.day} de {MESES_ES[fecha_obj.month - 1]}"

    from app.services.recordatorio_service import _enviar_whatsapp

    enviados = 0
    errores = 0
    notificados = set()  # evitar duplicados por teléfono

    # ── 1. Clientes con cita en BD ───────────────────────────────────────────
    citas_db = Cita.query.filter_by(fecha=fecha_obj).all()
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
        if _enviar_whatsapp(cli.telefono, texto):
            enviados += 1
        else:
            errores += 1
        notificados.add(cli.telefono)

    # ── 2. Clientes fijos que NO tienen cita en BD para ese día ─────────────
    dia_semana = fecha_obj.weekday()
    for cf in Cliente.query.filter_by(fijo=True).all():
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
        if _enviar_whatsapp(cf.telefono, texto):
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
    """Envía un mensaje WhatsApp a todos los clientes con cita en una fecha dada."""
    key = request.args.get("key") or (request.get_json(silent=True) or {}).get("key")
    if key != PANEL_KEY:
        return jsonify({"success": False, "mensaje": "No autorizado"}), 401

    data = request.get_json(silent=True) or {}
    fecha_str = (data.get("fecha") or "").strip()
    mensaje_custom = (data.get("mensaje") or "").strip()

    try:
        from datetime import datetime as dt
        fecha_obj = dt.strptime(fecha_str, "%Y-%m-%d").date() if fecha_str else None
    except ValueError:
        fecha_obj = None

    if not fecha_obj:
        return jsonify({"success": False, "mensaje": "Fecha inválida. Usar formato YYYY-MM-DD"})

    citas = Cita.query.filter_by(fecha=fecha_obj).all()
    if not citas:
        return jsonify({"success": False, "mensaje": f"No hay citas para el {fecha_str}"})

    from app.services.recordatorio_service import _enviar_whatsapp
    DIAS = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"]
    dia_nombre = DIAS[fecha_obj.weekday()]

    enviados = 0
    errores = 0
    for cita in citas:
        cli = Cliente.query.get(cita.cliente_id)
        if not cli or not cli.telefono:
            errores += 1
            continue
        hora_fmt = cita.hora.strftime("%H:%M")
        if mensaje_custom:
            texto = mensaje_custom.replace("{nombre}", cli.nombre or "").replace("{hora}", hora_fmt).replace("{fecha}", str(fecha_obj))
        else:
            texto = (
                f"💈 *BarberIA*\n\n"
                f"Hola {cli.nombre} 👋\n\n"
                f"Te avisamos que hubo un ajuste en el horario del *{dia_nombre} {fecha_obj.day}*.\n\n"
                f"Tu turno sigue registrado a las *{hora_fmt}* ✅\n\n"
                f"Si querés cancelar o cambiar tu turno escribinos por acá.\n\n"
                f"¡Te esperamos!"
            )
        ok = _enviar_whatsapp(cli.telefono, texto)
        if ok:
            enviados += 1
        else:
            errores += 1

    return jsonify({
        "success": True,
        "mensaje": f"Mensajes enviados: {enviados} / {len(citas)} citas. Errores: {errores}"
    })