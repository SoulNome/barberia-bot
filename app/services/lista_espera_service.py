from app.extensions import db
from app.models.lista_espera import ListaEspera
from app.models.cliente import Cliente
from app.services.agenda_service import normalizar_fecha


# ------------------------------------------------
# AGREGAR A LISTA DE ESPERA
# ------------------------------------------------

def agregar_a_espera(telefono, barbero_id, fecha, servicio=None):
    """
    Inscribe al cliente en la lista de espera para una fecha/barbero.
    Evita duplicados: un cliente no puede estar dos veces para el mismo día.
    """
    try:
        cliente = Cliente.query.filter_by(telefono=telefono).first()
        if not cliente:
            return False, "No encontramos tu número en el sistema."

        fecha_obj = normalizar_fecha(fecha)

        # Evitar duplicado
        existente = ListaEspera.query.filter_by(
            cliente_id = cliente.id,
            barbero_id = barbero_id,
            fecha      = fecha_obj,
            notificado = False,
        ).first()

        if existente:
            return False, "Ya estás en la lista de espera para ese día."

        entrada = ListaEspera(
            cliente_id = cliente.id,
            barbero_id = barbero_id,
            fecha      = fecha_obj,
            servicio   = servicio,
        )
        db.session.add(entrada)
        db.session.commit()
        return True, "Anotado en lista de espera."

    except Exception as e:
        db.session.rollback()
        return False, str(e)


# ------------------------------------------------
# NOTIFICAR LISTA DE ESPERA
# Llamar cuando se cancela una cita
# ------------------------------------------------

def notificar_lista_espera(barbero_id, fecha):
    """
    Busca el primer cliente en espera para ese barbero/fecha
    y le envía un WhatsApp avisando que hay turno disponible.
    Marca la entrada como notificada.
    """
    try:
        from app.services.recordatorio_service import _enviar_whatsapp

        entrada = ListaEspera.query.filter_by(
            barbero_id = barbero_id,
            fecha      = fecha,
            notificado = False,
        ).order_by(ListaEspera.creado_en.asc()).first()

        if not entrada:
            return

        cliente = Cliente.query.get(entrada.cliente_id)
        if not cliente or not cliente.telefono:
            return

        from app.models.barbero import Barbero
        barbero = Barbero.query.get(barbero_id)

        import locale
        DIAS_ES  = ["lunes","martes","miércoles","jueves","viernes","sábado","domingo"]
        MESES_ES = ["enero","febrero","marzo","abril","mayo","junio",
                    "julio","agosto","septiembre","octubre","noviembre","diciembre"]
        f = entrada.fecha
        fecha_bonita = f"{DIAS_ES[f.weekday()]} {f.day} de {MESES_ES[f.month-1]}"

        msg = (
            f"🔔 *¡Se liberó un turno!*\n\n"
            f"Hola {cliente.nombre} 👋\n\n"
            f"Se canceló una cita para:\n"
            f"📅 {fecha_bonita}\n"
            f"{'💈 ' + barbero.nombre if barbero else ''}\n\n"
            f"Escribe *1* para agendar antes de que se llene."
        )

        ok = _enviar_whatsapp(cliente.telefono, msg)

        if ok:
            entrada.notificado = True
            db.session.commit()

    except Exception as e:
        print(f"⚠ Error notificando lista de espera: {e}")
