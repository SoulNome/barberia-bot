from app.extensions import db
from app.models.user_state import UserState
from datetime import datetime, timedelta

STATE_TIMEOUT = timedelta(hours=2)


def get_state(telefono, barberia_id=None):
    q = UserState.query.filter_by(telefono=telefono)
    if barberia_id:
        q = q.filter_by(barberia_id=barberia_id)
    us = q.first()

    if not us:
        return {"estado": "inicio"}

    if us.updated_at and datetime.utcnow() - us.updated_at > STATE_TIMEOUT:
        us.set_data({"estado": "inicio"})
        db.session.commit()
        return {"estado": "inicio"}

    return us.get_data()


def set_state(telefono, data_dict, barberia_id=None):
    q = UserState.query.filter_by(telefono=telefono)
    if barberia_id:
        q = q.filter_by(barberia_id=barberia_id)
    us = q.first()

    if not us:
        us = UserState(telefono=telefono, barberia_id=barberia_id)
        db.session.add(us)

    us.set_data(data_dict)
    db.session.commit()
