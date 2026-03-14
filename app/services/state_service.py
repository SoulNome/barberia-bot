# app/services/state_service.py
# Reemplaza el diccionario user_states en memoria

from app.extensions import db
from app.models.user_state import UserState

def get_state(telefono):
    """Obtener estado del usuario desde la DB"""
    us = UserState.query.filter_by(telefono=telefono).first()
    if not us:
        return {"estado": "inicio"}
    return us.get_data()

def set_state(telefono, data_dict):
    """Guardar estado del usuario en la DB"""
    us = UserState.query.filter_by(telefono=telefono).first()
    if not us:
        us = UserState(telefono=telefono)
        db.session.add(us)
    us.set_data(data_dict)
    db.session.commit()