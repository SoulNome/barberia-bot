from datetime import datetime, time, timedelta
from app.models import Cita


# ------------------------------------------------
# FESTIVOS
# ------------------------------------------------

FESTIVOS = [
    "2026-01-01",
    "2026-12-25",
]


# ------------------------------------------------
# OBTENER HORARIOS DISPONIBLES
# ------------------------------------------------

def obtener_horarios_disponibles(barbero_id, fecha):

    try:

        # normalizar fecha
        if isinstance(fecha, str):
            fecha_obj = datetime.strptime(fecha, "%Y-%m-%d")
        else:
            fecha_obj = datetime.combine(fecha, time())

        hoy = datetime.now()

        dia_semana = fecha_obj.weekday()
        # lunes=0 ... domingo=6

        fecha_str = fecha_obj.strftime("%Y-%m-%d")

        # ------------------------------------------------
        # FESTIVOS
        # ------------------------------------------------

        if fecha_str in FESTIVOS:
            return []

        # ------------------------------------------------
        # DOMINGO CERRADO
        # ------------------------------------------------

        if dia_semana == 6:
            return []

        # ------------------------------------------------
        # HORARIO BASE
        # ------------------------------------------------

        inicio = datetime.combine(fecha_obj.date(), time(9, 0))
        fin = datetime.combine(fecha_obj.date(), time(18, 0))

        slots = []

        actual = inicio

        while actual < fin:

            slots.append(actual.time())

            actual += timedelta(minutes=30)

        # ------------------------------------------------
        # BLOQUEO ALMUERZO
        # ------------------------------------------------

        if dia_semana in [0, 1, 2]:  # lunes martes miércoles

            slots = [
                s for s in slots
                if not (time(12, 30) <= s < time(16, 0))
            ]

        # ------------------------------------------------
        # BLOQUEAR HORAS PASADAS SI ES HOY
        # ------------------------------------------------

        if fecha_obj.date() == hoy.date():

            slots = [
                s for s in slots
                if datetime.combine(fecha_obj.date(), s) > hoy
            ]

        # ------------------------------------------------
        # OBTENER CITAS DEL BARBERO
        # ------------------------------------------------

        citas = Cita.query.filter_by(
            barbero_id=barbero_id,
            fecha=fecha_obj.date()
        ).all()

        ocupadas = [c.hora for c in citas]

        # ------------------------------------------------
        # FILTRAR DISPONIBLES
        # ------------------------------------------------

        disponibles = [
            s.strftime("%H:%M")
            for s in slots
            if s not in ocupadas
        ]

        return disponibles

    except Exception as e:

        print("Error obteniendo horarios:", e)

        return []