from app.models import Cita, Cliente
from app import db
from datetime import datetime


def crear_cita(nombre, telefono, barbero_id, fecha, hora):

    # Buscar cliente por teléfono
    cliente = Cliente.query.filter_by(telefono=telefono).first()

    # Si no existe, crearlo automáticamente
    if not cliente:
        cliente = Cliente(
            nombre=nombre,
            telefono=telefono
        )
        db.session.add(cliente)
        db.session.commit()

    # Verificar si el horario ya está ocupado
    cita_existente = Cita.query.filter_by(
        barbero_id=barbero_id,
        fecha=fecha,
        hora=hora
    ).first()

    if cita_existente:
        return False, "Ese horario ya está ocupado"

    # Crear la cita
    nueva_cita = Cita(
        cliente_id=cliente.id,
        barbero_id=barbero_id,
        fecha=fecha,
        hora=hora
    )

    db.session.add(nueva_cita)
    db.session.commit()

    return True, "Cita creada correctamente"
def cancelar_cita(telefono, fecha, hora):

    from app.models import Cliente, Cita

    cliente = Cliente.query.filter_by(telefono=telefono).first()

    if not cliente:
        return False, "Cliente no encontrado"

    cita = Cita.query.filter_by(
        cliente_id=cliente.id,
        fecha=fecha,
        hora=hora
    ).first()

    if not cita:
        return False, "No existe esa cita"

    db.session.delete(cita)
    db.session.commit()

    return True, "Cita cancelada"