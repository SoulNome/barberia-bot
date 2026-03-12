from flask import Blueprint, request, render_template
from app.models import Cita, Cliente, Barbero
from datetime import date, datetime, time, timedelta
import os

panel_bp = Blueprint("panel", __name__)

PANEL_KEY = os.getenv("PANEL_KEY")


@panel_bp.route("/panel")
def panel():

    key = request.args.get("key")

    if key != PANEL_KEY:
        return "No autorizado"

    hoy = date.today()

    citas = Cita.query.filter_by(fecha=hoy).all()

    citas_hoy = len(citas)
    clientes = Cliente.query.count()
    barberos = Barbero.query.count()

    apertura = time(9,0)
    cierre = time(18,0)

    agenda = []

    actual = datetime.combine(hoy, apertura)

    while actual.time() < cierre:

        hora = actual.time()

        cita = next((c for c in citas if c.hora == hora), None)

        if cita:

            cliente = Cliente.query.get(cita.cliente_id)
            barbero = Barbero.query.get(cita.barbero_id)

            agenda.append((
                hora.strftime("%H:%M"),
                cliente.nombre,
                barbero.nombre
            ))

        else:

            agenda.append((
                hora.strftime("%H:%M"),
                None,
                None
            ))

        actual += timedelta(minutes=30)

    return render_template(
        "panel.html",
        agenda=agenda,
        citas_hoy=citas_hoy,
        clientes=clientes,
        barberos=barberos
    )