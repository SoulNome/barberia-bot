from apscheduler.schedulers.background import BackgroundScheduler
from datetime import date, timedelta

from app.models.cita import Cita
from app.models.cliente import Cliente
from app.extensions import db

from app.services.recordatorio_service import enviar_recordatorio


# ------------------------------------------------
# OBTENER CITAS DE MAÑANA
# ------------------------------------------------

def obtener_citas_de_manana():

    manana = date.today() + timedelta(days=1)

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