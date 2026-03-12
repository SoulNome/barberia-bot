from twilio.rest import Client
import os


# ------------------------------------------------
# CONFIGURACION TWILIO
# ------------------------------------------------

ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP = "whatsapp:+14155238886"

if not ACCOUNT_SID or not AUTH_TOKEN:
    raise Exception("Twilio credentials no configuradas")

client = Client(ACCOUNT_SID, AUTH_TOKEN)


# ------------------------------------------------
# MENSAJE RECORDATORIO
# ------------------------------------------------

def construir_mensaje(nombre, fecha, hora):

    return f"""
💈 *BarberIA*

Hola {nombre} 👋

Te recordamos tu cita:

📅 Fecha: {fecha}
⏰ Hora: {hora}

Por favor llega 5 minutos antes.

Si necesitas cancelar escribe:

cancelar

¡Te esperamos!
"""


# ------------------------------------------------
# ENVIAR RECORDATORIO INDIVIDUAL
# ------------------------------------------------

def enviar_recordatorio(telefono, nombre, fecha, hora):

    try:

        if not telefono:
            return False

        mensaje = construir_mensaje(nombre, fecha, hora)

        client.messages.create(
            from_=TWILIO_WHATSAPP,
            body=mensaje,
            to=f"whatsapp:{telefono}"
        )

        return True

    except Exception as e:

        print("⚠ Error enviando recordatorio:", e)

        return False


# ------------------------------------------------
# ENVIAR RECORDATORIOS MASIVOS
# ------------------------------------------------

def enviar_recordatorios(lista_citas):

    enviados = 0

    for cita in lista_citas:

        telefono = cita.get("telefono")
        nombre = cita.get("nombre")
        fecha = cita.get("fecha")
        hora = cita.get("hora")

        ok = enviar_recordatorio(
            telefono,
            nombre,
            fecha,
            hora
        )

        if ok:
            enviados += 1

    print(f"📲 Recordatorios enviados: {enviados}")