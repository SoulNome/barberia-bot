import dateparser
import re

def detectar_hora(texto):

    match = re.search(r'([01]?\d|2[0-3]):[0-5]\d', texto)

    if match:
        return match.group()

    match2 = re.search(r'\b(\d{1,2})\b', texto)

    if match2:
        return f"{match2.group()}:00"

    return None