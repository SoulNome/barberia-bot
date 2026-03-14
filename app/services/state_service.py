from app.extensions import db
from app.models.user_state import UserState
from datetime import datetime, timedelta

STATE_TIMEOUT = timedelta(hours=2)


def get_state(telefono):
    us = UserState.query.filter_by(telefono=telefono).first()
    if not us:
        return {"estado": "inicio"}
    # Si el estado lleva más de 2 horas sin actividad, resetear
    if us.updated_at and datetime.utcnow() - us.updated_at > STATE_TIMEOUT:
        us.set_data({"estado": "inicio"})
        db.session.commit()
        return {"estado": "inicio"}
    return us.get_data()


def set_state(telefono, data_dict):
    us = UserState.query.filter_by(telefono=telefono).first()
    if not us:
        us = UserState(telefono=telefono)
        db.session.add(us)
    us.set_data(data_dict)
    db.session.commit()