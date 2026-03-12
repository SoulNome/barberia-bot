from flask import Blueprint, jsonify
from app.services.barbero_service import obtener_barberos

barberos_bp = Blueprint("barberos", __name__)

@barberos_bp.route("/", methods=["GET"])
def listar_barberos():

    barberos = obtener_barberos()

    return jsonify({
        "barberos": barberos
    })