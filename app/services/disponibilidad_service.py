from datetime import datetime, time, timedelta
from app.models import Cita, Cliente
import dateparser
import re


# ------------------------------------------------
# DIAS EN ESPAÑOL → número weekday
# ------------------------------------------------

_DIAS_NUM = {
    "lunes": 0, "martes": 1,
    "miércoles": 2, "miercoles": 2,
    "jueves": 3, "viernes": 4,
    "sábado": 5, "sabado": 5
}


def _parsear_horario_fijo(horario_str, dia_semana):
    """
    Dado un string como 'Lunes 10:00' o 'Martes y Jueves 16:00',
    devuelve la hora (str HH:MM) si el dia_semana coincide, si no None.
    """
    if not horario_str:
        return None
    texto = horario_str.lower()
    m = re.search(r'(\d{1,2}:\d{2})', texto)
    if not m:
        return None
    hora_str = m.group(1)
    for nombre, num in _DIAS_NUM.items():
        if nombre in texto and num == dia_semana:
            return hora_str
    return None


# ------------------------------------------------
# CONFIGURACIÓN GENERAL
# ------------------------------------------------

INTERVALO_MINUTOS = 30
DOMINGO = 6


# ------------------------------------------------
# HORARIOS POR DÍA
# ------------------------------------------------
# 0 lunes
# 1 martes
# 2 miércoles
# 3 jueves
# 4 viernes
# 5 sábado
# 6 domingo

HORARIOS = {

    # lunes
    0: [
        ("10:00", "12:00"),
        ("16:00", "20:00")
    ],

    # martes
    1: [
        ("10:00", "12:00"),
        ("16:00", "20:00")
    ],

    # miércoles
    2: [
        ("10:00", "12:00"),
        ("16:00", "20:00")
    ],

    # jueves
    3: [
        ("10:00", "12:30"),
        ("15:00", "22:00")
    ],

    # viernes
    4: [
        ("09:00", "13:30"),
        ("14:30", "21:30")
    ],

    # sábado
    5: [
        ("09:00", "13:00"),
        ("15:00", "21:30")
    ]

}


# ------------------------------------------------
# FESTIVOS COLOMBIA
# Incluye fijos y los movibles (Ley Emiliani) para 2025 y 2026
# ------------------------------------------------

FESTIVOS = {
    # ── 2025 ─────────────────────────────────────
    "2025-01-01",  # Año Nuevo
    "2025-01-06",  # Reyes Magos
    "2025-03-24",  # San José (movido a lunes)
    "2025-04-17",  # Jueves Santo
    "2025-04-18",  # Viernes Santo
    "2025-05-01",  # Día del Trabajo
    "2025-06-02",  # Ascensión del Señor (movido a lunes)
    "2025-06-23",  # Corpus Christi (movido a lunes)
    "2025-06-30",  # Sagrado Corazón / San Pedro y San Pablo
    "2025-07-20",  # Independencia
    "2025-08-07",  # Batalla de Boyacá
    "2025-08-18",  # Asunción (movido a lunes)
    "2025-10-13",  # Día de la Raza (movido a lunes)
    "2025-11-03",  # Todos los Santos (movido a lunes)
    "2025-11-17",  # Independencia de Cartagena (movido a lunes)
    "2025-12-08",  # Inmaculada Concepción
    "2025-12-25",  # Navidad

    # ── 2026 ─────────────────────────────────────
    "2026-01-01",  # Año Nuevo
    "2026-01-12",  # Reyes Magos (movido a lunes)
    "2026-03-23",  # San José (movido a lunes)
    "2026-04-02",  # Jueves Santo
    "2026-04-03",  # Viernes Santo
    "2026-05-01",  # Día del Trabajo
    "2026-05-18",  # Ascensión del Señor (movido a lunes)
    "2026-06-08",  # Corpus Christi (movido a lunes)
    "2026-06-15",  # Sagrado Corazón (movido a lunes)
    "2026-06-29",  # San Pedro y San Pablo
    "2026-07-20",  # Independencia
    "2026-08-07",  # Batalla de Boyacá
    "2026-08-17",  # Asunción (movido a lunes)
    "2026-10-12",  # Día de la Raza
    "2026-11-02",  # Todos los Santos (movido a lunes)
    "2026-11-16",  # Independencia de Cartagena (movido a lunes)
    "2026-12-08",  # Inmaculada Concepción
    "2026-12-25",  # Navidad
}


