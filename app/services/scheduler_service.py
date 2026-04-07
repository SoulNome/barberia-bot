from apscheduler.schedulers.background import BackgroundScheduler
from datetime import date, datetime, timedelta

from app.models.cita import Cita
from app.models.cliente import Cliente
from app.extensions import db

from app.services.recordatorio_service import enviar_recordatorio


# ------------------------------------------------
# OBTENER CITAS DE MAÑANA
# ------------------------------------------------

def obtener_citas_de_manana():

    manana = (datetime.utcnow() - timedelta(hours=5)).date() + timedelta(days=1)

    citas = Cita.query.filter(
        Cita.fecha == manana,
        Cita.estado == "confirmada"
    ).all()

    lista = []

    for cita in citas:

        cliente = Cliente.query.get(cita.cliente_id)

        if not cliente:
            continue

        lista.append({
            "telefono": cliente.telefono,
            "nombre": cliente.nombre,
            "fecha": cita.fecha.strftime("%Y-%m-%d"),
            "hora": cita.hora.strftime("%H:%M")
        })

    return lista


# ------------------------------------------------
# ENVIAR RECORDATORIOS
# ------------------------------------------------

def enviar_recordatorios(app):

    with app.app_context():

        print("📅 Buscando citas para enviar recordatorios...")

        citas = obtener_citas_de_manana()

        enviados = 0

        for cita in citas:

            ok = enviar_recordatorio(
                cita["telefono"],
                cita["nombre"],
                cita["fecha"],
                cita["hora"]
            )

            if ok:
                enviados += 1

        print(f"📲 Recordatorios enviados: {enviados}")


# ------------------------------------------------
# INICIAR SCHEDULER
# ------------------------------------------------

def enviar_recordatorios_fijos(app):
    with app.app_context():
        from app.services.recordatorio_service import enviar_recordatorio_fijo
        clientes = Cliente.query.filter_by(fijo=True).all()
        enviados = 0
        for c in clientes:
            if c.telefono and c.horario_fijo:
                ok = enviar_recordatorio_fijo(c.telefono, c.nombre, c.horario_fijo)
                if ok:
                    enviados += 1
        print(f"📲 Recordatorios fijos enviados: {enviados}/{len(clientes)}")


def crear_citas_fijos(app):
    """
    Crea citas reales en la BD para clientes fijos para la semana en curso.
    Se ejecuta cada lunes. Así los clientes fijos pueden usar el flujo
    normal de reagendar/cancelar y sus turnos quedan protegidos en la BD.
    """
    with app.app_context():
        from app.models.barbero import Barbero
        from app.services.disponibilidad_service import _parsear_horario_fijo, FESTIVOS

        barbero_default = Barbero.query.order_by(Barbero.id).first()
        if not barbero_default:
            print("⚠ No hay barberos registrados, no se crean citas fijas")
            return

        hoy = (datetime.utcnow() - timedelta(hours=5)).date()
        clientes_fijos = Cliente.query.filter_by(fijo=True).all()
        creadas = 0
        confirmaciones = []

        for cf in clientes_fijos:
            if not cf.horario_fijo or not cf.telefono:
                continue

            for dias_ahead in range(7):
                fecha_cita = hoy + timedelta(days=dias_ahead)
                fecha_str = fecha_cita.strftime("%Y-%m-%d")

                # Saltar festivos y domingos
                if fecha_cita.weekday() == 6 or fecha_str in FESTIVOS:
                    continue

                dia_semana = fecha_cita.weekday()
                hora_str = _parsear_horario_fijo(cf.horario_fijo, dia_semana)
                if not hora_str:
                    continue

                hora = datetime.strptime(hora_str, "%H:%M").time()

                # No crear si ya existe la cita fija exacta del cliente
                ya_existe = Cita.query.filter_by(
                    cliente_id=cf.id,
                    fecha=fecha_cita,
                    hora=hora
                ).first()
                if ya_existe:
                    continue

                # No crear si el cliente ya reagendó a otro horario ese día
                # (evita duplicados cuando la cita fija fue cancelada por reagenda)
                reagendo = Cita.query.filter(
                    Cita.cliente_id == cf.id,
                    Cita.fecha == fecha_cita,
                    Cita.hora != hora
                ).first()
                if reagendo:
                    continue

                # No crear si el slot fue tomado por otro cliente
                conflicto = Cita.query.filter_by(
                    barbero_id=barbero_default.id,
                    fecha=fecha_cita,
                    hora=hora
                ).first()
                if conflicto:
                    print(f"⚠ Slot fijo {cf.nombre} {fecha_str} {hora_str} ocupado por otro cliente")
                    continue

                nueva = Cita(
                    cliente_id=cf.id,
                    barbero_id=barbero_default.id,
                    fecha=fecha_cita,
                    hora=hora,
                    servicio="📌 Turno fijo"
                )
                db.session.add(nueva)
                creadas += 1
                confirmaciones.append((cf.telefono, cf.nombre, fecha_str, hora_str))

        try:
            db.session.commit()
            print(f"📌 Citas fijas creadas: {creadas}")
        except Exception as e:
            db.session.rollback()
            print(f"⚠ Error creando citas fijas: {e}")
            return

        # Enviar confirmación a cada cliente por cita creada
        from app.services.recordatorio_service import _enviar_whatsapp
        DIAS_ES = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
        for telefono, nombre, fecha_str, hora_str in confirmaciones:
            try:
                fecha_obj = datetime.strptime(fecha_str, "%Y-%m-%d")
                dia_nombre = DIAS_ES[fecha_obj.weekday()]
                texto = (
                    f"💈 *BarberIA*\n\n"
                    f"Hola {nombre} 👋\n\n"
                    f"✅ Tu turno de esta semana está confirmado:\n\n"
                    f"📅 {dia_nombre} {fecha_obj.day}\n"
                    f"⏰ {hora_str}\n\n"
                    f"Si necesitas cambiar la hora escribe *reagendar*.\n\n"
                    f"¡Te esperamos!"
                )
                _enviar_whatsapp(telefono, texto)
            except Exception as e:
                print(f"⚠ Error enviando confirmación a {telefono}: {e}")


def iniciar_scheduler(app):

    scheduler = BackgroundScheduler()

    # Recordatorio citas de mañana — cada día a las 18:00 UTC (13:00 Colombia)
    scheduler.add_job(
        enviar_recordatorios,
        "cron",
        hour=18,
        minute=0,
        args=[app]
    )

    # Crear citas reales para clientes fijos — cada día a las 11:00 UTC (06:00 Colombia)
    # Corre diariamente para garantizar que los turnos fijos estén siempre en BD
    scheduler.add_job(
        crear_citas_fijos,
        "cron",
        hour=11,
        minute=0,
        args=[app]
    )

    # Recordatorio clientes fijos — cada lunes a las 13:00 UTC (08:00 Colombia)
    scheduler.add_job(
        enviar_recordatorios_fijos,
        "cron",
        day_of_week="mon",
        hour=13,
        minute=0,
        args=[app]
    )

    scheduler.start()

    print("⏰ Scheduler de recordatorios iniciado")