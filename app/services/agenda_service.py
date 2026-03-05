from app.models import Cita
from app import db
from datetime import datetime


def crear_cita(cliente_id, barbero_id, fecha, hora):

    cita_existente = Cita.query.filter_by(
        barbero_id=barbero_id,
        fecha=fecha,
        hora=hora
    ).first()

    if cita_existente:
        return False, "Ese horario ya está ocupado"

    nueva_cita = Cita(
        cliente_id=cliente_id,
        barbero_id=barbero_id,
        fecha=fecha,
        hora=hora
    )

    db.session.add(nueva_cita)
    db.session.commit()

    return True, "Cita creada correctamente"