from app.extensions import db
from app.models.lista_espera import ListaEspera
from app.models.cliente import Cliente
from app.services.agenda_service import normalizar_fecha


def agregar_a_espera(telefono, barbero_id, fecha, servicio=None, barberia_id=None):
    """
    Inscribe al cliente en la lista de espera para una fecha/barbero.
    Evita duplicados: un cliente no puede estar dos veces para el mismo día.
    """
    try:
        q = Cliente.query.filter_by(telefono=telefono)
        if barberia_id:
            q = q.filter_by(barberia_id=barberia_id)
        cliente = q.first()
        if not cliente:
            return False, "No encontramos tu número en el sistema."

        fecha_obj = normalizar_fecha(fecha)

        existente = ListaEspera.query.filter_by(
            cliente_id=cliente.id,
            barbero_id=barbero_id,
            fecha=fecha_obj,
            notificado=False,
        ).first()
        if existente:
            return False, "Ya estás en la lista de espera para ese día."

        entrada = ListaEspera(
            cliente_id  = cliente.id,
            barbero_id  = barbero_id,
            fecha       = fecha_obj,
            servicio    = servicio,
            barberia_id = barberia_id,
        )
        db.session.add(entrada)
        db.session.commit()
        return True, "Anotado en lista de espera."

    except Exception as e:
        db.session.rollback()
        return False, str(e)


def notificar_lista_espera(barbero_id, fecha, barberia_id=None, barberia=None, hora=None):
    """
    Busca el primer cliente en espera para ese barbero/fecha y le avisa.
    Si se pasa `hora`, se muestra en el mensaje y se pre-carga el estado del bot
    para que el cliente confirme con un solo '1' sin repetir el flujo.
    """
    try:
        from app.services.recordatorio_service import _enviar_whatsapp

        q = ListaEspera.query.filter_by(
            barbero_id=barbero_id,
            fecha=fecha,
            notificado=False,
        )
        if barberia_id:
            q = q.filter_by(barberia_id=barberia_id)
        entrada = q.order_by(ListaEspera.creado_en.asc()).first()

        if not entrada:
            return

        cliente = Cliente.query.get(entrada.cliente_id)
        if not cliente or not cliente.telefono:
            return

        from app.models.barbero import Barbero
        barbero_obj = Barbero.query.get(barbero_id)
        barbero_nombre = barbero_obj.nombre if barbero_obj else ""

        DIAS_ES  = ["lunes","martes","miércoles","jueves","viernes","sábado","domingo"]
        MESES_ES = ["enero","febrero","marzo","abril","mayo","junio",
                    "julio","agosto","septiembre","octubre","noviembre","diciembre"]
        f = entrada.fecha
        fecha_bonita = f"{DIAS_ES[f.weekday()]} {f.day} de {MESES_ES[f.month-1]}"

        # Formatear hora si viene
        hora_str = hora.strftime("%H:%M") if hora and hasattr(hora, "strftime") else str(hora) if hora else None

        if hora_str:
            msg = (
                f"🔔 *¡Se liberó un turno!*\n\n"
                f"Hola {cliente.nombre} 👋\n\n"
                f"Quedó disponible:\n"
                f"📅 {fecha_bonita}\n"
                f"⏰ {hora_str}\n"
                f"{'💈 ' + barbero_nombre if barbero_nombre else ''}\n\n"
                f"Responde *1* para tomarlo ahora ✅\n"
                f"Responde *2* para rechazarlo ❌\n\n"
                f"_Si no respondes en 30 minutos el turno se ofrecerá al siguiente._"
            )
        else:
            msg = (
                f"🔔 *¡Se liberó un turno!*\n\n"
                f"Hola {cliente.nombre} 👋\n\n"
                f"Se canceló una cita para:\n"
                f"📅 {fecha_bonita}\n"
                f"{'💈 ' + barbero_nombre if barbero_nombre else ''}\n\n"
                f"Responde *1* para agendar antes de que se llene."
            )

        ok = _enviar_whatsapp(cliente.telefono, msg, barberia)
        if ok:
            entrada.notificado = True
            db.session.commit()

            # Pre-cargar el estado del bot para confirmación directa con "1"
            if hora_str:
                try:
                    from app.services.state_service import set_state
                    set_state(cliente.telefono, {
                        "estado":         "espera_slot_ofrecido",
                        "barbero_id":     barbero_id,
                        "barbero_nombre": barbero_nombre,
                        "fecha":          str(fecha),
                        "hora":           hora_str,
                        "servicio":       entrada.servicio,
                        "nombre":         cliente.nombre,
                    }, barberia_id)
                except Exception as e:
                    print(f"⚠ No se pudo pre-cargar estado de espera: {e}")

    except Exception as e:
        print(f"⚠ Error notificando lista de espera: {e}")