# ------------------------------------------------
# NORMALIZAR FECHA
# ------------------------------------------------

def normalizar_fecha(fecha):

    if isinstance(fecha, str):

        f = fecha.strip().lower()

        if f == "hoy":
            return datetime.now()

        if f in ("mañana", "manana"):
            return datetime.now() + timedelta(days=1)

        if f in ("pasado mañana", "pasado manana"):
            return datetime.now() + timedelta(days=2)

        try:
            return datetime.strptime(f, "%Y-%m-%d")
        except:
            pass

        # Fallback: dateparser para "lunes", "próximo viernes", etc.
        parsed = dateparser.parse(f, languages=["es"], settings={"PREFER_DATES_FROM": "future"})
        if parsed:
            return parsed

        return None

    if isinstance(fecha, datetime):
        return fecha

    try:
        return datetime.combine(fecha, time())
    except:
        return None


# ------------------------------------------------
# GENERAR SLOTS DE HORARIO
# ------------------------------------------------

def generar_slots(inicio, fin):

    """
    Genera slots cada INTERVALO_MINUTOS
    """

    slots = []
    actual = inicio

    while actual < fin:

        slots.append(actual.time())

        actual += timedelta(minutes=INTERVALO_MINUTOS)

    return slots


# ------------------------------------------------
# OBTENER HORARIOS DISPONIBLES
# ------------------------------------------------

def obtener_horarios_disponibles(barbero_id, fecha):

    try:

        # ------------------------------------------------
        # NORMALIZAR FECHA
        # ------------------------------------------------

        fecha_obj = normalizar_fecha(fecha)

        if not fecha_obj:
            return []

        fecha_date = fecha_obj.date()

        hoy = datetime.utcnow() - timedelta(hours=5)  # Colombia UTC-5

        dia_semana = fecha_obj.weekday()

        fecha_str = fecha_obj.strftime("%Y-%m-%d")


        # ------------------------------------------------
        # FESTIVOS
        # ------------------------------------------------

        if fecha_str in FESTIVOS:
            return "festivo"

        # ------------------------------------------------
        # DOMINGO CERRADO
        # ------------------------------------------------

        if dia_semana == DOMINGO:
            return "domingo"


        # ------------------------------------------------
        # OBTENER BLOQUES DEL DÍA
        # ------------------------------------------------

        bloques = HORARIOS.get(dia_semana)

        if not bloques:
            return []


        slots = []


        # ------------------------------------------------
        # GENERAR SLOTS DE LOS BLOQUES
        # ------------------------------------------------

        for inicio_str, fin_str in bloques:

            inicio_time = datetime.strptime(inicio_str, "%H:%M").time()
            fin_time = datetime.strptime(fin_str, "%H:%M").time()

            inicio = datetime.combine(fecha_date, inicio_time)
            fin = datetime.combine(fecha_date, fin_time)

            slots_bloque = generar_slots(inicio, fin)

            slots.extend(slots_bloque)


        # ------------------------------------------------
        # BLOQUEAR HORAS PASADAS
        # ------------------------------------------------

        if fecha_date == hoy.date():

            slots = [
                s for s in slots
                if datetime.combine(fecha_date, s) > hoy
            ]


        # ------------------------------------------------
        # OBTENER CITAS OCUPADAS
        # ------------------------------------------------

        citas = Cita.query.filter_by(
            barbero_id=barbero_id,
            fecha=fecha_date
        ).all()

        ocupadas = {c.hora for c in citas}

        # Bloquear horarios de clientes fijos aunque no tengan cita en DB
        try:
            clientes_fijos = Cliente.query.filter_by(fijo=True).all()
            for cf in clientes_fijos:
                hora_fija_str = _parsear_horario_fijo(cf.horario_fijo, dia_semana)
                if hora_fija_str:
                    t = datetime.strptime(hora_fija_str, "%H:%M").time()
                    ocupadas.add(t)
        except Exception as e:
            print("⚠ Error bloqueando horarios fijos:", e)


        # ------------------------------------------------
        # GENERAR RESPUESTA FINAL
        # ------------------------------------------------

        horarios = []

        for slot in slots:

            disponible = slot not in ocupadas

            horarios.append({
                "hora": slot.strftime("%H:%M"),
                "disponible": disponible
            })


        return horarios


    except Exception as e:

        print("⚠ Error obteniendo horarios:", e)
        return None