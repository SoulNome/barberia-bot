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
        if len(hora) == 8:
            hora = hora[:5]
        match = re.match(r"(\d{1,2})\s*pm", hora)
        if match:
            h = int(match.group(1))
            if h != 12:
                h += 12
            return datetime.strptime(f"{h}:00", "%H:%M").time()
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


def _buscar_cliente(telefono, barberia_id=None):
    """
    Busca un cliente normalizando el formato del teléfono.
    Filtra por barberia_id si se indica.
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


# ------------------------------------------------
# CREAR CITA
# ------------------------------------------------

def crear_cita(nombre, telefono, barbero_id, fecha, hora, servicio,
               skip_client_check=False, barberia_id=None):
    try:
        fecha = normalizar_fecha(fecha)
        hora  = normalizar_hora(hora)

        if not fecha or not hora:
            return False, "❌ Fecha u hora inválida."

        # ── Obtener o crear cliente ───────────────────────────────────────────
        from app.services.clientes_service import obtener_o_crear_cliente
        cliente = obtener_o_crear_cliente(nombre, telefono, barberia_id)

        # ── Verificar cita existente del cliente ──────────────────────────────
        if not skip_client_check:
            cita_existente_cliente = Cita.query.filter(
                Cita.cliente_id == cliente.id,
                Cita.fecha == fecha,
                Cita.estado != "cancelada"
            ).first()
            if cita_existente_cliente:
                return False, "❌ Ya tienes una cita ese día. Cancela la anterior o elige otro día."

        # ── Verificar slot disponible ─────────────────────────────────────────
        cita_existente = Cita.query.filter(
            Cita.barbero_id == int(barbero_id),
            Cita.fecha == fecha,
            Cita.hora == hora,
            Cita.estado != "cancelada"
        ).first()
        if cita_existente:
            return False, "❌ Ese horario ya está ocupado. Por favor elige otro."

        # ── Verificar slot de cliente fijo ────────────────────────────────────
        try:
            from app.services.disponibilidad_service import _parsear_horario_fijo as _chk_fijo
            dia_semana = fecha.weekday()
            q_fijos = Cliente.query.filter_by(fijo=True)
            if barberia_id:
                q_fijos = q_fijos.filter_by(barberia_id=barberia_id)
            for cf in q_fijos.all():
                if cf.telefono == telefono:
                    continue
                hora_fija_str = _chk_fijo(cf.horario_fijo, dia_semana)
                if hora_fija_str:
                    t_fijo = datetime.strptime(hora_fija_str, "%H:%M").time()
                    if t_fijo == hora:
                        return False, "❌ Ese horario está reservado para un cliente habitual. Por favor elige otro."
        except Exception as e:
            print(f"⚠ Error verificando fijos en crear_cita: {e}")

        # ── Crear cita ────────────────────────────────────────────────────────
        nueva = Cita(
            cliente_id  = cliente.id,
            barbero_id  = int(barbero_id),
            fecha       = fecha,
            hora        = hora,
            servicio    = servicio,
            barberia_id = barberia_id,
        )
        db.session.add(nueva)
        db.session.commit()
        return True, "✅ Cita creada correctamente."

    except IntegrityError:
        db.session.rollback()
        return False, "❌ Ese horario ya está ocupado. Por favor elige otro."
    except Exception as e:
        db.session.rollback()
        return False, f"Error al crear cita: {str(e)}"


# ------------------------------------------------
# CANCELAR CITA
# ------------------------------------------------

def cancelar_cita(telefono, fecha, hora, barberia_id=None):
    try:
        fecha = normalizar_fecha(fecha)
        hora  = normalizar_hora(hora)

        cliente = _buscar_cliente(telefono, barberia_id)
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
        es_turno_fijo       = (cita.servicio or "").startswith("📌")

        if es_turno_fijo:
            cita.estado = "cancelada"
            db.session.flush()
            # Cancelar también todas las citas "📌 Turno fijo" futuras del mismo cliente
            hoy = (datetime.utcnow() - timedelta(hours=5)).date()
            Cita.query.filter(
                Cita.cliente_id == cliente.id,
                Cita.fecha >= hoy,
                Cita.estado != "cancelada",
                Cita.servicio == "📌 Turno fijo",
            ).update({"estado": "cancelada"}, synchronize_session=False)
            db.session.commit()
        else:
            db.session.delete(cita)
            db.session.commit()

        if not es_turno_fijo:
            try:
                from app.services.lista_espera_service import notificar_lista_espera
                notificar_lista_espera(barbero_id_guardado, fecha_guardada, barberia_id)
            except Exception:
                pass

        return True, "✅ Tu cita fue cancelada correctamente."

    except Exception as e:
        db.session.rollback()
        return False, f"Error cancelando cita: {str(e)}"


# ------------------------------------------------
# VER PRÓXIMA CITA
# ------------------------------------------------

def obtener_cita_cliente(telefono, barberia_id=None):
    cliente = _buscar_cliente(telefono, barberia_id)
    if not cliente:
        return None

    hoy = (datetime.utcnow() - timedelta(hours=5)).date()

    q = Cita.query.filter(
        Cita.cliente_id == cliente.id,
        Cita.fecha >= hoy,
        Cita.estado != "cancelada"
    )
    return q.order_by(Cita.fecha, Cita.hora).first()
