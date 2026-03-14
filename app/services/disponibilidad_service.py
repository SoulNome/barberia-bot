from datetime import datetime, time, timedelta
from app.models import Cita


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
        ("14:30", "22:00")
    ],

    # sábado
    5: [
        ("09:00", "13:00"),
        ("15:00", "21:00")
    ]

}


# ------------------------------------------------
# FESTIVOS
# ------------------------------------------------

FESTIVOS = [
    "2026-01-01",
    "2026-12-25",
]


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
            return []


        # ------------------------------------------------
        # DOMINGO CERRADO
        # ------------------------------------------------

        if dia_semana == DOMINGO:
            return []


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

        raise RuntimeError(f"[horarios] barbero_id={barbero_id} fecha={fecha} error={e}")