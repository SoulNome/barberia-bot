from flask import Blueprint, request, jsonify
from app.services.disponibilidad_service import obtener_horarios_disponibles

disponibilidad_bp = Blueprint("disponibilidad", __name__)

@disponibilidad_bp.route("/horarios", methods=["GET"])
def horarios():

    barbero_id = request.args.get("barbero_id")
    fecha = request.args.get("fecha")

    horarios = obtener_horarios_disponibles(barbero_id, fecha)

    return jsonify({
        "horarios": horarios
    })