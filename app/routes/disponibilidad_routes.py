from flask import Blueprint, request, jsonify
from app.services.disponibilidad_service import obtener_horarios_disponibles

disponibilidad_bp = Blueprint("disponibilidad", __name__)

@disponibilidad_bp.route("/horarios", methods=["GET"])
def horarios():

    barbero_id_raw = request.args.get("barbero_id")
    fecha = request.args.get("fecha")

    if not barbero_id_raw or not fecha:
        return jsonify({"horarios": [], "cerrado": False, "error": "Faltan parámetros"}), 400

    try:
        barbero_id = int(barbero_id_raw)
    except (ValueError, TypeError):
        return jsonify({"horarios": [], "cerrado": False, "error": "barbero_id invalido"}), 400

    # Detectar barberia_id desde el barbero para usar sus horarios propios
    barberia_id = None
    try:
        from app.models.barbero import Barbero
        b = Barbero.query.get(barbero_id)
        if b:
            barberia_id = b.barberia_id
    except Exception:
        pass

    resultado = obtener_horarios_disponibles(barbero_id, fecha, barberia_id)

    if resultado in ("domingo", "festivo") or resultado is None:
        return jsonify({"horarios": [], "cerrado": True})

    disponibles = [h for h in resultado if h["disponible"]]
    return jsonify({"horarios": disponibles})