import dateparser
import re
from rapidfuzz import process
from datetime import datetime


# ------------------------------------------------
# NORMALIZAR TEXTO
# ------------------------------------------------

def limpiar_texto(texto):

    texto = texto.lower().strip()

    reemplazos = {
        "mañna": "mañana",
        "manana": "mañana",
        "corte de pelo": "corte",
        "turnos": "turno",
        "reservar": "agendar"
    }

    for k, v in reemplazos.items():
        texto = texto.replace(k, v)

    return texto


# ------------------------------------------------
# DETECTAR ACCION
# ------------------------------------------------

def detectar_accion(texto):

    if any(p in texto for p in ["cita", "agendar", "reservar", "turno", "corte"]):
        return "agendar"

    if any(p in texto for p in ["cancelar", "eliminar", "quitar"]):
        return "cancelar"

    if any(p in texto for p in ["barbero", "barberos"]):
        return "barberos"

    if any(p in texto for p in ["horario", "hora", "horas"]):
        return "horarios"

    if any(p in texto for p in ["mi cita", "ver cita", "tengo cita"]):
        return "ver_cita"

    if any(p in texto for p in ["ayuda", "help"]):
        return "ayuda"

    return None


# ------------------------------------------------
# DETECTAR HORA
# ------------------------------------------------

def detectar_hora(texto):

    # formato 13:30
    match = re.search(r'([01]?\d|2[0-3]):[0-5]\d', texto)

    if match:
        return match.group()

    # formato 3pm
    match = re.search(r'\b(\d{1,2})\s*(am|pm)\b', texto)

    if match:

        hora = int(match.group(1))
        periodo = match.group(2)

        if periodo == "pm" and hora != 12:
            hora += 12

        if periodo == "am" and hora == 12:
            hora = 0

        return f"{hora:02d}:00"

    # formato solo numero (3)
    match = re.search(r'\b(\d{1,2})\b', texto)

    if match:

        hora = int(match.group(1))

        if 0 <= hora <= 23:
            return f"{hora:02d}:00"

    return None


# ------------------------------------------------
# DETECTAR BARBERO
# ------------------------------------------------

def detectar_barbero(texto, barberos):

    if not barberos:
        return None

    nombres = [b["nombre"].lower() for b in barberos]

    match = process.extractOne(texto, nombres)

    if match and match[1] > 65:
        return match[0]

    return None


# ------------------------------------------------
# DETECTAR FECHA
# ------------------------------------------------

def detectar_fecha(texto):

    fecha = dateparser.parse(
        texto,
        languages=["es"],
        settings={
            "PREFER_DATES_FROM": "future"
        }
    )

    if fecha:
        return fecha.strftime("%Y-%m-%d")

    return None


# ------------------------------------------------
# INTERPRETAR MENSAJE
# ------------------------------------------------

def interpretar_mensaje(texto, barberos):

    texto = limpiar_texto(texto)

    accion = detectar_accion(texto)

    fecha = detectar_fecha(texto)

    hora = detectar_hora(texto)

    barbero = detectar_barbero(texto, barberos)

    return {
        "accion": accion,
        "fecha": fecha,
        "hora": hora,
        "barbero": barbero
    }