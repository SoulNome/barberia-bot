import os
import random
import time
import requests


def _ampm(hora_str: str) -> str:
    """Convierte '14:30' → '2:30 PM' para mensajes WhatsApp."""
    try:
        h, m = map(int, hora_str.split(":"))
        periodo = "AM" if h < 12 else "PM"
        h12 = h % 12 or 12
        return f"{h12}:{m:02d} {periodo}"
    except Exception:
        return hora_str

# Credenciales globales (fallback para barbería por defecto)
_DEFAULT_EVO_URL      = os.getenv("EVOLUTION_API_URL", "")
_DEFAULT_EVO_KEY      = os.getenv("EVOLUTION_API_KEY", "")
_DEFAULT_EVO_INSTANCE = os.getenv("EVOLUTION_INSTANCE", "")
_DEFAULT_HERMES_PHONE = os.getenv("HERMES_PHONE", "")


def _enviar_whatsapp(numero, texto, barberia=None):
    """
    Envía un mensaje via Evolution API.
    Si se pasa un objeto Barberia, usa sus credenciales; si no, usa las env vars globales.
    """
    if barberia:
        api_url  = barberia.evolution_api_url  or _DEFAULT_EVO_URL
        api_key  = barberia.evolution_api_key  or _DEFAULT_EVO_KEY
        instance = barberia.evolution_instance or _DEFAULT_EVO_INSTANCE
    else:
        api_url  = _DEFAULT_EVO_URL
        api_key  = _DEFAULT_EVO_KEY
        instance = _DEFAULT_EVO_INSTANCE

    if not api_url or not instance:
        print("⚠ Evolution API no configurada, no se envió mensaje")
        return False

    url     = f"{api_url}/message/sendText/{instance}"
    headers = {"apikey": api_key, "Content-Type": "application/json"}
    # "delay" (ms): Evolution v2 muestra "escribiendo…" ese tiempo antes de
    # entregar — los envíos instantáneos en ráfaga son señal de bot para WhatsApp.
    payload = {"number": numero, "text": texto, "delay": random.randint(1500, 3000)}

    try:
        r = requests.post(url, json=payload, headers=headers, timeout=15)
        r.raise_for_status()
        return True
    except Exception as e:
        print(f"⚠ Error enviando mensaje a {numero}: {e}")
        return False


def pausa_anti_ban(min_s=8, max_s=20):
    """Pausa aleatoria entre mensajes de envíos masivos. WhatsApp bloquea
    números que despachan decenas de mensajes en el mismo segundo."""
    time.sleep(random.uniform(min_s, max_s))


def construir_mensaje(nombre, fecha, hora):
    return (
        f"💈 *Recordatorio de cita*\n\n"
        f"Hola {nombre} 👋\n\n"
        f"Te recordamos tu cita para *mañana*:\n\n"
        f"📅 Fecha: {fecha}\n"
        f"⏰ Hora: {_ampm(hora)}\n\n"
        f"Por favor llega 5 minutos antes 🙏\n\n"
        f"⚠️ *Importante:* Si no puedes asistir cancela antes de las 8:00 PM de hoy escribiendo *cancelar*.\n"
        f"Las inasistencias sin aviso generan una *multa* en tu próxima visita.\n\n"
        f"¡Te esperamos!"
    )


def enviar_recordatorio(telefono, nombre, fecha, hora, barberia=None):
    if not telefono:
        return False
    mensaje = construir_mensaje(nombre, fecha, hora)
    return _enviar_whatsapp(telefono, mensaje, barberia)


def notificar_barbero(nombre_cliente, fecha, hora, servicio=None, barbero_nombre=None,
                      accion="nueva", barberia=None):
    # Número del barbero: primero del objeto barbería, luego env var global
    phone = (barberia.whatsapp_barbero if barberia else None) or _DEFAULT_HERMES_PHONE
    if not phone:
        return
    if accion == "nueva":
        svc  = f"\n✂️ {servicio}"      if servicio       else ""
        barb = f"\n💈 {barbero_nombre}" if barbero_nombre else ""
        msg  = f"💈 *Nueva cita agendada*\n\n👤 {nombre_cliente}\n📅 {fecha}\n⏰ {_ampm(hora)}{svc}{barb}"
    else:
        msg = f"❌ *Cita cancelada*\n\n👤 {nombre_cliente}\n📅 {fecha}\n⏰ {_ampm(hora)}"
    _enviar_whatsapp(phone, msg, barberia)


def enviar_recordatorio_fijo(telefono, nombre, horario, barberia=None):
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
    return _enviar_whatsapp(telefono, mensaje, barberia)


def enviar_recordatorios(lista_citas, barberia=None):
    enviados = 0
    for cita in lista_citas:
        if enviados:
            pausa_anti_ban()
        ok = enviar_recordatorio(
            cita.get("telefono"),
            cita.get("nombre"),
            cita.get("fecha"),
            cita.get("hora"),
            barberia,
        )
        if ok:
            enviados += 1
    print(f"📲 Recordatorios enviados: {enviados}")
