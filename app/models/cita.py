from app.extensions import db
from datetime import datetime, timezone


class Cita(db.Model):

    __tablename__ = "citas"

    id = db.Column(db.Integer, primary_key=True)

    cliente_id = db.Column(db.Integer, db.ForeignKey("clientes.id"), nullable=False, index=True)

    barbero_id = db.Column(db.Integer, db.ForeignKey("barberos.id"), nullable=False, index=True)

    fecha = db.Column(db.Date, nullable=False, index=True)

    hora = db.Column(db.Time, nullable=False)

    servicio = db.Column(db.String(100))

    estado = db.Column(db.String(20), default="confirmada")

    creado_en = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    cliente = db.relationship("Cliente", backref="citas")

    barbero = db.relationship("Barbero", backref="citas")