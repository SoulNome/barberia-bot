import json
import time as time_module
from flask import Blueprint, request, render_template, Response, stream_with_context, jsonify
from app.models import Cita, Cliente, Barbero
from app.extensions import db
from datetime import date, datetime, time, timedelta
import os
from datetime import date as _date_cls

panel_bp = Blueprint("panel", __name__)

# ── Días festivos Colombia 2026 (Ley 51 de 1983) ──
FESTIVOS_COLOMBIA = {
    _date_cls(2026, 1, 1),   # Año Nuevo
    _date_cls(2026, 1, 12),  # Reyes Magos (trasladado)
    _date_cls(2026, 3, 23),  # San José (trasladado)
    _date_cls(2026, 4, 2),   # Jueves Santo
    _date_cls(2026, 4, 3),   # Viernes Santo
    _date_cls(2026, 5, 1),   # Día del Trabajo
    _date_cls(2026, 5, 18),  # Ascensión del Señor (trasladado)
    _date_cls(2026, 6, 8),   # Corpus Christi (trasladado)
    _date_cls(2026, 6, 15),  # Sagrado Corazón (trasladado)
    _date_cls(2026, 6, 29),  # San Pedro y San Pablo (trasladado al lun)
    _date_cls(2026, 7, 20),  # Independencia de Colombia
    _date_cls(2026, 8, 7),   # Batalla de Boyacá
    _date_cls(2026, 8, 17),  # Asunción de la Virgen (trasladado)
    _date_cls(2026, 10, 12), # Día de la Raza (trasladado)
    _date_cls(2026, 11, 2),  # Todos los Santos (trasladado)
    _date_cls(2026, 11, 16), # Independencia de Cartagena (trasladado)
    _date_cls(2026, 12, 8),  # Inmaculada Concepción
    _date_cls(2026, 12, 25), # Navidad
}

def es_festivo(fecha):
    return fecha in FESTIVOS_COLOMBIA
PANEL_KEY = os.getenv("PANEL_KEY")

PRECIOS = {
    "Corte niños": 15000,
    "Corte normal": 20000,
    "Corte + barba + tinte": 25000,
    "Corte + barba + tinte + alisadora": 30000,
    "Pigmentación cejas": 10000
}

def obtener_horarios_dia(dia_semana, fecha=None):
    if fecha and es_festivo(fecha):
        return []
    if dia_semana in [0, 1, 2]:
        return [(time(10,0), time(12,0)), (time(16,0), time(20,0))]
    if dia_semana == 3:
        return [(time(10,0), time(12,30)), (time(15,0), time(22,0))]
    if dia_semana == 4:
        return [(time(9,0), time(13,30)), (time(14,30), time(22,0))]
    if dia_semana == 5:
        return [(time(9,0), time(13,0)), (time(15,0), time(21,0))]
    return []

