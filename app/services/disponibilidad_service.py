from app.models import Cita
from datetime import datetime, time, timedelta


def obtener_horarios_disponibles(barbero_id, fecha):

    if isinstance(fecha, str):
        fecha = datetime.strptime(fecha, "%Y-%m-%d").date()

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

    ahora = datetime.now()

    while hora_actual < fin_datetime:

        hora = hora_actual.time()

        if hora not in horas_ocupadas and hora_actual > ahora:
            horarios.append(hora.strftime("%H:%M"))

        hora_actual += duracion

    return horarios