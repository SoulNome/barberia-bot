from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
import requests
from app.services.recordatorio_service import enviar_recordatorio


scheduler = BackgroundScheduler()


def revisar_citas():

    mañana = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

    r = requests.get(f"http://localhost:5000/agenda/citas?fecha={mañana}")

    citas = r.json()

    for cita in citas:

        enviar_recordatorio(
            cita["telefono"],
            cita["nombre"],
            cita["fecha"],
            cita["hora"]
        )


def iniciar_scheduler():

    scheduler.add_job(revisar_citas, 'interval', hours=1)

    scheduler.start()