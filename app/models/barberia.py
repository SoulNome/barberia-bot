from app.extensions import db

class Barberia(db.Model):

    __tablename__ = "barberias"

    id = db.Column(db.Integer, primary_key=True)

    nombre = db.Column(db.String(100), nullable=False)

    telefono = db.Column(db.String(20))

    direccion = db.Column(db.String(200))

    whatsapp_number = db.Column(db.String(20))