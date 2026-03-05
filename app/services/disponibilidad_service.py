from app.models import Cita
from datetime import datetime, time, timedelta


def obtener_horarios_disponibles(barbero_id, fecha):

    inicio = time(9, 0)
    fin = time(18, 0)

    duracion = timedelta(minutes=30)

    citas = Cita.query.filter_by(
        barbero_id=barbero_id,
        fecha=fecha
    ).all()

    horas_ocupadas = {cita.hora for cita in citas}

    horarios = []

    hora_actual = datetime.combine(fecha, inicio)

    fin_datetime = datetime.combine(fecha, fin)

    while hora_actual < fin_datetime:

        hora = hora_actual.time()

        if hora not in horas_ocupadas:
            horarios.append(hora.strftime("%H:%M"))

        hora_actual += duracion

    return horarios