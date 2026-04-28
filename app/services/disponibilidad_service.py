from datetime import datetime, time, timedelta
from app.models import Cita, Cliente
import dateparser
import re
import unicodedata


# ------------------------------------------------
# UTILIDADES DE FECHA — Colombia UTC-5
# ------------------------------------------------

def _colombia_now():
    return datetime.utcnow() - timedelta(hours=5)


def _sin_tildes(s):
    return ''.join(
        c for c in unicodedata.normalize('NFD', s)
        if unicodedata.category(c) != 'Mn'
    )


_DIAS_A_NUM = {
    "lunes": 0, "martes": 1, "miercoles": 2,
    "jueves": 3, "viernes": 4, "sabado": 5, "domingo": 6
}

_DIAS_NUM = {
    "lunes": 0, "martes": 1,
    "miércoles": 2, "miercoles": 2,
    "jueves": 3, "viernes": 4,
    "sábado": 5, "sabado": 5
}


def _dia_nombre_a_fecha(texto):
    t = _sin_tildes(texto.strip().lower())
    es_proximo = "proximo" in t or "siguiente" in t
    for nombre, num in _DIAS_A_NUM.items():
        if nombre in t:
            hoy = _colombia_now()
            dias_diff = (num - hoy.weekday()) % 7
            if es_proximo and dias_diff == 0:
                dias_diff = 7
            return hoy + timedelta(days=dias_diff)
    return None


def _parsear_horario_fijo(horario_str, dia_semana):
    if not horario_str:
        return None
    texto = horario_str.lower()
    partes = re.split(r'\s+y\s+', texto)
    for parte in partes:
        dia_encontrado = None
        for nombre, num in _DIAS_NUM.items():
            if nombre in parte:
                dia_encontrado = num
                break
        if dia_encontrado != dia_semana:
            continue
        m = re.search(r'(\d{1,2}):(\d{2})\s*(am|pm)?', parte)
        if not m:
            continue
        h, mins, ampm = int(m.group(1)), int(m.group(2)), m.group(3)
        if ampm == "pm" and h != 12:
            h += 12
        elif ampm == "am" and h == 12:
            h = 0
        elif ampm is None and 1 <= h <= 8:
            h += 12
        return f"{h:02d}:{mins:02d}"
    return None


# ------------------------------------------------
# CONFIGURACIÓN GENERAL
# ------------------------------------------------

INTERVALO_MINUTOS = 30
DOMINGO = 6

HORARIOS = {
    0: [("10:00", "12:00"), ("16:00", "21:30")],
    1: [("10:00", "12:00"), ("16:00", "21:30")],
    2: [("10:00", "12:00"), ("16:00", "21:30")],
    3: [("10:00", "13:00"), ("14:00", "21:30")],
    4: [("09:00", "13:00"), ("14:00", "17:00")],
    5: [("09:00", "13:00"), ("14:00", "21:30")],
}

FESTIVOS = {
    # ── 2025 ─────────────────────────────────────
    "2025-01-01", "2025-01-06", "2025-03-24", "2025-04-17", "2025-04-18",
    "2025-05-01", "2025-06-02", "2025-06-23", "2025-06-30", "2025-07-20",
    "2025-08-07", "2025-08-18", "2025-10-13", "2025-11-03", "2025-11-17",
    "2025-12-08", "2025-12-25",
    # ── 2026 ─────────────────────────────────────
    "2026-01-01", "2026-01-12", "2026-03-23", "2026-04-02", "2026-04-03",
    # "2026-05-01" — habilitado excepcionalmente (1 may 2026)
    "2026-05-18", "2026-06-08", "2026-06-15", "2026-06-29",
    "2026-07-20", "2026-08-07", "2026-08-17", "2026-10-12", "2026-11-02",
    "2026-11-16", "2026-12-08", "2026-12-25",
}


# ------------------------------------------------
# NORMALIZAR FECHA
# ------------------------------------------------

