from app.extensions import db
from datetime import datetime


class Cliente(db.Model):

    __tablename__ = "clientes"

    id = db.Column(db.Integer, primary_key=True)

    barberia_id = db.Column(db.Integer, db.ForeignKey("barberias.id"), nullable=True, index=True)

    nombre = db.Column(db.String(100), nullable=False)

    # unique=True quitado — ahora la unicidad es (telefono, barberia_id), gestionada
    # por el índice uq_clientes_tel_barberia creado en la migración de startup.
    telefono = db.Column(db.String(20), nullable=False, index=True)

    fecha_cumpleanos = db.Column(db.Date, nullable=True)

    fijo = db.Column(db.Boolean, default=False)

    horario_fijo = db.Column(db.String(100), nullable=True)

    creado_en = db.Column(db.DateTime, default=datetime.utcnow)
