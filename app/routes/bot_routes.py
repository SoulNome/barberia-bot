from flask import Blueprint, request
from twilio.twiml.messaging_response import MessagingResponse
import requests
import os

from app.services.conversation_service import manejar_mensaje

bot_bp = Blueprint("bot", __name__)

API_URL = os.environ.get("API_URL", "http://localhost:5000")


@bot_bp.route("/bot", methods=["POST"])
def bot():

    telefono = request.form.get("From")
    mensaje = (request.form.get("Body") or "").strip().lower()

    resp = MessagingResponse()

    r = requests.get(f"{API_URL}/barberos/")
    barberos = r.json()["barberos"]

    respuesta = manejar_mensaje(telefono, mensaje, barberos)

    resp.message(respuesta)

    return str(resp)