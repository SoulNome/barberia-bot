from twilio.rest import Client
import os


# ------------------------------------------------
# CONFIGURACION TWILIO
# ------------------------------------------------

ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP = "whatsapp:+14155238886"

client = Client(ACCOUNT_SID, AUTH_TOKEN)


# ------------------------------------------------
# ENVIAR RECORDATORIO INDIVIDUAL
# ------------------------------------------------

def enviar_recordatorio(telefono, nombre, fecha, hora):

    try:

        mensaje = f"""
Hola {nombre} 👋

Te recordamos tu cita en BarberIA 💈

📅 {fecha}
⏰ {hora}

¡Te esperamos!
"""

        client.messages.create(
            from_=TWILIO_WHATSAPP,
            body=mensaje,
            to=f"whatsapp:{telefono}"
        )

        return True

    except Exception as e:

        print("Error enviando recordatorio:", e)

        return False


# ------------------------------------------------
# ENVIAR RECORDATORIOS MASIVOS
# ------------------------------------------------

def enviar_recordatorios(lista_citas):

    enviados = 0

    for cita in lista_citas:

        telefono = cita["telefono"]
        nombre = cita["nombre"]
        fecha = cita["fecha"]
        hora = cita["hora"]

        ok = enviar_recordatorio(telefono, nombre, fecha, hora)

        if ok:
            enviados += 1

    print(f"Recordatorios enviados: {enviados}")