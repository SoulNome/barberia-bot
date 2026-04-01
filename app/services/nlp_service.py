import dateparser
import re
import unicodedata
from rapidfuzz import process
from datetime import datetime, timedelta


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
# UTILIDADES FECHA — Colombia UTC-5
# ------------------------------------------------

def _sin_tildes_nlp(s):
    return ''.join(
        c for c in unicodedata.normalize('NFD', s)
        if unicodedata.category(c) != 'Mn'
    )

_DIAS_NLP = {
    "lunes": 0, "martes": 1, "miercoles": 2,
    "jueves": 3, "viernes": 4, "sabado": 5, "domingo": 6
}

def _colombia_now_nlp():
    return datetime.utcnow() - timedelta(hours=5)


# ------------------------------------------------
# DETECTAR FECHA
# ------------------------------------------------

def detectar_fecha(texto):
    """
    Detecta una fecha en el texto.
    Para nombres de días usa aritmética Python pura (no dateparser)
    para evitar errores de timezone/locale del servidor.
    """
    t = _sin_tildes_nlp(texto.strip().lower())
    es_proximo = "proximo" in t or "siguiente" in t

    # 1. Nombre de día en español → parser propio
    for nombre, num in _DIAS_NLP.items():
        if nombre in t:
            hoy = _colombia_now_nlp()
            dias_diff = (num - hoy.weekday()) % 7
            if es_proximo and dias_diff == 0:
                dias_diff = 7
            target = hoy + timedelta(days=dias_diff)
            return target.strftime("%Y-%m-%d")

    # 2. Palabras clave simples
    hoy = _colombia_now_nlp()
    if "hoy" in t:
        return hoy.strftime("%Y-%m-%d")
    if "manana" in t or "mañana" in t:
        return (hoy + timedelta(days=1)).strftime("%Y-%m-%d")
    if "pasado" in t and ("manana" in t or "mañana" in t):
        return (hoy + timedelta(days=2)).strftime("%Y-%m-%d")

    # 3. Fallback: dateparser solo para fechas absolutas ("15 de abril", "2026-04-15")
    fecha = dateparser.parse(
        texto,
        languages=["es"],
        settings={"PREFER_DATES_FROM": "future"}
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