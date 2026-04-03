import os
import requests

EVOLUTION_API_URL      = os.getenv("EVOLUTION_API_URL", "")
EVOLUTION_API_KEY      = os.getenv("EVOLUTION_API_KEY", "")
EVOLUTION_INSTANCE     = os.getenv("EVOLUTION_INSTANCE", "")
HERMES_PHONE           = os.getenv("HERMES_PHONE", "")


def _enviar_whatsapp(numero, texto):
    """Envía un mensaje via Evolution API."""
    if not EVOLUTION_API_URL or not EVOLUTION_INSTANCE:
        print("⚠ Evolution API no configurada, no se envió mensaje")
        return False
    url = f"{EVOLUTION_API_URL}/message/sendText/{EVOLUTION_INSTANCE}"
    headers = {"apikey": EVOLUTION_API_KEY, "Content-Type": "application/json"}
    payload = {"number": numero, "text": texto}
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=10)
        r.raise_for_status()
        return True
    except Exception as e:
        print(f"⚠ Error enviando mensaje a {numero}: {e}")
        return False


# ------------------------------------------------
# MENSAJE RECORDATORIO
# ------------------------------------------------

def construir_mensaje(nombre, fecha, hora):
    return (
        f"💈 *BarberIA*\n\n"
        f"Hola {nombre} 👋\n\n"
        f"Te recordamos tu cita:\n\n"
        f"📅 Fecha: {fecha}\n"
        f"⏰ Hora: {hora}\n\n"
        f"Por favor llega 5 minutos antes.\n\n"
        f"Si necesitas cancelar escribe:\n\ncancelar\n\n"
        f"¡Te esperamos!"
    )


# ------------------------------------------------
# ENVIAR RECORDATORIO INDIVIDUAL
# ------------------------------------------------

def enviar_recordatorio(telefono, nombre, fecha, hora):
    if not telefono:
        return False
    mensaje = construir_mensaje(nombre, fecha, hora)
    return _enviar_whatsapp(telefono, mensaje)


# ------------------------------------------------
# NOTIFICAR AL BARBERO
# ------------------------------------------------

def notificar_barbero(nombre_cliente, fecha, hora, servicio=None, barbero_nombre=None, accion="nueva"):
    if not HERMES_PHONE:
        return
    if accion == "nueva":
        svc  = f"\n✂️ {servicio}"      if servicio       else ""
        barb = f"\n💈 {barbero_nombre}" if barbero_nombre else ""
        msg  = f"💈 *Nueva cita agendada*\n\n👤 {nombre_cliente}\n📅 {fecha}\n⏰ {hora}{svc}{barb}"
    else:
        msg = f"❌ *Cita cancelada*\n\n👤 {nombre_cliente}\n📅 {fecha}\n⏰ {hora}"
    _enviar_whatsapp(HERMES_PHONE, msg)


# ------------------------------------------------
# RECORDATORIO FIJO (SEMANAL)
# ------------------------------------------------

def enviar_recordatorio_fijo(telefono, nombre, horario):
    if not telefono:
        return False
    mensaje = (
        f"💈 *BarberIA*\n\n"
        f"Hola {nombre} 👋\n\n"
        f"Te recordamos que esta semana tienes tu cita habitual:\n\n"
        f"⏰ *{horario}*\n\n"
        f"Si necesitas cambiarla escribe *reagendar*.\n\n"
        f"¡Te esperamos!"
    )
    return _enviar_whatsapp(telefono, mensaje)


# ------------------------------------------------
# ENVIAR RECORDATORIOS MASIVOS
# ------------------------------------------------

def enviar_recordatorios(lista_citas):
    enviados = 0
    for cita in lista_citas:
        ok = enviar_recordatorio(
            cita.get("telefono"),
            cita.get("nombre"),
            cita.get("fecha"),
            cita.get("hora"),
        )
        if ok:
            enviados += 1
    print(f"📲 Recordatorios enviados: {enviados}")
