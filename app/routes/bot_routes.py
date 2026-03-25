import os
import requests
from flask import Blueprint, request, jsonify

from app.services.conversation_service import manejar_mensaje
from app.services.barbero_service import obtener_barberos

bot_bp = Blueprint("bot", __name__)

EVOLUTION_API_URL = os.getenv("EVOLUTION_API_URL", "")
EVOLUTION_API_KEY = os.getenv("EVOLUTION_API_KEY", "")
EVOLUTION_INSTANCE = os.getenv("EVOLUTION_INSTANCE", "")


def enviar_respuesta(numero, texto):
    """Envía un mensaje de texto via Evolution API."""
    url = f"{EVOLUTION_API_URL}/message/sendText/{EVOLUTION_INSTANCE}"
    headers = {
        "apikey": EVOLUTION_API_KEY,
        "Content-Type": "application/json"
    }
    payload = {
        "number": numero,
        "text": texto
    }
    print(f"[DEBUG] Enviando a Evolution: url={url} numero={numero}")
    print(f"[DEBUG] API_KEY={EVOLUTION_API_KEY[:6]}... INSTANCE={EVOLUTION_INSTANCE}")
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=10)
        print(f"[DEBUG] Evolution respondió: {r.status_code} {r.text[:200]}")
    except Exception as e:
        print(f"[ERROR] No se pudo enviar mensaje: {e}")


@bot_bp.route("/bot", methods=["POST"])
def bot():
    try:
        data = request.get_json(silent=True) or {}

        import json
        print(f"\n[DEBUG] ===== WEBHOOK RECIBIDO =====")
        print(f"[DEBUG] Raw data: {json.dumps(data, indent=2)}")
        print(f"[DEBUG] ==============================\n")

        # Evolution API v1 envía en formato:
        # { "data": { "pushName": "Name", "message": {...}, "key": {...}, etc } }

        numero = None
        mensaje = None

        if "data" in data:
            msg_data = data["data"]
            print(f"[DEBUG] msg_data keys: {msg_data.keys()}")

            # Intentar extraer del campo 'sender' primero
            if "sender" in msg_data:
                numero = msg_data.get("sender", "").replace("@s.whatsapp.net", "").replace("@c.us", "")
                print(f"[DEBUG] Sender encontrado: {numero}")

            # O del campo 'key.remoteJid'
            if not numero and "key" in msg_data:
                remote_jid = msg_data["key"].get("remoteJid", "")
                numero = remote_jid.replace("@s.whatsapp.net", "").replace("@c.us", "")
                print(f"[DEBUG] RemoteJid encontrado: {numero}")

            # Extraer mensaje
            if "message" in msg_data:
                message_obj = msg_data["message"]
                mensaje = (
                    message_obj.get("conversation")
                    or message_obj.get("text", "")
                    or message_obj.get("body", "")
                ).strip().lower()
                print(f"[DEBUG] Mensaje encontrado: {mensaje}")

        print(f"[DEBUG] Número final: {numero}, Mensaje final: {mensaje}")

        if not numero or not mensaje:
            print("[DEBUG] Número o mensaje vacío, ignorando")
            return jsonify({"status": "ignored"}), 200

        barberos = obtener_barberos()
        respuesta = manejar_mensaje(f"+{numero}", mensaje, barberos)

        print(f"[DEBUG] Respuesta: {respuesta}")

        enviar_respuesta(numero, respuesta)

        return jsonify({"status": "ok"}), 200

    except Exception as e:
        print(f"[ERROR] En webhook: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500