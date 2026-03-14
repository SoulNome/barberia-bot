from flask import Blueprint, request, jsonify
from app.services.disponibilidad_service import obtener_horarios_disponibles

disponibilidad_bp = Blueprint("disponibilidad", __name__)

@disponibilidad_bp.route("/horarios", methods=["GET"])
def horarios():

    barbero_id = request.args.get("barbero_id")
    fecha = request.args.get("fecha")

    resultado = obtener_horarios_disponibles(barbero_id, fecha)

    if resultado in ("domingo", "festivo") or resultado is None:
        return jsonify({"horarios": [], "cerrado": True})

    disponibles = [h for h in resultado if h["disponible"]]
    return jsonify({"horarios": disponibles})