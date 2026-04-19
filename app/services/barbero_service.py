from app.models.barbero import Barbero


def obtener_barberos(barberia_id=None):
    if barberia_id:
        barberos = Barbero.query.filter_by(barberia_id=barberia_id).all()
    else:
        barberos = Barbero.query.all()

    return [
        {
            "id": b.id,
            "nombre": b.nombre
        }
        for b in barberos
    ]
