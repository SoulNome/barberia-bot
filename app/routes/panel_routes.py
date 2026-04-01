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
    """Retorna 'HH:MM' si el horario_fijo coincide con dia_semana, si no None."""
    if not horario_str:
        return None
    texto = horario_str.lower()
    m = re.search(r'(\d{1,2}:\d{2})', texto)
    if not m:
        return None
    hora_str = m.group(1)
    for nombre, num in _DIAS_NUM_PANEL.items():
        if nombre in texto and num == dia_semana:
            return hora_str
    return None

def obtener_horarios_dia(dia_semana):
    if dia_semana in [0, 1, 2]:          # L-M-X: último turno 21:00
        return [(time(10,0), time(12,0)), (time(16,0), time(21,30))]
    if dia_semana == 3:                  # Jueves: último turno 21:00
        return [(time(10,0), time(12,30)), (time(15,0), time(21,30))]
    if dia_semana == 4:                  # Viernes: último turno 22:00
        return [(time(9,0), time(13,30)), (time(14,30), time(22,30))]
    if dia_semana == 5:                  # Sábado: último turno 21:00
        return [(time(9,0), time(13,0)), (time(15,0), time(21,30))]
    return []

def _build_panel_data(fecha=None):
    hoy = fecha or date.today()
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