from twilio.rest import Client
import os


# ------------------------------------------------
# CONFIGURACION TWILIO
# ------------------------------------------------

ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP = os.getenv("TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886")
HERMES_PHONE = os.getenv("HERMES_PHONE")

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

def notificar_barbero(nombre_cliente, fecha, hora, servicio=None, barbero_nombre=None, accion="nueva"):
    if not HERMES_PHONE:
        return
    try:
        if accion == "nueva":
            svc = f"\n✂️ {servicio}" if servicio else ""
            barb = f"\n💈 {barbero_nombre}" if barbero_nombre else ""
            msg = f"💈 *Nueva cita agendada*\n\n👤 {nombre_cliente}\n📅 {fecha}\n⏰ {hora}{svc}{barb}"
        else:
            msg = f"❌ *Cita cancelada*\n\n👤 {nombre_cliente}\n📅 {fecha}\n⏰ {hora}"
        client.messages.create(
            from_=TWILIO_WHATSAPP,
            body=msg,
            to=f"whatsapp:{HERMES_PHONE}"
        )
    except Exception as e:
        print("⚠ Error notificando barbero:", e)


def enviar_recordatorio_fijo(telefono, nombre, horario):
    try:
        if not telefono:
            return False
        mensaje = (
            f"💈 *BarberIA*\n\n"
            f"Hola {nombre} 👋\n\n"
            f"Te recordamos que esta semana tienes tu cita habitual:\n\n"
            f"⏰ *{horario}*\n\n"
            f"Si necesitas cambiarla escribe *cambiar cita*.\n\n"
            f"¡Te esperamos!"
        )
        client.messages.create(
            from_=TWILIO_WHATSAPP,
            body=mensaje,
            to=f"whatsapp:{telefono}"
        )
        return True
    except Exception as e:
        print("⚠ Error enviando recordatorio fijo:", e)
        return False


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