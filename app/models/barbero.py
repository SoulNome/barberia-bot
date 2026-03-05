from app.extensions import db

class Barbero(db.Model):

    __tablename__ = "barberos"

    id = db.Column(db.Integer, primary_key=True)

    nombre = db.Column(db.String(100), nullable=False)

    barberia_id = db.Column(db.Integer, db.ForeignKey("barberias.id"), nullable=False)