import dateparser
import re
import unicodedata
from rapidfuzz import process
from datetime import datetime, timedelta


# ────────────────────────────────────────────────────────────────────────────────
# NORMALIZAR TEXTO
# ────────────────────────────────────────────────────────────────────────────────

_REEMPLAZOS = {
    # typos de mañana
    "mañna":    "mañana",
    "manana":   "mañana",
    "mañna":    "mañana",
    "maana":    "mañana",
    "mananana": "mañana",
    # verbos sinónimos → forma canónica
    "reservar":    "agendar",
    "solicitar":   "agendar",
    "pedir":       "agendar",
    "separar":     "agendar",
    "apartar":     "agendar",
    "sacar":       "agendar",
    "coger":       "agendar",
    "anular":      "cancelar",
    "eliminar":    "cancelar",
    "borrar":      "cancelar",
    "quitar":      "cancelar",
    "dejar":       "cancelar",
    # sustantivos sinónimos
    "turnos":      "turno",
    "citas":       "cita",
    "corte de pelo":  "corte",
    "corte de cabello": "corte",
    "pelo":        "corte",
    "cabello":     "corte",
    "peluqueria":  "barberia",
    # reagendar
    "mover cita":   "reagendar",
    "cambiar cita": "reagendar",
    "cambiar turno": "reagendar",
    "cambiar hora": "reagendar",
    "otro dia":     "reagendar",
    "otra fecha":   "reagendar",
    "reprogramar":  "reagendar",
    "reschedulear": "reagendar",
    # precios
    "cuanto vale":   "precio",
    "cuanto cuesta": "precio",
    "cuánto vale":   "precio",
    "cuánto cuesta": "precio",
    "cuánto cobran": "precio",
    "cuanto cobran": "precio",
    "valor del servicio": "precio",
    "tarifas":       "precio",
    # ver cita
    "tengo cita":   "mi cita",
    "tengo turno":  "mi cita",
    "ver turno":    "mi cita",
    "mi turno":     "mi cita",
    "cuando es mi": "mi cita",
    # disponibilidad → horarios
    "disponibilidad": "horario",
    "disponible":     "horario",
    "hay espacio":    "horario",
    "hay turno":      "horario",
    "hay cupo":       "horario",
    "hay lugar":      "horario",
    # afirmaciones comunes
    "de acuerdo":  "si",
    "por supuesto": "si",
    "claro que si": "si",
    "claro que sí": "si",
    "esta bien":   "si",
    "está bien":   "si",
}


def limpiar_texto(texto):
    texto = texto.lower().strip()
    # Aplicar reemplazos (del más largo al más corto para evitar overlaps)
    for k in sorted(_REEMPLAZOS, key=len, reverse=True):
        if k in texto:
            texto = texto.replace(k, _REEMPLAZOS[k])
    return texto


# ────────────────────────────────────────────────────────────────────────────────
# DETECTAR ACCIÓN
# ────────────────────────────────────────────────────────────────────────────────

# Orden importante: las más específicas primero para evitar falsos positivos

_PATRONES_REAGENDAR = [
    "reagendar", "reprogramar", "reschedulear",
    "mover cita", "cambiar cita", "cambiar turno",
    "cambiar hora", "otro dia", "otra fecha",
]

_PATRONES_CANCELAR = [
    "cancelar", "anular", "eliminar", "borrar",
]

_PATRONES_VER_CITA = [
    "mi cita", "ver cita", "ver turno", "mi turno",
    "tengo cita", "tengo turno", "cuando es", "a que hora es",
    "cuándo es", "cuándo tengo",
]

_PATRONES_PRECIOS = [
    "precio", "precios", "tarifa", "costo",
    "cuanto vale", "cuánto vale", "cuanto cuesta", "cuánto cuesta",
    "cuanto cobran", "cuánto cobran", "valor",
]

