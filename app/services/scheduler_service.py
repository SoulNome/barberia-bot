from apscheduler.schedulers.background import BackgroundScheduler
from app.extensions import db
from app.models import Cita, Cliente
from datetime import datetime, timedelta


def enviar_recordatorios_fijos(app):
    with app.app_context():
        from app.models.barberia import Barberia
        from app.services.recordatorio_service import enviar_recordatorio_fijo

        for barberia in Barberia.query.all():
            clientes = Cliente.query.filter_by(fijo=True, barberia_id=barberia.id).all()
            enviados = 0
            for c in clientes:
                if c.telefono and c.horario_fijo:
                    ok = enviar_recordatorio_fijo(c.telefono, c.nombre, c.horario_fijo, barberia)
                    if ok:
                        enviados += 1
            if clientes:
                print(f"📲 [{barberia.nombre}] Recordatorios fijos enviados: {enviados}/{len(clientes)}")


def crear_citas_fijos(app):
    """
    Crea citas reales en la BD para clientes fijos de cada barbería.
    Se ejecuta diariamente. Itera por barbería para respetar el aislamiento multi-tenant.
    """
    with app.app_context():
        from app.models.barbero import Barbero
        from app.models.barberia import Barberia
        from app.services.disponibilidad_service import _parsear_horario_fijo, FESTIVOS

        hoy = (datetime.utcnow() - timedelta(hours=5)).date()

        for barberia in Barberia.query.all():

            barbero_default = Barbero.query.filter_by(
                barberia_id=barberia.id
            ).order_by(Barbero.id).first()

            if not barbero_default:
                continue

            clientes_fijos = Cliente.query.filter_by(fijo=True, barberia_id=barberia.id).all()
            creadas = 0

            for cf in clientes_fijos:
                if not cf.horario_fijo or not cf.telefono:
                    continue

                for dias_ahead in range(7):
                    fecha_cita = hoy + timedelta(days=dias_ahead)
                    fecha_str  = fecha_cita.strftime("%Y-%m-%d")

                    if fecha_cita.weekday() == 6 or fecha_str in FESTIVOS:
                        continue

                    dia_semana = fecha_cita.weekday()
                    hora_str   = _parsear_horario_fijo(cf.horario_fijo, dia_semana)
                    if not hora_str:
                        continue

                    hora = datetime.strptime(hora_str, "%H:%M").time()

                    ya_existe = Cita.query.filter_by(
                        cliente_id=cf.id,
                        fecha=fecha_cita,
                        hora=hora
                    ).first()

                    if ya_existe:
                        if ya_existe.estado == "cancelada":
                            hoy_co = (datetime.utcnow() - timedelta(hours=5)).date()
                            if fecha_cita >= hoy_co:
                                continue
                            else:
                                db.session.delete(ya_existe)
                                db.session.flush()
                        else:
                            continue

                    # No crear si el cliente ya reagendó ese día
                    reagendo = Cita.query.filter(
                        Cita.cliente_id == cf.id,
                        Cita.fecha == fecha_cita,
                        Cita.hora != hora,
                        Cita.estado != "cancelada"
                    ).first()
                    if reagendo:
                        continue

                    # No crear si el slot fue tomado por otro
                    conflicto = Cita.query.filter(
                        Cita.barbero_id == barbero_default.id,
                        Cita.fecha == fecha_cita,
                        Cita.hora == hora,
                        Cita.estado != "cancelada"
                    ).first()
                    if conflicto:
                        print(f"⚠ [{barberia.nombre}] Slot fijo {cf.nombre} {fecha_str} {hora_str} ocupado")
                        continue

                    nueva = Cita(
                        cliente_id  = cf.id,
                        barbero_id  = barbero_default.id,
                        fecha       = fecha_cita,
                        hora        = hora,
                        servicio    = "📌 Turno fijo",
                        barberia_id = barberia.id,
                    )
                    db.session.add(nueva)
                    creadas += 1

            try:
                db.session.commit()
                if creadas:
                    print(f"📌 [{barberia.nombre}] Citas fijas creadas: {creadas}")
            except Exception as e:
                db.session.rollback()
                print(f"⚠ [{barberia.nombre}] Error creando citas fijas: {e}")


def iniciar_scheduler(app):
    scheduler = BackgroundScheduler()

    # Recordatorios diarios a las 08:00 Colombia (13:00 UTC)
    scheduler.add_job(
        enviar_recordatorios_fijos,
        "cron",
        hour=13,
        minute=0,
        args=[app]
    )

    # Crear citas fijos — cada día a las 06:00 Colombia (11:00 UTC)
    scheduler.add_job(
        crear_citas_fijos,
        "cron",
        hour=11,
        minute=0,
        args=[app]
    )

    # Recordatorio clientes fijos — cada lunes a las 08:00 Colombia (13:00 UTC)
    scheduler.add_job(
        enviar_recordatorios_fijos,
        "cron",
        day_of_week="mon",
        hour=13,
        minute=0,
        args=[app]
    )

    scheduler.start()
    print("⏰ Scheduler iniciado")
