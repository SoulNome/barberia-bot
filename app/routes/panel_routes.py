import json
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

def obtener_horarios_dia(dia_semana):
    if dia_semana in [0, 1, 2]:
        return [(time(10,0), time(12,0)), (time(16,0), time(20,0))]
    if dia_semana == 3:
        return [(time(10,0), time(12,30)), (time(15,0), time(22,0))]
    if dia_semana == 4:
        return [(time(9,0), time(13,30)), (time(14,30), time(22,0))]
    if dia_semana == 5:
        return [(time(9,0), time(13,0)), (time(15,0), time(21,0))]
    return []

def _build_panel_data():
    hoy = date.today()
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
    bloques = obtener_horarios_dia(dia_semana)
    total_slots = 0
    for inicio, fin in bloques:
        actual = datetime.combine(hoy, inicio)
        while actual.time() < fin:
            total_slots += 1
            hora = actual.time()
            cita = next((c for c in citas if c.hora == hora), None)
            if cita:
                agenda.append({"hora": hora.strftime("%H:%M"), "cliente": clientes_dict.get(cita.cliente_id), "barbero": barberos_dict.get(cita.barbero_id), "servicio": cita.servicio, "cumpleanos": bool(cita.servicio and "🎂" in cita.servicio)})
            else:
                agenda.append({"hora": hora.strftime("%H:%M"), "cliente": None, "barbero": None, "servicio": None, "cumpleanos": False})
            actual += timedelta(minutes=30)
    ocupacion = int((citas_hoy / total_slots) * 100) if total_slots > 0 else 0
    return {"citas_hoy": citas_hoy, "clientes": clientes, "barberos": barberos_count, "ingresos_hoy": ingresos_hoy, "servicio_top": servicio_top, "ocupacion": ocupacion, "agenda": agenda}

@panel_bp.route("/panel")
def panel():
    key = request.args.get("key")
    if key != PANEL_KEY:
        return "No autorizado"
    data = _build_panel_data()
    return render_template("panel.html", **data)

@panel_bp.route("/panel-stream")
def panel_stream():
    key = request.args.get("key")
    if key != PANEL_KEY:
        return "No autorizado", 401

    from flask import current_app
    app = current_app._get_current_object()

    def generar():
        while True:
            try:
                with app.app_context():
                    payload = _build_panel_data()
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