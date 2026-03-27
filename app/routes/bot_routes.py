import os
import json
import requests
from flask import Blueprint, request, jsonify

from app.extensions import db
from app.models.contact_map import ContactMap
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


def guardar_contacto(lid, phone, push_name=""):
    """Guarda o actualiza el mapeo @lid → teléfono en la BD."""
    try:
        lid_clean   = lid.replace("@lid", "")
        phone_clean = str(phone).replace("@s.whatsapp.net", "").replace("@c.us", "")
        if not lid_clean or not phone_clean:
            return
        existing = ContactMap.query.filter_by(lid=lid_clean).first()
        if existing:
            existing.phone     = phone_clean
            existing.push_name = push_name
        else:
            db.session.add(ContactMap(lid=lid_clean, phone=phone_clean, push_name=push_name))
        db.session.commit()
        print(f"[CONTACT] Guardado: {lid_clean} → {phone_clean} ({push_name})")
    except Exception as e:
        print(f"[CONTACT] Error guardando contacto: {e}")
        db.session.rollback()


def resolver_numero(jid):
    """
    Convierte @lid al número real buscando en la tabla contact_map.
    Si no está en la tabla, devuelve el JID original.
    """
    if "@lid" not in jid:
        return jid

    lid_clean = jid.replace("@lid", "")
    mapping   = ContactMap.query.filter_by(lid=lid_clean).first()
    if mapping:
        print(f"[CONTACT] @lid resuelto: {jid} → {mapping.phone}")
        return mapping.phone
    print(f"[CONTACT] @lid sin mapeo aún: {jid}")
    return jid


def enviar_respuesta(jid, texto):
    """Envía un mensaje de texto via Evolution API."""
    numero = resolver_numero(jid)
    url    = f"{EVOLUTION_API_URL}/message/sendText/{EVOLUTION_INSTANCE}"
    payload = {"number": numero, "textMessage": {"text": texto}}
    print(f"[DEBUG] Enviando a: {numero}")
    try:
        r = requests.post(url, json=payload, headers=HEADERS, timeout=10)
        print(f"[DEBUG] Evolution respondió: {r.status_code} {r.text[:200]}")
    except Exception as e:
        print(f"[ERROR] No se pudo enviar mensaje: {e}")


def procesar_contacts_upsert(data):
    """Captura el mapeo @lid → teléfono del evento contacts.upsert."""
    contacts = data.get("data", [])
    if not isinstance(contacts, list):
        contacts = [contacts]
    for c in contacts:
        jid   = c.get("id", "")
        phone = c.get("notify") or c.get("verifiedName") or c.get("name") or ""
        # El número real puede venir en campos como 'phone' o el propio 'id' sin @lid
        # Si el id es @s.whatsapp.net, el número es la parte antes del @
        if "@s.whatsapp.net" in jid or "@c.us" in jid:
            phone_clean = jid.replace("@s.whatsapp.net", "").replace("@c.us", "")
            push_name   = c.get("name") or c.get("notify") or ""
            # Buscar si hay un @lid asociado
            lid = c.get("lid") or c.get("lidJid") or ""
            if lid:
                guardar_contacto(lid, phone_clean, push_name)
        # Si el contacto tiene un campo 'phone' separado
        if "@lid" in jid and c.get("phone"):
            guardar_contacto(jid, c["phone"], c.get("name", ""))


@bot_bp.route("/bot", methods=["POST"])
def bot():
    try:
        data = request.get_json(silent=True) or {}

        event = data.get("event", "")

        # Capturar mapeo @lid → teléfono
        if event == "contacts.upsert":
            print(f"[CONTACT] contacts.upsert data: {json.dumps(data, indent=2)}")
            procesar_contacts_upsert(data)
            return jsonify({"status": "ok"}), 200

        if event != "messages.upsert":
            return jsonify({"status": "ignored"}), 200

        print(f"\n[DEBUG] ===== MENSAJE RECIBIDO =====")
        print(f"[DEBUG] Raw data: {json.dumps(data, indent=2)}")
        print(f"[DEBUG] ==============================\n")

        numero_jid = None
        mensaje    = None

        if "data" in data:
            msg_data = data["data"]

            # Ignorar mensajes propios
            if msg_data.get("key", {}).get("fromMe"):
                return jsonify({"status": "ignored"}), 200

            push_name = msg_data.get("pushName", "")

            if "key" in msg_data:
                remote_jid = msg_data["key"].get("remoteJid", "")

                # Ignorar grupos y broadcasts
                if "@g.us" in remote_jid or "@broadcast" in remote_jid:
                    return jsonify({"status": "ignored"}), 200

                numero_jid = remote_jid

                # Si es @lid, intentar guardar el mapeo desde pushName (fallback)
                if "@lid" in remote_jid and push_name:
                    print(f"[CONTACT] Mensaje de @lid: {remote_jid} (pushName={push_name})")

            # Extraer texto
            if "message" in msg_data:
                message_obj = msg_data["message"]
                extended    = message_obj.get("extendedTextMessage", {})
                mensaje     = (
                    message_obj.get("conversation")
                    or extended.get("text", "")
                    or message_obj.get("text", "")
                    or message_obj.get("body", "")
                )
                if mensaje:
                    mensaje = mensaje.strip().lower()

        if not numero_jid:
            return jsonify({"status": "ignored"}), 200

        if not mensaje:
            # Mensaje no es texto (audio, imagen, sticker, etc.)
            enviar_respuesta(numero_jid, "Hola! Solo puedo leer mensajes de texto 😊 Por favor escríbeme tu consulta.")
            return jsonify({"status": "ok"}), 200

        numero_sesion = f"+{numero_jid.split('@')[0]}"
        barberos      = obtener_barberos()
        respuesta     = manejar_mensaje(numero_sesion, mensaje, barberos)

        print(f"[DEBUG] Respuesta: {respuesta}")
        enviar_respuesta(numero_jid, respuesta)

        return jsonify({"status": "ok"}), 200

    except Exception as e:
        print(f"[ERROR] En webhook: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500
