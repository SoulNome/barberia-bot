from app.extensions import db

class Cliente(db.Model):

    __tablename__ = "clientes"

    id = db.Column(db.Integer, primary_key=True)

    nombre = db.Column(db.String(100))

    telefono = db.Column(db.String(20), unique=True)