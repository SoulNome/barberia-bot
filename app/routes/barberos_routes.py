from flask import Blueprint, request
from twilio.twiml.messaging_response import MessagingResponse
import os

from app.services.conversation_service import manejar_mensaje
from app.services.barbero_service import obtener_barberos

bot_bp = Blueprint("bot", __name__)

@bot_bp.route("/bot", methods=["POST"])
def bot():

    telefono = request.form.get("From")
    mensaje = (request.form.get("Body") or "").strip().lower()

    resp = MessagingResponse()

    barberos = obtener_barberos()

    respuesta = manejar_mensaje(telefono, mensaje, barberos)

    resp.message(respuesta)

    return str(resp)