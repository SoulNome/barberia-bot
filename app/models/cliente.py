from app.extensions import db
from datetime import datetime

class Cliente(db.Model):

    __tablename__ = "clientes"

    id = db.Column(db.Integer, primary_key=True)

    nombre = db.Column(db.String(100), nullable=False)

    telefono = db.Column(db.String(20), unique=True, nullable=False, index=True)

    fecha_cumpleanos = db.Column(db.Date, nullable=True)

    fijo = db.Column(db.Boolean, default=False)

    horario_fijo = db.Column(db.String(100), nullable=True)

    creado_en = db.Column(db.DateTime, default=datetime.utcnow)