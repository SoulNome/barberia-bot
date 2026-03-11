from twilio.rest import Client
from datetime import datetime, timedelta
import requests

ACCOUNT_SID = "TU_SID"
AUTH_TOKEN = "TU_TOKEN"

client = Client(ACCOUNT_SID, AUTH_TOKEN)


def enviar_recordatorio(telefono, nombre, fecha, hora):

    mensaje = f"""
Hola {nombre} 👋

Te recordamos tu cita mañana 💈

📅 {fecha}
⏰ {hora}

¡Te esperamos!
"""

    client.messages.create(
        from_='whatsapp:+14155238886',
        body=mensaje,
        to=f'whatsapp:{telefono}'
    )