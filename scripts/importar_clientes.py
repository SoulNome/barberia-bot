"""
Script para importar clientes a la base de datos.
Ejecución local: python scripts/importar_clientes.py
Ejecución Railway: POST /run-import?key=PANEL_KEY

Nota: el año en fecha_cumpleanos es 2000 (placeholder).
Solo importa mes y día para el check de cumpleaños.
"""

import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

CLIENTES = [
    {"nombre": "Dago Ladino",                      "telefono": "+573163380844", "fecha_cumpleanos": "2000-08-11", "fijo": True,  "horario_fijo": "Martes 8:00pm y viernes 5:00pm"},
    {"nombre": "Jaime Olaya",                       "telefono": "+573188711359", "fecha_cumpleanos": "2000-07-13", "fijo": False, "horario_fijo": ""},
    {"nombre": "Daniel Rodriguez",                  "telefono": "+573104995590", "fecha_cumpleanos": "2000-04-11", "fijo": True,  "horario_fijo": "Sabados 12:00pm"},
    {"nombre": "Jersson Solis",                     "telefono": "+573003829620", "fecha_cumpleanos": "2000-07-21", "fijo": True,  "horario_fijo": "Sabados 5:30"},
    {"nombre": "Diego Villada",                     "telefono": "+573147471972", "fecha_cumpleanos": "2000-08-08", "fijo": True,  "horario_fijo": "Viernes 10:00am"},
    {"nombre": "Maicol Garcia",                     "telefono": "+573153708637", "fecha_cumpleanos": "2000-07-17", "fijo": False, "horario_fijo": ""},
    {"nombre": "Cristian Gomez",                    "telefono": "+573172183955", "fecha_cumpleanos": "2000-09-09", "fijo": True,  "horario_fijo": "Miercoles 6:00am y Sabados 6:30pm"},
    {"nombre": "Diego Fernando Camacho Lenis",      "telefono": "+573183858967", "fecha_cumpleanos": "2000-04-30", "fijo": False, "horario_fijo": ""},
    {"nombre": "Willian Andres Marin",              "telefono": "+573166735250", "fecha_cumpleanos": "2000-08-15", "fijo": False, "horario_fijo": ""},
    {"nombre": "Hector Fabio Agudelo",              "telefono": "+573173640871", "fecha_cumpleanos": "2000-04-07", "fijo": False, "horario_fijo": ""},
    {"nombre": "James Garcia",                      "telefono": "+573188511109", "fecha_cumpleanos": "2000-10-28", "fijo": False, "horario_fijo": ""},
    {"nombre": "Jader Murcia",                      "telefono": "+573206307808", "fecha_cumpleanos": "2000-11-12", "fijo": False, "horario_fijo": ""},
    {"nombre": "Jhon Humberto Rios",                "telefono": "+573182183041", "fecha_cumpleanos": "2000-01-23", "fijo": True,  "horario_fijo": "Lunes 6:00pm"},
    {"nombre": "Juan Diego Morales Sanchez",        "telefono": "+573027713336", "fecha_cumpleanos": "2000-05-18", "fijo": False, "horario_fijo": ""},
    {"nombre": "Jesus Morales",                     "telefono": "+573124504053", "fecha_cumpleanos": "2000-05-12", "fijo": False, "horario_fijo": ""},
    {"nombre": "Victor Pirry",                      "telefono": "+573026289004", "fecha_cumpleanos": "2000-10-22", "fijo": False, "horario_fijo": ""},
    {"nombre": "Victor Manuel Barandica",           "telefono": "+573193901406", "fecha_cumpleanos": "2000-03-23", "fijo": False, "horario_fijo": ""},
    {"nombre": "Julian Echeverry",                  "telefono": "+573152283729", "fecha_cumpleanos": "2000-08-26", "fijo": False, "horario_fijo": ""},
    {"nombre": "Ronald Rodriguez Mora",             "telefono": "+573217745683", "fecha_cumpleanos": "2000-03-05", "fijo": False, "horario_fijo": ""},
    {"nombre": "Carlos Mario Hoyos",                "telefono": "+573187128980", "fecha_cumpleanos": "2000-06-16", "fijo": False, "horario_fijo": ""},
    {"nombre": "Antonio Gomez",                     "telefono": "+573153200706", "fecha_cumpleanos": "2000-10-21", "fijo": False, "horario_fijo": ""},
    {"nombre": "Anderson Ceballos",                 "telefono": "+573127805726", "fecha_cumpleanos": "2000-06-15", "fijo": True,  "horario_fijo": "Cada sabado 15 dias 4:30pm"},
    {"nombre": "Alejandro Serna Rudas",             "telefono": "+573147778792", "fecha_cumpleanos": "2000-12-28", "fijo": True,  "horario_fijo": "Viernes 12:30pm"},
    {"nombre": "David Nieto",                       "telefono": "+573144288159", "fecha_cumpleanos": "2000-05-22", "fijo": True,  "horario_fijo": "Viernes 1:00pm"},
    {"nombre": "Luis Fernando Perez Trejos",        "telefono": "+573171310902", "fecha_cumpleanos": "2000-02-02", "fijo": False, "horario_fijo": ""},
    {"nombre": "Victor Hugo Lozano Santa",          "telefono": "+573163897824", "fecha_cumpleanos": "2000-11-29", "fijo": True,  "horario_fijo": "Sabados 10:30am"},
    {"nombre": "Hugo Cuenu",                        "telefono": "+573243263220", "fecha_cumpleanos": "2000-09-13", "fijo": False, "horario_fijo": ""},
    {"nombre": "Esteban Ocampo",                    "telefono": "+573106113047", "fecha_cumpleanos": "2000-08-12", "fijo": False, "horario_fijo": ""},
    {"nombre": "Jhorman Arce",                      "telefono": "+573162397308", "fecha_cumpleanos": "2000-02-23", "fijo": False, "horario_fijo": ""},
    {"nombre": "Liberman Lopez Chacon",             "telefono": "+573163403434", "fecha_cumpleanos": "2000-12-29", "fijo": False, "horario_fijo": ""},
    {"nombre": "Santiago Quintero",                 "telefono": "+573178379550", "fecha_cumpleanos": "2000-09-22", "fijo": True,  "horario_fijo": "Sabados 11:00am"},
    {"nombre": "Victor Lenis",                      "telefono": "+573186020025", "fecha_cumpleanos": "2000-06-02", "fijo": False, "horario_fijo": "Cada viernes 15 dias 9:00pm"},
    {"nombre": "Victor Barandica",                  "telefono": "+573188686036", "fecha_cumpleanos": "2000-08-14", "fijo": False, "horario_fijo": ""},
    {"nombre": "Carlos Andres Gutierrez",           "telefono": "+573172183279", "fecha_cumpleanos": "2000-12-08", "fijo": False, "horario_fijo": ""},
    {"nombre": "Wilmar Suarez Villamil",            "telefono": "+573225705269", "fecha_cumpleanos": "2000-08-04", "fijo": False, "horario_fijo": ""},
    {"nombre": "Wener Sierra Beltran",              "telefono": "+573186637199", "fecha_cumpleanos": "2000-01-05", "fijo": False, "horario_fijo": ""},
    {"nombre": "Andres Jaramillo",                  "telefono": "+573127012740", "fecha_cumpleanos": "2000-06-17", "fijo": True,  "horario_fijo": "Sabado 4:00pm"},
    {"nombre": "Faber Alexis Solis",                "telefono": "+573217164525", "fecha_cumpleanos": "2000-06-11", "fijo": False, "horario_fijo": ""},
    {"nombre": "Cristian Jaramillo Marin",          "telefono": "+573136909984", "fecha_cumpleanos": "2000-08-18", "fijo": False, "horario_fijo": ""},
    {"nombre": "Jacobo Garcia",                     "telefono": "+573205876551", "fecha_cumpleanos": "2000-12-10", "fijo": False, "horario_fijo": ""},
    {"nombre": "Julian Romero",                     "telefono": "+573104479749", "fecha_cumpleanos": "2000-03-07", "fijo": False, "horario_fijo": ""},
    {"nombre": "Alex Velasco",                      "telefono": "+573163849192", "fecha_cumpleanos": "2000-08-03", "fijo": False, "horario_fijo": ""},
    {"nombre": "Mateo Corrales",                    "telefono": "+573246860436", "fecha_cumpleanos": "2000-09-24", "fijo": False, "horario_fijo": "Cada viernes 15 dias 6:30"},
    {"nombre": "Brayan Hurtado",                    "telefono": "+573218101812", "fecha_cumpleanos": "2000-12-23", "fijo": False, "horario_fijo": ""},
    {"nombre": "Gustavo Alzate",                    "telefono": "+573152433934", "fecha_cumpleanos": "2000-04-18", "fijo": True,  "horario_fijo": "Viernes 12:00pm"},
    {"nombre": "Ronald",                            "telefono": "+573216620460", "fecha_cumpleanos": "2000-03-19", "fijo": False, "horario_fijo": ""},
    {"nombre": "Oscar Andres Morales",              "telefono": "+573234120640", "fecha_cumpleanos": "2000-04-28", "fijo": False, "horario_fijo": ""},
    {"nombre": "Jhojan Serna",                      "telefono": "+573182079231", "fecha_cumpleanos": "2000-04-02", "fijo": False, "horario_fijo": ""},
    {"nombre": "Yuliana Leon Correa",               "telefono": "+573213975246", "fecha_cumpleanos": "2000-01-08", "fijo": False, "horario_fijo": ""},
    {"nombre": "Fransisco Jose Azocar Aviles",      "telefono": "+573157295365", "fecha_cumpleanos": "2000-10-23", "fijo": False, "horario_fijo": ""},
    {"nombre": "Jhon Jairo Quiñones",               "telefono": "+573233450622", "fecha_cumpleanos": "2000-12-26", "fijo": False, "horario_fijo": ""},
    {"nombre": "Andres Trejos",                     "telefono": "+573185110913", "fecha_cumpleanos": "2000-09-18", "fijo": False, "horario_fijo": ""},
    {"nombre": "Jonnier Garcia",                    "telefono": "+573167962463", "fecha_cumpleanos": "2000-10-27", "fijo": False, "horario_fijo": ""},
    {"nombre": "Diana Carolina Salamanca Lopez",    "telefono": "+573182670906", "fecha_cumpleanos": "2000-02-13", "fijo": False, "horario_fijo": ""},
    {"nombre": "Martha Cecilia Lopez Rojas",        "telefono": "+573136168702", "fecha_cumpleanos": "2000-09-04", "fijo": False, "horario_fijo": ""},
    {"nombre": "Wilfredo Salamanca",                "telefono": "+573145525373", "fecha_cumpleanos": "2000-09-14", "fijo": False, "horario_fijo": ""},
    {"nombre": "Fredy Alban Carvajal",              "telefono": "+573123018857", "fecha_cumpleanos": "2000-09-17", "fijo": False, "horario_fijo": ""},
    {"nombre": "Juan David Villota",                "telefono": "+573155940554", "fecha_cumpleanos": "2000-01-09", "fijo": True,  "horario_fijo": "Viernes 11:00am"},
    {"nombre": "Kaiser",                            "telefono": "+573185639829", "fecha_cumpleanos": "2000-04-25", "fijo": False, "horario_fijo": ""},
    {"nombre": "Gustavo Rodriguez",                 "telefono": "+573128178242", "fecha_cumpleanos": "2000-06-03", "fijo": False, "horario_fijo": ""},
    {"nombre": "Jhon Mario Agudelo",                "telefono": "+573218235797", "fecha_cumpleanos": "2000-07-09", "fijo": True,  "horario_fijo": "Viernes 2:00pm"},
    {"nombre": "Julian Manzano",                    "telefono": "+573175885307", "fecha_cumpleanos": "2000-06-07", "fijo": True,  "horario_fijo": "Viernes 10:30am"},
    {"nombre": "Brayan Andres Ramos Grajales",      "telefono": "+573183903459", "fecha_cumpleanos": "2000-04-12", "fijo": False, "horario_fijo": ""},
    {"nombre": "Alexander Ramos Oyola",             "telefono": "+573177655187", "fecha_cumpleanos": "2000-12-23", "fijo": False, "horario_fijo": ""},
    {"nombre": "Jhonatan Quiceno",                  "telefono": "+573228113415", "fecha_cumpleanos": "2000-11-28", "fijo": True,  "horario_fijo": "Viernes 11:30am"},
    {"nombre": "Ivan Marmolejo",                    "telefono": "+573218989306", "fecha_cumpleanos": "2000-10-29", "fijo": False, "horario_fijo": ""},
    {"nombre": "Alan Marmolejo",                    "telefono": "+573175886897", "fecha_cumpleanos": "2000-07-26", "fijo": False, "horario_fijo": ""},
    {"nombre": "Victor Caicedo",                    "telefono": "+573156179370", "fecha_cumpleanos": "",           "fijo": False, "horario_fijo": ""},
    {"nombre": "Sebastian Mottato Alzate",          "telefono": "+573164863614", "fecha_cumpleanos": "2000-10-13", "fijo": False, "horario_fijo": ""},
    {"nombre": "Robinson Viveros",                  "telefono": "+573174321860", "fecha_cumpleanos": "",           "fijo": True,  "horario_fijo": "Sabado 1:00pm"},
    {"nombre": "Ucevio Caicedo",                    "telefono": "+573215740909", "fecha_cumpleanos": "",           "fijo": False, "horario_fijo": ""},
    {"nombre": "Juan Caicedo",                      "telefono": "+573215726260", "fecha_cumpleanos": "2000-03-01", "fijo": False, "horario_fijo": ""},
    {"nombre": "Luis Ferney Hernandez",             "telefono": "+573159350947", "fecha_cumpleanos": "2000-01-09", "fijo": False, "horario_fijo": ""},
    {"nombre": "Juan Jose Meza Bejarano",           "telefono": "+573127885287", "fecha_cumpleanos": "2000-05-22", "fijo": False, "horario_fijo": ""},
    {"nombre": "Mauricio Montoya",                  "telefono": "+573148700754", "fecha_cumpleanos": "2000-05-31", "fijo": False, "horario_fijo": ""},
    {"nombre": "Carlos Motato",                     "telefono": "+573184087337", "fecha_cumpleanos": "2000-10-28", "fijo": False, "horario_fijo": ""},
    {"nombre": "Alan David Posada Carmona",         "telefono": "+573005189237", "fecha_cumpleanos": "2000-08-24", "fijo": False, "horario_fijo": ""},
    {"nombre": "Jorge Humberto Posada Ramirez",     "telefono": "+573182679750", "fecha_cumpleanos": "2000-09-12", "fijo": False, "horario_fijo": ""},
    {"nombre": "Leonardo Paredes Morales",          "telefono": "+573188759729", "fecha_cumpleanos": "2000-04-20", "fijo": False, "horario_fijo": ""},
    {"nombre": "Milton Morales",                    "telefono": "+573174681122", "fecha_cumpleanos": "2000-07-11", "fijo": False, "horario_fijo": ""},
    {"nombre": "Samuel Solis Castillo",             "telefono": "+573162770867", "fecha_cumpleanos": "2000-02-27", "fijo": False, "horario_fijo": ""},
    {"nombre": "John Quiñones",                     "telefono": "+573137566615", "fecha_cumpleanos": "2000-07-26", "fijo": False, "horario_fijo": ""},
    {"nombre": "Julio Agudelo",                     "telefono": "+573043374186", "fecha_cumpleanos": "2000-12-12", "fijo": True,  "horario_fijo": "Viernes cada 15 9:30pm"},
    {"nombre": "Jorge Gomez",                       "telefono": "+573127748822", "fecha_cumpleanos": "2000-08-22", "fijo": True,  "horario_fijo": "Jueves 7:00pm"},
    {"nombre": "Eduar Hurtado",                     "telefono": "+573177738292", "fecha_cumpleanos": "2000-06-18", "fijo": False, "horario_fijo": ""},
    {"nombre": "Cristian Tascon",                   "telefono": "+573027032583", "fecha_cumpleanos": "2000-09-06", "fijo": False, "horario_fijo": ""},
    {"nombre": "Nelson Garcia",                     "telefono": "+573167904748", "fecha_cumpleanos": "2000-08-19", "fijo": False, "horario_fijo": ""},
    {"nombre": "Fernando Hernandez",                "telefono": "+573184461072", "fecha_cumpleanos": "2000-05-28", "fijo": False, "horario_fijo": ""},
    {"nombre": "Luis Gabriel Zamora",               "telefono": "+573025092537", "fecha_cumpleanos": "2000-02-21", "fijo": True,  "horario_fijo": "Jueves 7:30pm"},
    # ⚠ Francisco Mona tiene el mismo teléfono que Jorge Gomez (+573127748822), será omitido
    {"nombre": "Francisco Mona",                    "telefono": "+573127748822", "fecha_cumpleanos": "2000-10-31", "fijo": True,  "horario_fijo": "Jueves 8:00pm"},
    {"nombre": "Miguel Hinestroza",                 "telefono": "+573152528164", "fecha_cumpleanos": "",           "fijo": False, "horario_fijo": ""},
    {"nombre": "Andres Pineda",                     "telefono": "+573176163235", "fecha_cumpleanos": "2000-05-09", "fijo": False, "horario_fijo": ""},
    {"nombre": "Dency Peña",                        "telefono": "+573185638414", "fecha_cumpleanos": "2000-02-10", "fijo": True,  "horario_fijo": "Sabados 2:00pm"},
    {"nombre": "Juan Camilo Montoya",               "telefono": "+573163962693", "fecha_cumpleanos": "2000-08-20", "fijo": True,  "horario_fijo": "Viernes 10:00pm"},
    {"nombre": "Angel Vargas",                      "telefono": "+573054045567", "fecha_cumpleanos": "2000-06-01", "fijo": False, "horario_fijo": ""},
    {"nombre": "Jesus Morales Muñoz",               "telefono": "+573124504353", "fecha_cumpleanos": "2000-05-09", "fijo": False, "horario_fijo": ""},
    {"nombre": "Juan Sebastian Bonilla Hinestroza", "telefono": "+573181622510", "fecha_cumpleanos": "2000-02-28", "fijo": False, "horario_fijo": ""},
]