_PATRONES_AGENDAR = [
    "agendar", "reservar", "separar", "sacar",
    "cita", "turno", "corte", "arreglo", "fade",
    "quiero un", "quiero una", "necesito un", "necesito una",
    "me puedes", "me pueden", "puedo agendar", "puedo pedir",
    "quiero ir",
]

_PATRONES_BARBEROS = [
    "barbero", "barberos", "quién atiende", "quien atiende",
    "quienes son", "quiénes son", "los chicos",
]

_PATRONES_HORARIOS = [
    "horario", "horarios", "hora libre", "horas libres",
    "disponibilidad", "disponible", "hay espacio",
    "cuando trabajan", "cuándo trabajan", "cuando abren",
    "a que hora abren", "cuales son los horarios",
]

_PATRONES_AYUDA = [
    "ayuda", "help", "no entiendo", "como funciona",
    "cómo funciona", "que puedo hacer", "qué puedo hacer",
    "opciones", "menu", "menú",
]


def detectar_accion(texto):
    t = texto  # ya viene limpio y sin tildes en minúsculas

    # 1. Reagendar (debe ir antes que cancelar y agendar)
    if any(p in t for p in _PATRONES_REAGENDAR):
        return "reagendar"

    # 2. Cancelar (antes que agendar, evita "cancelar mi cita" → "agendar")
    if any(p in t for p in _PATRONES_CANCELAR):
        return "cancelar"

    # 3. Ver cita (antes que agendar, evita "ver mi cita" → "agendar")
    if any(p in t for p in _PATRONES_VER_CITA):
        return "ver_cita"

    # 4. Precios
    if any(p in t for p in _PATRONES_PRECIOS):
        return "precios"

    # 5. Agendar
    if any(p in t for p in _PATRONES_AGENDAR):
        return "agendar"

    # 6. Barberos
    if any(p in t for p in _PATRONES_BARBEROS):
        return "barberos"

    # 7. Horarios
    if any(p in t for p in _PATRONES_HORARIOS):
        return "horarios"

    # 8. Ayuda
    if any(p in t for p in _PATRONES_AYUDA):
        return "ayuda"

    return None


# ────────────────────────────────────────────────────────────────────────────────
# DETECTAR HORA
# ────────────────────────────────────────────────────────────────────────────────

def detectar_hora(texto):
    t = texto.lower()

    # formato HH:MM
    m = re.search(r'\b([01]?\d|2[0-3]):[0-5]\d\b', t)
    if m:
        return m.group()

    # formato "3 pm", "10am", "3:00pm"
    m = re.search(r'\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b', t)
    if m:
        h   = int(m.group(1))
        min_ = int(m.group(2)) if m.group(2) else 0
        ap  = m.group(3)
        if ap == "pm" and h != 12:
            h += 12
        elif ap == "am" and h == 12:
            h = 0
        return f"{h:02d}:{min_:02d}"

    # "a las N" / "las N"
    m = re.search(r'\ba\s+las?\s+(\d{1,2})\b', t)
    if m:
        h = int(m.group(1))
        if 1 <= h <= 8:
            h += 12   # asumir PM si es rango de tarde
        return f"{h:02d}:00"

    # "en la mañana" / "en la tarde" → no retorna hora concreta, se deja al flujo
    return None


# ────────────────────────────────────────────────────────────────────────────────
# DETECTAR BARBERO
# ────────────────────────────────────────────────────────────────────────────────

def detectar_barbero(texto, barberos):
    if not barberos:
        return None

    nombres = [b["nombre"].lower() for b in barberos]
    match = process.extractOne(texto, nombres)

    if match and match[1] > 60:
        return match[0]

    return None


# ────────────────────────────────────────────────────────────────────────────────
# DETECTAR SERVICIO POR NOMBRE (fuzzy)
# ────────────────────────────────────────────────────────────────────────────────

