from flask import Blueprint, request, jsonify
from app.services.agenda_service import crear_cita, cancelar_cita

agenda_bp = Blueprint("agenda", __name__)


@agenda_bp.route("/crear-cita", methods=["POST"])
def crear():

    data = request.get_json()

    if not data:
        return jsonify({
            "success": False,
            "mensaje": "No se enviaron datos"
        }), 400

    nombre = data.get("nombre")
    telefono = data.get("telefono")
    barbero_id = data.get("barbero_id")
    fecha = data.get("fecha")
    hora = data.get("hora")

    if not all([nombre, telefono, barbero_id, fecha, hora]):
        return jsonify({
            "success": False,
            "mensaje": "Faltan datos"
        }), 400

    servicio = data.get("servicio")

    ok, mensaje = crear_cita(
        nombre,
        telefono,
        barbero_id,
        fecha,
        hora,
        servicio
    )

    return jsonify({
        "success": ok,
        "mensaje": mensaje
    })


@agenda_bp.route("/cancelar-cita", methods=["POST"])
def cancelar():

    data = request.get_json()

    telefono = data.get("telefono")
    fecha = data.get("fecha")
    hora = data.get("hora")

    ok, mensaje = cancelar_cita(
        telefono,
        fecha,
        hora
    )

    return jsonify({
        "success": ok,
        "mensaje": mensaje
    })