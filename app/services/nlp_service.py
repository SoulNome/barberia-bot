import dateparser
import re
from rapidfuzz import process


def detectar_accion(texto):

    texto = texto.lower()

    if any(p in texto for p in [
        "cita",
        "agendar",
        "reservar",
        "turno",
        "corte"
    ]):
        return "agendar"

    if any(p in texto for p in [
        "cancelar",
        "cancel",
        "eliminar"
    ]):
        return "cancelar"

    if any(p in texto for p in [
        "barbero",
        "barberos"
    ]):
        return "barberos"

    if any(p in texto for p in [
        "horario",
        "horarios",
        "hora"
    ]):
        return "horarios"

    return None


def detectar_hora(texto):

    match = re.search(r'\b([01]?\d|2[0-3]):([0-5]\d)\b', texto)

    if match:
        return match.group()

    return None


def detectar_barbero(texto, barberos):

    nombres = [b["nombre"].lower() for b in barberos]

    match = process.extractOne(texto, nombres)

    if match and match[1] > 70:
        return match[0]

    return None


def interpretar_mensaje(texto, barberos):

    texto = texto.lower()

    accion = detectar_accion(texto)

    fecha = dateparser.parse(texto)

    hora = detectar_hora(texto)

    barbero = detectar_barbero(texto, barberos)

    return {
        "accion": accion,
        "fecha": fecha.strftime("%Y-%m-%d") if fecha else None,
        "hora": hora,
        "barbero": barbero
    }