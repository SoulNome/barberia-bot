from flask import Blueprint, request, render_template
from app.models import Cita, Cliente, Barbero
from datetime import date, datetime, time, timedelta
import os

panel_bp = Blueprint("panel", __name__)

PANEL_KEY = os.getenv("PANEL_KEY")


# ------------------------------------------------
# PRECIOS SERVICIOS
# ------------------------------------------------

PRECIOS = {
    "Corte niños": 15000,
    "Corte normal": 20000,
    "Corte + barba + tinte": 25000,
    "Corte + barba + tinte + alisadora": 30000,
    "Pigmentación cejas": 10000
}


# ------------------------------------------------
# HORARIOS POR DIA
# ------------------------------------------------

def obtener_horarios_dia(dia_semana):

    if dia_semana in [0,1,2]:
        return [
            (time(10,0), time(12,0)),
            (time(16,0), time(20,0))
        ]

    if dia_semana == 3:
        return [
            (time(10,0), time(12,30)),
            (time(15,0), time(22,0))
        ]

    if dia_semana == 4:
        return [
            (time(9,0), time(13,30)),
            (time(14,30), time(22,0))
        ]

    if dia_semana == 5:
        return [
            (time(9,0), time(13,0)),
            (time(15,0), time(21,0))
        ]

    return []


# ------------------------------------------------
# PANEL
# ------------------------------------------------

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

    clientes_dict = {c.id: c.nombre for c in Cliente.query.all()}
    barberos_dict = {b.id: b.nombre for b in Barbero.query.all()}

    # ------------------------------------------------
    # CALCULAR INGRESOS
    # ------------------------------------------------

    ingresos_hoy = 0

    for cita in citas:
        if cita.servicio in PRECIOS:
            ingresos_hoy += PRECIOS[cita.servicio]

    agenda = []

    dia_semana = hoy.weekday()

    bloques = obtener_horarios_dia(dia_semana)

    for inicio, fin in bloques:

        actual = datetime.combine(hoy, inicio)

        while actual.time() < fin:

            hora = actual.time()

            cita = next((c for c in citas if c.hora == hora), None)

            if cita:

                cliente_nombre = clientes_dict.get(cita.cliente_id)
                barbero_nombre = barberos_dict.get(cita.barbero_id)

                agenda.append({
                    "hora": hora.strftime("%H:%M"),
                    "cliente": cliente_nombre,
                    "barbero": barbero_nombre,
                    "servicio": cita.servicio
                })

            else:

                agenda.append({
                    "hora": hora.strftime("%H:%M"),
                    "cliente": None,
                    "barbero": None,
                    "servicio": None
                })

            actual += timedelta(minutes=30)

    return render_template(
        "panel.html",
        agenda=agenda,
        citas_hoy=citas_hoy,
        clientes=clientes,
        barberos=barberos,
        ingresos_hoy=ingresos_hoy
    )