from app.extensions import db
from app.models.cliente import Cliente


# ------------------------------------------------
# OBTENER CLIENTE POR TELEFONO
# ------------------------------------------------

def obtener_cliente_por_telefono(telefono):

    return Cliente.query.filter_by(telefono=telefono).first()


# ------------------------------------------------
# CREAR CLIENTE
# ------------------------------------------------

def crear_cliente(nombre, telefono):

    cliente = Cliente(
        nombre=nombre,
        telefono=telefono
    )

    db.session.add(cliente)
    db.session.commit()

    return cliente


# ------------------------------------------------
# OBTENER O CREAR CLIENTE
# ------------------------------------------------

def obtener_o_crear_cliente(nombre, telefono):

    cliente = obtener_cliente_por_telefono(telefono)

    if cliente:
        return cliente

    return crear_cliente(nombre, telefono)


# ------------------------------------------------
# ACTUALIZAR NOMBRE CLIENTE
# ------------------------------------------------

def actualizar_nombre_cliente(cliente, nombre):

    if not nombre:
        return cliente

    if cliente.nombre != nombre:

        cliente.nombre = nombre

        db.session.commit()

    return cliente