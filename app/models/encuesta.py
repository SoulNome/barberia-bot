from app.extensions import db
from datetime import datetime, timezone


class Encuesta(db.Model):

    __tablename__ = "encuestas"

    id          = db.Column(db.Integer, primary_key=True)
    barberia_id = db.Column(db.Integer, db.ForeignKey("barberias.id"), nullable=True, index=True)
    cita_id     = db.Column(db.Integer, db.ForeignKey("citas.id"),     nullable=True, index=True)
    cliente_id  = db.Column(db.Integer, db.ForeignKey("clientes.id"),  nullable=False, index=True)
    calificacion = db.Column(db.Integer, nullable=False)   # 1-5
    comentario  = db.Column(db.Text,    nullable=True)
    creado_en   = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    cliente = db.relationship("Cliente", backref="encuestas")