def detectar_servicio_por_nombre(texto, servicios_dict):
    """
    servicios_dict = {id: {"nombre": ..., "precio": ...}}
    Retorna el id del servicio o None.
    """
    if not servicios_dict:
        return None

    nombres = {str(k): v["nombre"].lower() for k, v in servicios_dict.items()}
    candidatos = list(nombres.values())
    match = process.extractOne(texto.lower(), candidatos)

    if match and match[1] > 55:
        nombre_match = match[0]
        for k, v in nombres.items():
            if v == nombre_match:
                return int(k)
    return None


# ────────────────────────────────────────────────────────────────────────────────
# UTILIDADES FECHA — Colombia UTC-5
# ────────────────────────────────────────────────────────────────────────────────

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


# ────────────────────────────────────────────────────────────────────────────────
# DETECTAR FECHA
# ────────────────────────────────────────────────────────────────────────────────

def detectar_fecha(texto):
    """
    Detecta una fecha en el texto.
    Para nombres de días usa aritmética Python pura para evitar errores de timezone.
    """
    t = _sin_tildes_nlp(texto.strip().lower())
    es_proximo = "proximo" in t or "siguiente" in t or "proxima" in t

    # 1. Nombre de día en español → parser propio
    for nombre, num in _DIAS_NLP.items():
        if nombre in t:
            hoy = _colombia_now_nlp()
            dias_diff = (num - hoy.weekday()) % 7
            # "lunes" cuando hoy ES lunes → próximo lunes
            if dias_diff == 0:
                dias_diff = 7
            if es_proximo:
                # "próximo lunes" = el lunes de la semana que viene (no el más cercano)
                if dias_diff < 7:
                    dias_diff += 7
            target = hoy + timedelta(days=dias_diff)
            return target.strftime("%Y-%m-%d")

    # 2. Palabras clave simples
    hoy = _colombia_now_nlp()
    if t in ("hoy",) or t.startswith("hoy "):
        return hoy.strftime("%Y-%m-%d")
    if "hoy" in t and len(t) <= 8:
        return hoy.strftime("%Y-%m-%d")
    if "manana" in t or "mañana" in t:
        if "pasado" in t:
            return (hoy + timedelta(days=2)).strftime("%Y-%m-%d")
        return (hoy + timedelta(days=1)).strftime("%Y-%m-%d")
    if "pasado manana" in t or "pasado mañana" in t:
        return (hoy + timedelta(days=2)).strftime("%Y-%m-%d")
    if "esta semana" in t:
        return (hoy + timedelta(days=1)).strftime("%Y-%m-%d")

    # 3. Fecha con formato numérico directo (2026-04-20, 20/04, 20 de abril)
    m = re.search(r'\b(\d{4})-(\d{2})-(\d{2})\b', t)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"

    m = re.search(r'\b(\d{1,2})[/\-](\d{1,2})(?:[/\-](\d{2,4}))?\b', t)
    if m:
        dia  = int(m.group(1))
        mes  = int(m.group(2))
        anio = int(m.group(3)) if m.group(3) else hoy.year
        if anio < 100:
            anio += 2000
        if 1 <= dia <= 31 and 1 <= mes <= 12:
            return f"{anio:04d}-{mes:02d}-{dia:02d}"

    # 4. Fallback: dateparser solo para fechas absolutas ("15 de abril")
    try:
        fecha = dateparser.parse(
            texto,
            languages=["es"],
            settings={"PREFER_DATES_FROM": "future", "RETURN_AS_TIMEZONE_AWARE": False}
        )
        if fecha:
            return fecha.strftime("%Y-%m-%d")
    except Exception:
        pass

    return None


# ────────────────────────────────────────────────────────────────────────────────
# INTERPRETAR MENSAJE
# ────────────────────────────────────────────────────────────────────────────────

def interpretar_mensaje(texto, barberos):
    texto = limpiar_texto(texto)

    accion  = detectar_accion(texto)
    fecha   = detectar_fecha(texto)
    hora    = detectar_hora(texto)
    barbero = detectar_barbero(texto, barberos)

    return {
        "accion":  accion,
        "fecha":   fecha,
        "hora":    hora,
        "barbero": barbero,
    }
