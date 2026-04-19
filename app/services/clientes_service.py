from app.extensions import db
from app.models.cliente import Cliente


def obtener_cliente_por_telefono(telefono, barberia_id=None):
    """
    Busca con/sin prefijo '+' para tolerar diferencias de formato.
    Si barberia_id está presente, filtra por barbería.
    """
    tel = telefono.strip()
    alt = tel[1:] if tel.startswith('+') else ('+' + tel)

    for t in (tel, alt):
        q = Cliente.query.filter_by(telefono=t)
        if barberia_id:
            q = q.filter_by(barberia_id=barberia_id)
        c = q.first()
        if c:
            return c
    return None


def crear_cliente(nombre, telefono, barberia_id=None):
    cliente = Cliente(
        nombre=nombre,
        telefono=telefono,
        barberia_id=barberia_id,
    )
    db.session.add(cliente)
    db.session.commit()
    return cliente


def obtener_o_crear_cliente(nombre, telefono, barberia_id=None):
    cliente = obtener_cliente_por_telefono(telefono, barberia_id)
    if cliente:
        return cliente
    return crear_cliente(nombre, telefono, barberia_id)


def actualizar_nombre_cliente(cliente, nombre):
    if not nombre:
        return cliente
    if cliente.nombre != nombre:
        cliente.nombre = nombre
        db.session.commit()
    return cliente
