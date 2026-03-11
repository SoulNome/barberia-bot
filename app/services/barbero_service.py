from app.models.barbero import Barbero

def obtener_barberos():

    barberos = Barbero.query.all()

    return [
        {
            "id": b.id,
            "nombre": b.nombre
        }
        for b in barberos
    ]