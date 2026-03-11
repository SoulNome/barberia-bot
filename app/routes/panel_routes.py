from flask import Blueprint, request
from app.models import Cita, Cliente, Barbero
from datetime import date
import os

panel_bp = Blueprint("panel", __name__)

PANEL_KEY = os.getenv("PANEL_KEY")


@panel_bp.route("/panel")
def panel():

    key = request.args.get("key")

    if key != PANEL_KEY:
        return "No autorizado"

    citas = Cita.query.order_by(Cita.fecha.asc()).all()

    citas_hoy = Cita.query.filter_by(fecha=date.today()).count()
    clientes = Cliente.query.count()
    barberos = Barbero.query.count()

    html = f"""
<!DOCTYPE html>
<html>
<head>

<title>BarberIA Dashboard</title>

<style>

body {{
    font-family: 'Segoe UI', sans-serif;
    background: #0f172a;
    color: white;
    margin: 0;
}}

.container {{
    width: 1100px;
    margin: auto;
    padding-top: 40px;
}}

h1 {{
    text-align: center;
    margin-bottom: 40px;
}}

.stats {{
    display: flex;
    gap: 20px;
    margin-bottom: 40px;
}}

.card {{
    flex: 1;
    background: linear-gradient(135deg,#1e293b,#334155);
    padding: 25px;
    border-radius: 12px;
    text-align: center;
    box-shadow: 0 10px 25px rgba(0,0,0,0.3);
    transition: 0.3s;
}}

.card:hover {{
    transform: translateY(-5px);
}}

.card h2 {{
    font-size: 40px;
    margin: 10px 0;
}}

.card p {{
    color: #cbd5f5;
}}

table {{
    width: 100%;
    border-collapse: collapse;
    background: #1e293b;
    border-radius: 12px;
    overflow: hidden;
    box-shadow: 0 10px 30px rgba(0,0,0,0.3);
}}

th {{
    background: #334155;
    padding: 15px;
}}

td {{
    padding: 14px;
}}

tr:nth-child(even) {{
    background: #0f172a;
}}

tr:hover {{
    background: #334155;
}}

.header-bar {{
    display:flex;
    justify-content:space-between;
    margin-bottom:20px;
}}

.badge {{
    background:#22c55e;
    padding:4px 10px;
    border-radius:6px;
    font-size:12px;
}}

</style>

</head>

<body>

<div class="container">

<h1>💈 BarberIA Dashboard</h1>

<div class="stats">

<div class="card">
<p>Citas hoy</p>
<h2>{citas_hoy}</h2>
</div>

<div class="card">
<p>Clientes</p>
<h2>{clientes}</h2>
</div>

<div class="card">
<p>Barberos</p>
<h2>{barberos}</h2>
</div>

</div>

<div class="header-bar">
<h2>📅 Agenda de citas</h2>
<span class="badge">Sistema activo</span>
</div>

<table>

<tr>
<th>Cliente</th>
<th>Barbero</th>
<th>Fecha</th>
<th>Hora</th>
</tr>
"""

    for cita in citas:

        cliente = Cliente.query.get(cita.cliente_id)
        barbero = Barbero.query.get(cita.barbero_id)

        html += f"""
<tr>
<td>{cliente.nombre}</td>
<td>{barbero.nombre}</td>
<td>{cita.fecha}</td>
<td>{cita.hora}</td>
</tr>
"""

    html += """
</table>

</div>

</body>
</html>
"""

    return html