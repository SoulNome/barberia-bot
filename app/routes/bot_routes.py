import os
import json
import requests
from flask import Blueprint, request, jsonify

from app.services.conversation_service import manejar_mensaje
from app.services.barbero_service import obtener_barberos

bot_bp = Blueprint("bot", __name__)

EVOLUTION_API_URL  = os.getenv("EVOLUTION_API_URL", "").strip()
EVOLUTION_API_KEY  = os.getenv("EVOLUTION_API_KEY", "").strip()
EVOLUTION_INSTANCE = os.getenv("EVOLUTION_INSTANCE", "").strip()

HEADERS = {
    "apikey": EVOLUTION_API_KEY,
    "Content-Type": "application/json"
}


def resolver_jid(jid, push_name=""):
    """
    Convierte un JID @lid al número de teléfono real.
    Evolution API v1 no puede enviar a @lid directamente.
    Intenta buscarlo en los contactos de la instancia.
    """
    if "@lid" not in jid:
        return jid  # @s.whatsapp.net — válido directamente

    print(f"[DEBUG] Resolviendo @lid: {jid} (pushName={push_name})")

    try:
        url = f"{EVOLUTION_API_URL}/contact/findContacts/{EVOLUTION_INSTANCE}"
        r = requests.post(
            url,
            json={"where": {"id": jid}},
            headers=HEADERS,
            timeout=5
        )
        print(f"[DEBUG] Lookup contacto: {r.status_code} {r.text[:300]}")
        if r.status_code == 200:
            contacts = r.json()
            if isinstance(contacts, list):
                for c in contacts:
                    number = c.get("number") or c.get("phone") or c.get("id", "").split("@")[0]
                    if number and "@" not in str(number) and len(str(number)) > 5:
                        print(f"[DEBUG] @lid resuelto a: {number}")
                        return str(number)
    except Exception as e:
        print(f"[DEBUG] Error resolviendo @lid: {e}")

    # Fallback: devolver el @lid original (probablemente falle al enviar)
    print(f"[WARNING] No se pudo resolver @lid {jid} — Evolution v1 no soporta @lid nativamente. Considera actualizar a v2.")
    return jid


def enviar_respuesta(jid, texto):
    """Envía un mensaje de texto via Evolution API."""
    numero = resolver_jid(jid)

    url = f"{EVOLUTION_API_URL}/message/sendText/{EVOLUTION_INSTANCE}"
    payload = {
        "number": numero,
        "textMessage": {"text": texto}
    }
    print(f"[DEBUG] Enviando a: {numero}")
    try:
        r = requests.post(url, json=payload, headers=HEADERS, timeout=10)
        print(f"[DEBUG] Evolution respondió: {r.status_code} {r.text[:200]}")
    except Exception as e:
        print(f"[ERROR] No se pudo enviar mensaje: {e}")


@bot_bp.route("/bot", methods=["POST"])
def bot():
    try:
        data = request.get_json(silent=True) or {}

        print(f"\n[DEBUG] ===== WEBHOOK RECIBIDO =====")
        print(f"[DEBUG] Raw data: {json.dumps(data, indent=2)}")
        print(f"[DEBUG] ==============================\n")

        numero_jid = None
        mensaje    = None
        push_name  = ""

        if "data" in data:
            msg_data = data["data"]

            # Ignorar mensajes propios
            if msg_data.get("key", {}).get("fromMe"):
                print("[DEBUG] Mensaje propio, ignorando")
                return jsonify({"status": "ignored"}), 200

            push_name = msg_data.get("pushName", "")

            if "key" in msg_data:
                remote_jid = msg_data["key"].get("remoteJid", "")

                # Ignorar grupos y broadcasts
                if "@g.us" in remote_jid or "@broadcast" in remote_jid:
                    print(f"[DEBUG] Grupo/broadcast, ignorando: {remote_jid}")
                    return jsonify({"status": "ignored"}), 200

                numero_jid = remote_jid
                print(f"[DEBUG] RemoteJid: {numero_jid} | pushName: {push_name}")

            # Extraer texto — conversation, extendedTextMessage, text, body
            if "message" in msg_data:
                message_obj = msg_data["message"]
                extended = message_obj.get("extendedTextMessage", {})
                mensaje = (
                    message_obj.get("conversation")
                    or extended.get("text", "")
                    or message_obj.get("text", "")
                    or message_obj.get("body", "")
                )
                if mensaje:
                    mensaje = mensaje.strip().lower()
                print(f"[DEBUG] Mensaje: {mensaje}")

        if not numero_jid or not mensaje:
            print("[DEBUG] JID o mensaje vacío, ignorando")
            return jsonify({"status": "ignored"}), 200

        # ID de sesión = parte numérica del JID (consistente entre requests)
        numero_sesion = f"+{numero_jid.split('@')[0]}"

        barberos  = obtener_barberos()
        respuesta = manejar_mensaje(numero_sesion, mensaje, barberos)

        print(f"[DEBUG] Respuesta: {respuesta}")

        enviar_respuesta(numero_jid, respuesta)

        return jsonify({"status": "ok"}), 200

    except Exception as e:
        print(f"[ERROR] En webhook: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500
