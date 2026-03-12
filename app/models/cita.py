from app.extensions import db
from datetime import datetime


class Cita(db.Model):

    __tablename__ = "citas"

    id = db.Column(db.Integer, primary_key=True)

    cliente_id = db.Column(db.Integer, db.ForeignKey("clientes.id"))

    barbero_id = db.Column(db.Integer, db.ForeignKey("barberos.id"))

    fecha = db.Column(db.Date)

    hora = db.Column(db.Time)

    servicio = db.Column(db.String(100))  # NUEVO CAMPO

    estado = db.Column(db.String(20), default="confirmada")

    creado_en = db.Column(db.DateTime, default=datetime.utcnow)