def normalizar_fecha(fecha):
    if isinstance(fecha, str):
        f = fecha.strip().lower()
        if f == "hoy":
            return _colombia_now()
        if f in ("mañana", "manana"):
            return _colombia_now() + timedelta(days=1)
        if f in ("pasado mañana", "pasado manana"):
            return _colombia_now() + timedelta(days=2)
        try:
            return datetime.strptime(f, "%Y-%m-%d")
        except ValueError:
            pass
        por_nombre = _dia_nombre_a_fecha(f)
        if por_nombre:
            return por_nombre
        parsed = dateparser.parse(f, languages=["es"], settings={"PREFER_DATES_FROM": "future"})
        if parsed:
            return parsed
        return None
    if isinstance(fecha, datetime):
        return fecha
    try:
        return datetime.combine(fecha, time())
    except Exception:
        return None


# ------------------------------------------------
# GENERAR SLOTS
# ------------------------------------------------

def generar_slots(inicio, fin):
    slots = []
    actual = inicio
    while actual < fin:
        slots.append(actual.time())
        actual += timedelta(minutes=INTERVALO_MINUTOS)
    return slots


# ------------------------------------------------
# OBTENER HORARIOS DISPONIBLES
# ------------------------------------------------

def obtener_horarios_disponibles(barbero_id, fecha, barberia_id=None):
    try:
        fecha_obj = normalizar_fecha(fecha)
        if not fecha_obj:
            return []

        fecha_date = fecha_obj.date()
        hoy        = datetime.utcnow() - timedelta(hours=5)
        dia_semana = fecha_obj.weekday()
        fecha_str  = fecha_obj.strftime("%Y-%m-%d")

        if fecha_str in FESTIVOS:
            return "festivo"
        if dia_semana == DOMINGO:
            return "domingo"

        # Usar horarios propios de la barbería si tiene config; si no, los globales
        horarios_config = HORARIOS
        if barberia_id:
            try:
                from app.models.barberia import Barberia
                b = Barberia.query.get(barberia_id)
                if b:
                    horarios_config = b.get_horarios()
                    # Verificar días bloqueados por la barbería
                    if fecha_str in b.get_dias_bloqueados():
                        return "cerrado"
            except Exception:
                pass

        bloques = horarios_config.get(dia_semana)
        if not bloques:
            return []

        slots = []
        for inicio_str, fin_str in bloques:
            inicio_time = datetime.strptime(inicio_str, "%H:%M").time()
            fin_time    = datetime.strptime(fin_str,    "%H:%M").time()
            inicio = datetime.combine(fecha_date, inicio_time)
            fin    = datetime.combine(fecha_date, fin_time)
            slots.extend(generar_slots(inicio, fin))

        if fecha_date == hoy.date():
            slots = [s for s in slots if datetime.combine(fecha_date, s) > hoy]

        citas = Cita.query.filter(
            Cita.barbero_id == int(barbero_id),
            Cita.fecha == fecha_date,
            Cita.estado != "cancelada"
        ).all()
        ocupadas = {c.hora for c in citas}

        # Bloquear horarios de clientes fijos (filtrado por barbería)
        try:
            q_fijos = Cliente.query.filter_by(fijo=True)
            if barberia_id:
                q_fijos = q_fijos.filter_by(barberia_id=barberia_id)
            for cf in q_fijos.all():
                hora_fija_str = _parsear_horario_fijo(cf.horario_fijo, dia_semana)
                if hora_fija_str:
                    t = datetime.strptime(hora_fija_str, "%H:%M").time()
                    # Solo bloquear si NO hay una cita cancelada de ese cliente en ese slot
                    cita_cancelada = Cita.query.filter_by(
                        cliente_id=cf.id,
                        fecha=fecha_date,
                        hora=t,
                        estado="cancelada"
                    ).first()
                    if not cita_cancelada:
                        ocupadas.add(t)
        except Exception as e:
            print("⚠ Error bloqueando horarios fijos:", e)

        horarios = []
        for slot in slots:
            horarios.append({
                "hora": slot.strftime("%H:%M"),
                "disponible": slot not in ocupadas
            })

        return horarios

    except Exception as e:
        print("⚠ Error obteniendo horarios:", e)
        return None
