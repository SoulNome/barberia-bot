from app.models import Cita, Cliente
from app import db
from datetime import datetime, date, timedelta
from sqlalchemy.exc import IntegrityError
import re


# ------------------------------------------------
# UTILIDADES
# ------------------------------------------------

def normalizar_fecha(fecha):

    if isinstance(fecha, str):
        try:
            return datetime.strptime(fecha, "%Y-%m-%d").date()
        except ValueError:
            pass
        # Fallback: usar el mismo parser confiable de disponibilidad_service
        from app.services.disponibilidad_service import _dia_nombre_a_fecha
        por_nombre = _dia_nombre_a_fecha(fecha)
        if por_nombre:
            return por_nombre.date()
        import dateparser
        parsed = dateparser.parse(fecha, languages=["es"], settings={"PREFER_DATES_FROM": "future"})
        if parsed:
            return parsed.date()
        return None

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
            if h != 12:
                h += 12
            return datetime.strptime(f"{h}:00", "%H:%M").time()

        # aceptar formato 1am
        match = re.match(r"(\d{1,2})\s*am", hora)
        if match:
            h = int(match.group(1))
            if h == 12:
                h = 0
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

def crear_cita(nombre, telefono, barbero_id, fecha, hora, servicio=None, skip_client_check=False):

    try:

        fecha = normalizar_fecha(fecha)
        if not fecha:
            return False, "❌ Fecha inválida. Intenta con un formato como 2026-04-15."

        hora = normalizar_hora(hora)

        cliente = obtener_o_crear_cliente(nombre, telefono)

        # ------------------------------------------------
        # VERIFICAR SI CLIENTE YA TIENE CITA
        # ------------------------------------------------

        if not skip_client_check:
            cita_cliente = Cita.query.filter(
                Cita.cliente_id == cliente.id,
                Cita.fecha >= (datetime.utcnow() - timedelta(hours=5)).date()
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
        # VERIFICAR SI HORARIO OCUPADO (primera barrera)
        # ------------------------------------------------

        cita_existente = Cita.query.filter_by(
            barbero_id=barbero_id,
            fecha=fecha,
            hora=hora
        ).first()

        if cita_existente:
            return False, "❌ Ese horario ya está ocupado. Por favor elige otro."

        # ------------------------------------------------
        # VERIFICAR SI HORARIO ES DE CLIENTE FIJO (segunda barrera)
        # ------------------------------------------------

        try:
            from app.services.disponibilidad_service import _parsear_horario_fijo as _chk_fijo
            dia_semana = fecha.weekday()
            for cf in Cliente.query.filter_by(fijo=True).all():
                if cf.telefono == telefono:
                    continue  # el mismo cliente fijo puede confirmar su propio turno
                hora_fija_str = _chk_fijo(cf.horario_fijo, dia_semana)
                if hora_fija_str:
                    t_fijo = datetime.strptime(hora_fija_str, "%H:%M").time()
                    if t_fijo == hora:
                        return False, "❌ Ese horario está reservado para un cliente habitual. Por favor elige otro."
        except Exception as e:
            print(f"⚠ Error verificando fijos en crear_cita: {e}")

        # ------------------------------------------------
        # CREAR CITA
        # ------------------------------------------------

        nueva_cita = Cita(
            cliente_id=cliente.id,
            barbero_id=barbero_id,
            fecha=fecha,
            hora=hora,
            servicio=servicio
        )

        db.session.add(nueva_cita)

        try:
            db.session.commit()
        except IntegrityError:
            # Segunda barrera: la BD rechazó el turno duplicado
            db.session.rollback()
            return False, "❌ Ese horario acaba de ser tomado por otro cliente. Por favor elige otro turno."

        try:
            from app.models import Barbero
            from app.services.recordatorio_service import notificar_barbero
            barbero = Barbero.query.get(barbero_id)
            notificar_barbero(
                nombre_cliente=nombre,
                fecha=str(fecha),
                hora=hora.strftime("%H:%M"),
                servicio=servicio,
                barbero_nombre=barbero.nombre if barbero else None,
                accion="nueva"
            )
        except Exception:
            pass

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

        barbero_id_guardado = cita.barbero_id
        fecha_guardada      = cita.fecha

        db.session.delete(cita)
        db.session.commit()

        # Notificar lista de espera si alguien está esperando
        try:
            from app.services.lista_espera_service import notificar_lista_espera
            notificar_lista_espera(barbero_id_guardado, fecha_guardada)
        except Exception:
            pass

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
        Cita.fecha >= (datetime.utcnow() - timedelta(hours=5)).date()
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