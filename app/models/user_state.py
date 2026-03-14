# app/models/user_state.py
# Agregar este archivo en app/models/

from app.extensions import db
from datetime import datetime
import json

class UserState(db.Model):
    __tablename__ = "user_states"

    id          = db.Column(db.Integer, primary_key=True)
    telefono    = db.Column(db.String(50), unique=True, nullable=False, index=True)
    estado      = db.Column(db.String(50), default="inicio")
    data        = db.Column(db.Text, default="{}")  # JSON con el estado completo
    updated_at  = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def get_data(self):
        try:
            return json.loads(self.data)
        except:
            return {"estado": "inicio"}

    def set_data(self, data_dict):
        self.estado = data_dict.get("estado", "inicio")
        self.data = json.dumps(data_dict)

    def __repr__(self):
        return f"<UserState {self.telefono} → {self.estado}>"
