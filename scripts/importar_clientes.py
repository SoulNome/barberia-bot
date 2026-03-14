"""
Script para importar clientes a la base de datos.
Uso: python scripts/importar_clientes.py

Llena la lista CLIENTES con los datos reales antes de ejecutar.
Formato de fecha_cumpleanos: "YYYY-MM-DD" o "" si no aplica
Formato de fijo: True / False
Formato de horario_fijo: "Lunes 10:00" o "" si no aplica
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from app import create_app, db
from app.models.cliente import Cliente
from datetime import datetime

# -------------------------------------------------------
# LLENA AQUÍ LOS CLIENTES
# -------------------------------------------------------

CLIENTES = [
    # {
    #     "nombre":           "Juan Pérez",
    #     "telefono":         "+573001234567",
    #     "fecha_cumpleanos": "1990-05-14",
    #     "fijo":             True,
    #     "horario_fijo":     "Lunes 10:00",
    # },
    # {
    #     "nombre":           "Carlos López",
    #     "telefono":         "+573009876543",
    #     "fecha_cumpleanos": "",
    #     "fijo":             False,
    #     "horario_fijo":     "",
    # },
]

# -------------------------------------------------------

def importar():

    app = create_app()

    with app.app_context():

        insertados  = 0
        omitidos    = 0
        errores     = 0

        for datos in CLIENTES:

            telefono = datos.get("telefono", "").strip()

            if not telefono:
                print(f"  ⚠ Fila sin teléfono, omitida: {datos.get('nombre')}")
                omitidos += 1
                continue

            existente = Cliente.query.filter_by(telefono=telefono).first()

            if existente:
                print(f"  → Ya existe: {datos['nombre']} ({telefono})")
                omitidos += 1
                continue

            try:

                fecha_cumple = None
                raw_fecha    = datos.get("fecha_cumpleanos", "").strip()

                if raw_fecha:
                    fecha_cumple = datetime.strptime(raw_fecha, "%Y-%m-%d").date()

                cliente = Cliente(
                    nombre           = datos["nombre"].strip(),
                    telefono         = telefono,
                    fecha_cumpleanos = fecha_cumple,
                    fijo             = bool(datos.get("fijo", False)),
                    horario_fijo     = datos.get("horario_fijo", "").strip() or None,
                )

                db.session.add(cliente)
                db.session.commit()

                fijo_txt = f" | Fijo: {datos.get('horario_fijo')}" if datos.get("fijo") else ""
                print(f"  ✅ Importado: {datos['nombre']} ({telefono}){fijo_txt}")
                insertados += 1

            except Exception as e:
                db.session.rollback()
                print(f"  ❌ Error con {datos.get('nombre')}: {e}")
                errores += 1

        print(f"\n{'─'*40}")
        print(f"  Insertados : {insertados}")
        print(f"  Omitidos   : {omitidos}")
        print(f"  Errores    : {errores}")
        print(f"  Total      : {len(CLIENTES)}")
        print(f"{'─'*40}")


if __name__ == "__main__":
    importar()