def _build_panel_data(fecha=None):
    hoy = fecha or date.today()
    citas = Cita.query.filter_by(fecha=hoy).all()
    citas_hoy = len(citas)
    clientes = Cliente.query.count()
    barberos_count = Barbero.query.count()
    clientes_dict = {c.id: c.nombre for c in Cliente.query.all()}
    barberos_dict = {b.id: b.nombre for b in Barbero.query.all()}
    ingresos_hoy = sum(PRECIOS.get(c.servicio, 0) for c in citas)
    conteo = {}
    for cita in citas:
        if cita.servicio:
            conteo[cita.servicio] = conteo.get(cita.servicio, 0) + 1
    servicio_top = max(conteo, key=conteo.get) if conteo else None
    agenda = []
    dia_semana = hoy.weekday()
    bloques = obtener_horarios_dia(dia_semana, hoy)
    total_slots = 0
    for inicio, fin in bloques:
        actual = datetime.combine(hoy, inicio)
        while actual.time() < fin:
            total_slots += 1
            hora = actual.time()
            cita = next((c for c in citas if c.hora == hora), None)
            if cita:
                agenda.append({"hora": hora.strftime("%H:%M"), "cita_id": cita.id, "cliente": clientes_dict.get(cita.cliente_id), "barbero": barberos_dict.get(cita.barbero_id), "servicio": cita.servicio, "cumpleanos": bool(cita.servicio and "🎂" in cita.servicio)})
            else:
                agenda.append({"hora": hora.strftime("%H:%M"), "cita_id": None, "cliente": None, "barbero": None, "servicio": None, "cumpleanos": False})
            actual += timedelta(minutes=30)
    ocupacion = int((citas_hoy / total_slots) * 100) if total_slots > 0 else 0
    # ── Overlay clientes fijos en slots libres del día ──
    import re as _re
    DIAS_FIJOS = {
        "lun": 0, "lunes": 0,
        "mar": 1, "martes": 1,
        "mie": 2, "miercoles": 2, "miércoles": 2,
        "jue": 3, "jueves": 3,
        "vie": 4, "viernes": 4, "vierne": 4,
        "sab": 5, "sabado": 5, "sabados": 5, "sábado": 5, "sábados": 5,
        "dom": 6, "domingo": 6, "domingos": 6
    }
    def _parse_hora_fijo(h_str):
        h_str = h_str.strip().lower().replace(" ", "")
        m = _re.match(r"(\d{1,2}):(\d{2})\s*(am|pm)?", h_str)
        if not m:
            m = _re.match(r"(\d{1,2})\s*(am|pm)", h_str)
            if m:
                hh, mm, ap = int(m.group(1)), 0, m.group(2)
            else:
                return None
        else:
            hh, mm, ap = int(m.group(1)), int(m.group(2)), m.group(3)
        if ap == "pm" and hh != 12:
            hh += 12
        elif ap == "am" and hh == 12:
            hh = 0
        try:
            return time(hh, mm).strftime("%H:%M")
        except Exception:
            return None
    for cf in Cliente.query.filter_by(fijo=True).all():
        if not cf.horario_fijo:
            continue
        # Separar múltiples horarios por "y"
        bloques_raw = _re.split(r"\s+y\s+", cf.horario_fijo.strip().lower())
        for bloque in bloques_raw:
            bloque = bloque.strip()
            # Saltar bi-semanales ("cada X 15 dias")
            if "15 dia" in bloque or "cada" in bloque:
                continue
            # Buscar día y hora
            dia_found = None
            for palabra in bloque.replace(",", " ").split():
                palabra_clean = palabra.rstrip("s").rstrip(",")
                if palabra_clean in DIAS_FIJOS:
                    dia_found = DIAS_FIJOS[palabra_clean]
                elif palabra in DIAS_FIJOS:
                    dia_found = DIAS_FIJOS[palabra]
            if dia_found is None or dia_found != dia_semana:
                continue
            # Extraer hora del bloque
            hora_match = _re.search(r"(\d{1,2}:\d{2}\s*(?:am|pm)?|\d{1,2}\s*(?:am|pm))", bloque)
            if not hora_match:
                continue
            hora_fija = _parse_hora_fijo(hora_match.group(1))
            if not hora_fija:
                continue
            for slot in agenda:
                if slot["hora"] == hora_fija and slot["cita_id"] is None and slot["cliente"] is None:
                    slot["cliente"] = cf.nombre
                    slot["es_fijo"] = True
                    break
    return {"citas_hoy": citas_hoy, "clientes": clientes, "barberos": barberos_count, "ingresos_hoy": ingresos_hoy, "servicio_top": servicio_top, "ocupacion": ocupacion, "agenda": agenda, "fecha_iso": hoy.isoformat()}

@panel_bp.route("/panel")
def panel():
    key = request.args.get("key")
    if key != PANEL_KEY:
        return "No autorizado"
    fecha_str = request.args.get("fecha", "")
    try:
        fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date() if fecha_str else date.today()
    except ValueError:
        fecha = date.today()
    hoy = date.today()
    es_hoy = fecha == hoy
    DIAS = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"]
    MESES = ["Ene","Feb","Mar","Abr","May","Jun","Jul","Ago","Sep","Oct","Nov","Dic"]
    fecha_label = f"{DIAS[fecha.weekday()]} {fecha.day} {MESES[fecha.month-1]} {fecha.year}"
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