def importar(app=None):

    if app is None:
        from app import create_app
        app = create_app()

    from app.models.cliente import Cliente
    from app.extensions import db
    from datetime import datetime

    insertados = omitidos = errores = 0

    with app.app_context():
        for datos in CLIENTES:
            telefono = datos.get("telefono", "").strip()
            if not telefono:
                omitidos += 1
                continue

            if Cliente.query.filter_by(telefono=telefono).first():
                print(f"  → Ya existe: {datos['nombre']} ({telefono})")
                omitidos += 1
                continue

            try:
                fecha_cumple = None
                raw = datos.get("fecha_cumpleanos", "").strip()
                if raw:
                    fecha_cumple = datetime.strptime(raw, "%Y-%m-%d").date()

                c = Cliente(
                    nombre           = datos["nombre"].strip(),
                    telefono         = telefono,
                    fecha_cumpleanos = fecha_cumple,
                    fijo             = bool(datos.get("fijo", False)),
                    horario_fijo     = datos.get("horario_fijo", "").strip() or None,
                )
                db.session.add(c)
                db.session.commit()

                tag = f" [{datos['horario_fijo']}]" if datos.get("fijo") else ""
                print(f"  ✅ {datos['nombre']} ({telefono}){tag}")
                insertados += 1

            except Exception as e:
                db.session.rollback()
                print(f"  ❌ {datos.get('nombre')}: {e}")
                errores += 1

    print(f"\n{'─'*45}")
    print(f"  Insertados : {insertados}")
    print(f"  Omitidos   : {omitidos}")
    print(f"  Errores    : {errores}")
    print(f"  Total      : {len(CLIENTES)}")
    print(f"{'─'*45}")

    return {"insertados": insertados, "omitidos": omitidos, "errores": errores}


if __name__ == "__main__":
    importar()
