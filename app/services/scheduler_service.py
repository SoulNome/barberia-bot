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
            "fecha": cita.fecha,
            "hora": cita.hora
        })

    return lista


# ------------------------------------------------
# ENVIAR RECORDATORIOS
# ------------------------------------------------

def enviar_recordatorios():

    print("Buscando citas para enviar recordatorios...")

    citas = obtener_citas_de_manana()

    for cita in citas:

        enviar_recordatorio(
            cita["telefono"],
            cita["nombre"],
            cita["fecha"],
            cita["hora"]
        )

    print(f"Recordatorios enviados: {len(citas)}")


# ------------------------------------------------
# INICIAR SCHEDULER
# ------------------------------------------------

def iniciar_scheduler():

    scheduler = BackgroundScheduler()

    # todos los días a las 18:00
    scheduler.add_job(
        enviar_recordatorios,
        "cron",
        hour=18,
        minute=0
    )

    scheduler.start()

    print("Scheduler de recordatorios iniciado")