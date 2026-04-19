from app.extensions import db
from datetime import datetime, timezone


class ListaEspera(db.Model):

    __tablename__ = "lista_espera"

    id         = db.Column(db.Integer, primary_key=True)

    barberia_id = db.Column(db.Integer, db.ForeignKey("barberias.id"), nullable=True, index=True)

    cliente_id = db.Column(db.Integer, db.ForeignKey("clientes.id"), nullable=False, index=True)
    barbero_id = db.Column(db.Integer, db.ForeignKey("barberos.id"), nullable=True,  index=True)
    fecha      = db.Column(db.Date,    nullable=False, index=True)
    servicio   = db.Column(db.String(100))
    notificado = db.Column(db.Boolean, default=False)
    creado_en  = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    cliente = db.relationship("Cliente", backref="lista_espera")
    barbero = db.relationship("Barbero", backref="lista_espera")
