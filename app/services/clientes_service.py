from app.extensions import db
from app.models.cliente import Cliente

def obtener_o_crear_cliente(nombre, telefono):

    cliente = Cliente.query.filter_by(telefono=telefono).first()

    if cliente:
        return cliente

    cliente = Cliente(
        nombre=nombre,
        telefono=telefono
    )

    db.session.add(cliente)
    db.session.commit()

    return cliente