from app.extensions import db
from datetime import datetime
import json


class UserState(db.Model):
    __tablename__ = "user_states"

    id         = db.Column(db.Integer, primary_key=True)

    barberia_id = db.Column(db.Integer, db.ForeignKey("barberias.id"), nullable=True, index=True)

    # unique=True quitado — ahora la unicidad es (telefono, barberia_id), gestionada
    # por el índice uq_user_states_tel_barberia creado en la migración de startup.
    telefono   = db.Column(db.String(50), nullable=False, index=True)

    estado     = db.Column(db.String(50), default="inicio")
    data       = db.Column(db.Text, default="{}")
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def get_data(self):
        try:
            return json.loads(self.data)
        except Exception:
            return {"estado": "inicio"}

    def set_data(self, data_dict):
        self.estado = data_dict.get("estado", "inicio")
        self.data = json.dumps(data_dict)

    def __repr__(self):
        return f"<UserState {self.telefono} bid={self.barberia_id} → {self.estado}>"
