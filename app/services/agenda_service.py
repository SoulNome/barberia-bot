from app.models import Cita, Cliente
from app import db
from datetime import datetime, date
import re


# ------------------------------------------------
# UTILIDADES
# ------------------------------------------------

def normalizar_fecha(fecha):

    if isinstance(fecha, str):
        return datetime.strptime(fecha, "%Y-%m-%d").date()

    return fecha


def normalizar_hora(hora):

    if isinstance(hora, str):

        hora = hora.strip().lower()

        # aceptar formato 13:30:00
        if len(hora) == 8:
            hora = hora[:5]

        # aceptar formato 1pm
        match = re.match(r"(\d{1,2})\s*pm", hora)
        if match:
            h = int(match.group(1))
            return datetime.strptime(f"{h+12}:00", "%H:%M").time()

        # aceptar formato 1am
        match = re.match(r"(\d{1,2})\s*am", hora)
        if match:
            h = int(match.group(1))
            return datetime.strptime(f"{h}:00", "%H:%M").time()

        return datetime.strptime(hora, "%H:%M").time()

    return hora


def formatear_hora(hora):

    if isinstance(hora, str):
        hora = normalizar_hora(hora)

    return hora.strftime("%H:%M")


def obtener_o_crear_cliente(nombre, telefono):

    cliente = Cliente.query.filter_by(telefono=telefono).first()

    if not cliente:

        cliente = Cliente(
            nombre=nombre,
            telefono=telefono
        )

        db.session.add(cliente)
        db.session.commit()

    return cliente


# ------------------------------------------------
# CREAR CITA
# ------------------------------------------------

def crear_cita(nombre, telefono, barbero_id, fecha, hora):

    try:

        fecha = normalizar_fecha(fecha)
        hora = normalizar_hora(hora)

        cliente = obtener_o_crear_cliente(nombre, telefono)

        # ------------------------------------------------
        # VERIFICAR SI CLIENTE YA TIENE CITA
        # ------------------------------------------------

        cita_cliente = Cita.query.filter(
            Cita.cliente_id == cliente.id,
            Cita.fecha >= date.today()
        ).first()

        if cita_cliente:

            return False, f"""
❌ Ya tienes una cita registrada:

📅 {cita_cliente.fecha}
⏰ {formatear_hora(cita_cliente.hora)}

Si deseas cancelarla escribe:

cancelar {cita_cliente.fecha} {formatear_hora(cita_cliente.hora)}
"""

        # ------------------------------------------------
        # VERIFICAR SI HORARIO OCUPADO
        # ------------------------------------------------

        cita_existente = Cita.query.filter_by(
            barbero_id=barbero_id,
            fecha=fecha,
            hora=hora
        ).first()

        if cita_existente:
            return False, "❌ Ese horario ya está ocupado."

        # ------------------------------------------------
        # CREAR CITA
        # ------------------------------------------------

        nueva_cita = Cita(
            cliente_id=cliente.id,
            barbero_id=barbero_id,
            fecha=fecha,
            hora=hora
        )

        db.session.add(nueva_cita)
        db.session.commit()

        return True, "Cita creada correctamente"

    except Exception as e:

        db.session.rollback()

        return False, f"Error creando cita: {str(e)}"


# ------------------------------------------------
# CANCELAR CITA
# ------------------------------------------------

def cancelar_cita(telefono, fecha, hora):

    try:

        fecha = normalizar_fecha(fecha)
        hora = normalizar_hora(hora)

        cliente = Cliente.query.filter_by(telefono=telefono).first()

        if not cliente:
            return False, "❌ No encontramos un cliente con ese número."

        cita = Cita.query.filter_by(
            cliente_id=cliente.id,
            fecha=fecha,
            hora=hora
        ).first()

        if not cita:
            return False, "❌ No encontramos esa cita."

        db.session.delete(cita)
        db.session.commit()

        return True, "✅ Tu cita fue cancelada correctamente."

    except Exception as e:

        db.session.rollback()

        return False, f"Error cancelando cita: {str(e)}"


# ------------------------------------------------
# VER PRÓXIMA CITA
# ------------------------------------------------

def obtener_cita_cliente(telefono):

    cliente = Cliente.query.filter_by(telefono=telefono).first()

    if not cliente:
        return None

    cita = Cita.query.filter(
        Cita.cliente_id == cliente.id,
        Cita.fecha >= date.today()
    ).order_by(Cita.fecha.asc()).first()

    return cita


# ------------------------------------------------
# VERIFICAR SI EXISTE CITA
# ------------------------------------------------

def cita_existente(barbero_id, fecha, hora):

    fecha = normalizar_fecha(fecha)
    hora = normalizar_hora(hora)

    return Cita.query.filter_by(
        barbero_id=barbero_id,
        fecha=fecha,
        hora=hora
    ).first()