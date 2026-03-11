from flask import Blueprint, request
from twilio.twiml.messaging_response import MessagingResponse
import requests

from app.services.nlp_service import interpretar_mensaje

bot_bp = Blueprint("bot", __name__)

API_URL = "http://localhost:5000"

# estado conversacional
user_states = {}


@bot_bp.route("/bot", methods=["POST"])
def bot():

    telefono = request.form.get("From")
    mensaje = request.form.get("Body").strip().lower()

    resp = MessagingResponse()

    # obtener barberos
    r = requests.get(f"{API_URL}/barberos/")
    barberos = r.json()["barberos"]

    # interpretar mensaje con NLP
    nlp = interpretar_mensaje(mensaje, barberos)

    accion = nlp["accion"]
    fecha = nlp["fecha"]
    hora = nlp["hora"]
    barbero = nlp["barbero"]

    estado = user_states.get(telefono, "inicio")

    print("MENSAJE:", mensaje)
    print("ACCION:", accion)
    print("FECHA:", fecha)
    print("HORA:", hora)
    print("BARBERO:", barbero)

    # -------------------------
    # SALUDO
    # -------------------------

    if mensaje in ["hola", "menu", "hi"]:

        resp.message(
            "Hola 👋 soy *BarberIA* 💈\n\n"
            "Puedes escribir:\n\n"
            "• quiero una cita\n"
            "• ver barberos\n"
            "• horarios mañana\n"
            "• cancelar cita"
        )

        user_states[telefono] = "inicio"

        return str(resp)

    # -------------------------
    # AGENDAR DIRECTO (IA)
    # -------------------------

    if accion == "agendar" and fecha and hora and barbero:

        barbero_id = next(
            (b["id"] for b in barberos if b["nombre"].lower() == barbero),
            None
        )

        requests.post(
            f"{API_URL}/agenda/crear-cita",
            json={
                "nombre": "Cliente",
                "telefono": telefono.replace("whatsapp:", ""),
                "barbero_id": barbero_id,
                "fecha": fecha,
                "hora": hora
            }
        )

        resp.message(
            f"✅ Cita agendada\n\n"
            f"📅 {fecha}\n"
            f"⏰ {hora}\n"
            f"💈 {barbero.title()}"
        )

        return str(resp)

    # -------------------------
    # INICIAR AGENDAMIENTO
    # -------------------------

    if accion == "agendar":

        texto = "Perfecto 💈 Vamos a agendar tu cita.\n\n"

        texto += "¿Con qué barbero?\n\n"

        for b in barberos:
            texto += f"{b['id']}️⃣ {b['nombre']}\n"

        user_states[telefono] = "esperando_barbero"

        resp.message(texto)

        return str(resp)

    # -------------------------
    # VER BARBEROS
    # -------------------------

    if accion == "barberos":

        texto = "💈 Nuestros barberos:\n\n"

        for b in barberos:
            texto += f"{b['id']}️⃣ {b['nombre']}\n"

        resp.message(texto)

        return str(resp)

    # -------------------------
    # SELECCIONAR BARBERO
    # -------------------------

    if estado == "esperando_barbero":

        barbero_id = mensaje

        user_states[telefono] = {
            "estado": "esperando_fecha",
            "barbero_id": barbero_id
        }

        resp.message(
            "Perfecto 👍\n\n"
            "¿Para qué fecha quieres la cita?\n"
            "Ejemplo: mañana o 2026-03-10"
        )

        return str(resp)

    # -------------------------
    # SELECCIONAR FECHA
    # -------------------------

    if isinstance(estado, dict) and estado.get("estado") == "esperando_fecha":

        barbero_id = estado["barbero_id"]

        fecha_final = fecha if fecha else mensaje

        r = requests.get(
            f"{API_URL}/agenda/horarios",
            params={
                "barbero_id": barbero_id,
                "fecha": fecha_final
            }
        )

        data = r.json()

        horarios = data["horarios"] if isinstance(data, dict) else data

        texto = "⏰ Horarios disponibles:\n\n"

        for i, h in enumerate(horarios):
            texto += f"{i+1}️⃣ {h}\n"

        texto += "\nEscribe el número del horario."

        user_states[telefono] = {
            "estado": "esperando_hora",
            "barbero_id": barbero_id,
            "fecha": fecha_final,
            "horarios": horarios
        }

        resp.message(texto)

        return str(resp)

    # -------------------------
    # SELECCIONAR HORA
    # -------------------------

    if isinstance(estado, dict) and estado.get("estado") == "esperando_hora":

        try:

            index = int(mensaje) - 1
            hora = estado["horarios"][index]

            barbero_id = estado["barbero_id"]
            fecha = estado["fecha"]

            user_states[telefono] = {
                "estado": "esperando_nombre",
                "barbero_id": barbero_id,
                "fecha": fecha,
                "hora": hora
            }

            resp.message("Escribe tu nombre para confirmar la cita.")

        except:

            resp.message("Por favor escribe un número válido.")

        return str(resp)

    # -------------------------
    # CONFIRMAR CITA
    # -------------------------

    if isinstance(estado, dict) and estado.get("estado") == "esperando_nombre":

        nombre = mensaje

        barbero_id = estado["barbero_id"]
        fecha = estado["fecha"]
        hora = estado["hora"]

        requests.post(
            f"{API_URL}/agenda/crear-cita",
            json={
                "nombre": nombre,
                "telefono": telefono.replace("whatsapp:", ""),
                "barbero_id": barbero_id,
                "fecha": fecha,
                "hora": hora
            }
        )

        user_states[telefono] = "inicio"

        resp.message(
            f"✅ Cita confirmada\n\n"
            f"📅 {fecha}\n"
            f"⏰ {hora}\n\n"
            "Gracias por usar BarberIA 💈"
        )

        return str(resp)

    # -------------------------
    # CANCELAR
    # -------------------------

    if accion == "cancelar":

        resp.message(
            "Para cancelar una cita escribe:\n\n"
            "cancelar 2026-03-10 15:00"
        )

        return str(resp)

    # -------------------------
    # DEFAULT
    # -------------------------

    resp.message(
        "No entendí tu mensaje 🤔\n\n"
        "Puedes decir:\n"
        "• hola\n"
        "• quiero una cita\n"
        "• ver barberos\n"
        "• cancelar cita"
    )

    return str(resp)
    