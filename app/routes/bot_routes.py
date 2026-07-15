import os
import json
import random
import requests
from flask import Blueprint, request, jsonify

from app.extensions import db
from app.models.contact_map import ContactMap
from app.models.barberia import Barberia
from app.services.conversation_service import manejar_mensaje
from app.services.barbero_service import obtener_barberos

bot_bp = Blueprint("bot", __name__)

# Credenciales globales (fallback para /bot sin slug — cliente activo)
_DEFAULT_EVO_URL  = os.getenv("EVOLUTION_API_URL", "").strip()
_DEFAULT_EVO_KEY  = os.getenv("EVOLUTION_API_KEY", "").strip()
_DEFAULT_EVO_INST = os.getenv("EVOLUTION_INSTANCE", "").strip()

# ID de barbería por defecto (barbería 1, el cliente activo)
_DEFAULT_BARBERIA_ID = None  # se resuelve lazy la primera vez


def _get_default_barberia_id():
    global _DEFAULT_BARBERIA_ID
    if _DEFAULT_BARBERIA_ID is None:
        b = Barberia.query.order_by(Barberia.id).first()
        _DEFAULT_BARBERIA_ID = b.id if b else 1
    return _DEFAULT_BARBERIA_ID


def guardar_contacto(lid, phone, push_name=""):
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
    except Exception as e:
        print(f"[CONTACT] Error guardando contacto: {e}")
        db.session.rollback()


def resolver_numero(jid):
    if "@lid" not in jid:
        return jid
    lid_clean = jid.replace("@lid", "")
    mapping   = ContactMap.query.filter_by(lid=lid_clean).first()
    if mapping:
        print(f"[CONTACT] @lid resuelto: {jid} → {mapping.phone}")
        return mapping.phone
    print(f"[CONTACT] @lid sin mapeo aún: {jid}")
    return jid


def _enviar_respuesta(jid, texto, evo_url, evo_key, evo_inst):
    numero  = resolver_numero(jid)
    url     = f"{evo_url}/message/sendText/{evo_inst}"
    headers = {"apikey": evo_key, "Content-Type": "application/json"}
    # "delay" (ms): Evolution v2 muestra "escribiendo…" antes de entregar;
    # responder en el mismo instante en que llega el mensaje delata al bot.
    payload = {"number": numero, "text": texto, "delay": random.randint(1200, 2500)}
    print(f"[DEBUG] Enviando a: {numero}")
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=15)
        print(f"[DEBUG] Evolution respondió: {r.status_code} {r.text[:200]}")
    except Exception as e:
        print(f"[ERROR] No se pudo enviar mensaje: {e}")


def procesar_contacts_upsert(data):
    contacts = data.get("data", [])
    if not isinstance(contacts, list):
        contacts = [contacts]
    for c in contacts:
        jid   = c.get("id", "")
        phone = c.get("notify") or c.get("verifiedName") or c.get("name") or ""
        if "@s.whatsapp.net" in jid or "@c.us" in jid:
            phone_clean = jid.replace("@s.whatsapp.net", "").replace("@c.us", "")
            push_name   = c.get("name") or c.get("notify") or ""
            lid = c.get("lid") or c.get("lidJid") or ""
            if lid:
                guardar_contacto(lid, phone_clean, push_name)
        if "@lid" in jid and c.get("phone"):
            guardar_contacto(jid, c["phone"], c.get("name", ""))


def _procesar_webhook(data, barberia_id, evo_url, evo_key, evo_inst):
    """Lógica compartida de procesamiento de webhook independiente de la barbería."""
    event = data.get("event", "")

    if event == "contacts.upsert":
        print(f"[CONTACT] contacts.upsert data: {json.dumps(data, indent=2)}")
        procesar_contacts_upsert(data)
        return jsonify({"status": "ok"}), 200

    if event != "messages.upsert":
        return jsonify({"status": "ignored"}), 200

    print(f"\n[DEBUG] ===== MENSAJE RECIBIDO (barberia_id={barberia_id}) =====")
    print(f"[DEBUG] Raw data: {json.dumps(data, indent=2)}")
    print(f"[DEBUG] ==========================================================\n")

    numero_jid = None
    mensaje    = None

    if "data" in data:
        msg_data = data["data"]

        if msg_data.get("key", {}).get("fromMe"):
            return jsonify({"status": "ignored"}), 200

        push_name = msg_data.get("pushName", "")

        if "key" in msg_data:
            remote_jid = msg_data["key"].get("remoteJid", "")
            if "@g.us" in remote_jid or "@broadcast" in remote_jid:
                return jsonify({"status": "ignored"}), 200
            numero_jid = remote_jid
            if "@lid" in remote_jid and push_name:
                print(f"[CONTACT] Mensaje de @lid: {remote_jid} (pushName={push_name})")

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
        _enviar_respuesta(
            numero_jid,
            "Hola! Solo puedo leer mensajes de texto 😊 Por favor escríbeme tu consulta.",
            evo_url, evo_key, evo_inst
        )
        return jsonify({"status": "ok"}), 200

    numero_sesion = f"+{numero_jid.split('@')[0]}"
    barberos      = obtener_barberos(barberia_id)
    respuesta     = manejar_mensaje(numero_sesion, mensaje, barberos, barberia_id)

    print(f"[DEBUG] Respuesta: {respuesta}")
    _enviar_respuesta(numero_jid, respuesta, evo_url, evo_key, evo_inst)

    return jsonify({"status": "ok"}), 200


# ──────────────────────────────────────────────────────────────────────────────
# Ruta NUEVA: /bot/<slug>  — cada barbería apunta su webhook aquí
# ──────────────────────────────────────────────────────────────────────────────

@bot_bp.route("/bot/<slug>", methods=["POST"])
def bot_slug(slug):
    try:
        barberia = Barberia.query.filter_by(slug=slug).first()
        if not barberia:
            return jsonify({"status": "error", "message": f"Barbería '{slug}' no encontrada"}), 404

        # Si el bot está desactivado para esta barbería, ignorar el mensaje sin responder
        if getattr(barberia, 'bot_activo', True) is False:
            return jsonify({"status": "bot_inactivo"}), 200

        evo_url  = barberia.evolution_api_url  or _DEFAULT_EVO_URL
        evo_key  = barberia.evolution_api_key  or _DEFAULT_EVO_KEY
        evo_inst = barberia.evolution_instance or _DEFAULT_EVO_INST

        data = request.get_json(silent=True) or {}
        return _procesar_webhook(data, barberia.id, evo_url, evo_key, evo_inst)

    except Exception as e:
        print(f"[ERROR] En webhook /{slug}: {e}")
        import traceback; traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500


# ──────────────────────────────────────────────────────────────────────────────
# Ruta LEGADA: /bot  — mantiene compatibilidad con el cliente activo
# ──────────────────────────────────────────────────────────────────────────────

@bot_bp.route("/bot", methods=["POST"])
def bot():
    try:
        barberia_id = _get_default_barberia_id()
        data        = request.get_json(silent=True) or {}
        return _procesar_webhook(data, barberia_id, _DEFAULT_EVO_URL, _DEFAULT_EVO_KEY, _DEFAULT_EVO_INST)

    except Exception as e:
        print(f"[ERROR] En webhook /bot: {e}")
        import traceback; traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500
