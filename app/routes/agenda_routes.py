from flask import Blueprint, request, jsonify
from app.services.agenda_service import crear_cita

agenda_bp = Blueprint("agenda", __name__)


@agenda_bp.route("/crear-cita", methods=["POST"])
def crear():

    data = request.json

    ok, mensaje = crear_cita(
        data["cliente_id"],
        data["barbero_id"],
        data["fecha"],
        data["hora"]
    )

    return jsonify({
        "success": ok,
        "mensaje": mensaje
    })