import dateparser
import re
from rapidfuzz import process
from datetime import datetime


# ------------------------------------------------
# DETECTAR ACCION
# ------------------------------------------------

def detectar_accion(texto):

    texto = texto.lower()

    if any(p in texto for p in ["cita", "agendar", "reservar", "turno", "corte"]):
        return "agendar"

    if any(p in texto for p in ["cancelar", "eliminar"]):
        return "cancelar"

    if any(p in texto for p in ["barbero", "barberos"]):
        return "barberos"

    if any(p in texto for p in ["horario", "hora", "horas"]):
        return "horarios"

    if any(p in texto for p in ["mi cita", "ver cita", "tengo cita"]):
        return "ver_cita"

    return None


# ------------------------------------------------
# DETECTAR HORA
# ------------------------------------------------

def detectar_hora(texto):

    # formato 13:30
    match = re.search(r'([01]?\d|2[0-3]):[0-5]\d', texto)

    if match:
        return match.group()

    # formato 3pm / 4am
    match = re.search(r'\b(\d{1,2})(am|pm)\b', texto)

    if match:

        hora = int(match.group(1))
        periodo = match.group(2)

        if periodo == "pm" and hora != 12:
            hora += 12

        if periodo == "am" and hora == 12:
            hora = 0

        return f"{hora:02d}:00"

    return None


# ------------------------------------------------
# DETECTAR BARBERO
# ------------------------------------------------

def detectar_barbero(texto, barberos):

    nombres = [b["nombre"].lower() for b in barberos]

    match = process.extractOne(texto, nombres)

    if match and match[1] > 70:
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

    texto = texto.lower()

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