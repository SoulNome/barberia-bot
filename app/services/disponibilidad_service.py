from datetime import datetime, time, timedelta
from app.models import Cita


# ------------------------------------------------
# CONFIGURACIÓN DE NEGOCIO
# ------------------------------------------------

HORA_APERTURA = time(9, 0)
HORA_CIERRE = time(18, 0)

INTERVALO_MINUTOS = 30

HORARIO_ALMUERZO_INICIO = time(12, 30)
HORARIO_ALMUERZO_FIN = time(16, 0)

DIAS_ALMUERZO = [0, 1, 2]  # lunes martes miércoles

DOMINGO = 6


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

        try:
            return datetime.strptime(fecha, "%Y-%m-%d")

        except:
            return None

    if isinstance(fecha, datetime):
        return fecha

    return datetime.combine(fecha, time())


# ------------------------------------------------
# OBTENER HORARIOS DISPONIBLES
# ------------------------------------------------

def obtener_horarios_disponibles(barbero_id, fecha):

    try:

        fecha_obj = normalizar_fecha(fecha)

        if not fecha_obj:
            return []

        fecha_date = fecha_obj.date()

        hoy = datetime.now()

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
        # GENERAR HORARIOS
        # ------------------------------------------------

        inicio = datetime.combine(fecha_date, HORA_APERTURA)
        fin = datetime.combine(fecha_date, HORA_CIERRE)

        slots = []

        actual = inicio

        while actual < fin:

            slots.append(actual.time())

            actual += timedelta(minutes=INTERVALO_MINUTOS)

        # ------------------------------------------------
        # BLOQUEO ALMUERZO
        # ------------------------------------------------

        if dia_semana in DIAS_ALMUERZO:

            slots = [
                s for s in slots
                if not (HORARIO_ALMUERZO_INICIO <= s < HORARIO_ALMUERZO_FIN)
            ]

        # ------------------------------------------------
        # BLOQUEAR HORAS PASADAS
        # ------------------------------------------------

        if fecha_date == hoy.date():

            slots = [
                s for s in slots
                if datetime.combine(fecha_date, s) > hoy
            ]

        # ------------------------------------------------
        # OBTENER CITAS
        # ------------------------------------------------

        citas = Cita.query.filter_by(
            barbero_id=barbero_id,
            fecha=fecha_date
        ).all()

        ocupadas = {c.hora for c in citas}

        # ------------------------------------------------
        # GENERAR RESPUESTA
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

        return []