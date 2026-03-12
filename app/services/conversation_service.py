from app.services.nlp_service import interpretar_mensaje
from app.services.disponibilidad_service import obtener_horarios_disponibles
from app.services.agenda_service import crear_cita, obtener_cita_cliente, cancelar_cita
from app.services.clientes_service import obtener_cliente_por_telefono

user_states = {}

# ------------------------------------------------
# SERVICIOS
# ------------------------------------------------

SERVICIOS = {
    1: {"nombre": "Corte niños", "precio": 15000},
    2: {"nombre": "Corte normal", "precio": 20000},
    3: {"nombre": "Corte + barba + tinte", "precio": 25000},
    4: {"nombre": "Corte + barba + tinte + alisadora", "precio": 30000},
    5: {"nombre": "Pigmentación cejas", "precio": 10000}
}


# ------------------------------------------------
# MENU
# ------------------------------------------------

def menu_principal(nombre=""):

    saludo = f"Hola {nombre} 👋" if nombre else "Hola 👋"

    return f"""
💈 *BarberIA*

{saludo}

1️⃣ Agendar cita
2️⃣ Ver barberos
3️⃣ Ver horarios
4️⃣ Cancelar cita
5️⃣ Ver mi cita
6️⃣ Ayuda
7️⃣ Ver precios

0️⃣ Volver al menú
"""


# ------------------------------------------------
# ORDENAR BARBEROS
# Hermes siempre primero
# ------------------------------------------------

def ordenar_barberos(barberos):

    barberos = sorted(
        barberos,
        key=lambda b: 0 if b["nombre"].lower() == "hermes" else 1
    )

    for i, b in enumerate(barberos):
        b["menu_id"] = i + 1

    return barberos


# ------------------------------------------------
# CONVERSACION PRINCIPAL
# ------------------------------------------------

def manejar_mensaje(telefono, mensaje, barberos):

    mensaje = mensaje.strip().lower()
    telefono_limpio = telefono.replace("whatsapp:", "")

    barberos = ordenar_barberos(barberos)

    estado_data = user_states.get(telefono, {"estado": "inicio"})
    estado = estado_data["estado"]

    cliente = obtener_cliente_por_telefono(telefono_limpio)
    nombre_cliente = cliente.nombre if cliente else ""

    nlp = interpretar_mensaje(mensaje, barberos)

    accion = nlp.get("accion")
    fecha = nlp.get("fecha")

    # ------------------------------------------------
    # VOLVER AL MENU
    # ------------------------------------------------

    if mensaje in ["hola", "menu", "volver", "inicio", "0"]:

        user_states[telefono] = {"estado": "inicio"}

        return menu_principal(nombre_cliente)
    
    # ------------------------------------------------
    # CANCELAR CITA DIRECTO
    # ------------------------------------------------

    if mensaje.startswith("cancelar"):

        cita = obtener_cita_cliente(telefono_limpio)

        if not cita:
            return "❌ No tienes citas registradas."

        fecha = cita.fecha
        hora = cita.hora.strftime("%H:%M")

        ok, msg = cancelar_cita(
            telefono_limpio,
            fecha,
            hora
        )

        user_states[telefono] = {"estado": "inicio"}

        return f"""
    ✅ Cita cancelada correctamente

    📅 {fecha}
    ⏰ {hora}

    Escribe *hola* para volver al menú.
    """

    # ------------------------------------------------
    # MENU NUMERICO SOLO EN INICIO
    # ------------------------------------------------

    if estado == "inicio":

        if mensaje == "1":
            accion = "agendar"

        elif mensaje == "2":
            accion = "barberos"

        elif mensaje == "3":
            accion = "horarios"

        elif mensaje == "4":
            accion = "cancelar_menu"

        elif mensaje == "5":
            accion = "ver_cita"

        elif mensaje == "6":
            accion = "ayuda"

        elif mensaje == "7":
            accion = "precios"

    # ------------------------------------------------
    # VER PRECIOS
    # ------------------------------------------------

    if accion == "precios":

        texto = "💈 *Servicios BarberIA*\n\n"

        for i, s in SERVICIOS.items():

            precio = f"${s['precio']:,}".replace(",", ".")

            texto += f"{i}️⃣ {s['nombre']} — {precio}\n"

        texto += "\nEscribe *1* para agendar."

        return texto

    # ------------------------------------------------
    # VER BARBEROS
    # ------------------------------------------------

    if accion == "barberos":

        texto = "💈 *Nuestros barberos*\n\n"

        for b in barberos:
            texto += f"{b['menu_id']}️⃣ {b['nombre']}\n"

        texto += "\nEscribe *1* para agendar."

        return texto

    # ------------------------------------------------
    # VER HORARIOS
    # ------------------------------------------------

    if accion == "horarios":

        barbero = barberos[0]

        horarios = obtener_horarios_disponibles(barbero["id"], "hoy")

        if not horarios:
            return "❌ No hay horarios disponibles hoy."

        texto = "📅 *Horarios disponibles hoy*\n\n"

        for h in horarios:

            if not h["disponible"]:
                continue

            texto += f"🟢 {h['hora']}\n"

        return texto

    # ------------------------------------------------
    # AGENDAR
    # ------------------------------------------------

    if accion == "agendar":

        texto = "💈 *Selecciona un servicio*\n\n"

        for i, s in SERVICIOS.items():

            precio = f"${s['precio']:,}".replace(",", ".")

            texto += f"{i}️⃣ {s['nombre']} — {precio}\n"

        user_states[telefono] = {"estado": "esperando_servicio"}

        return texto

    # ------------------------------------------------
    # ESPERANDO SERVICIO
    # ------------------------------------------------

    if estado == "esperando_servicio":

        if not mensaje.isdigit():
            return "❌ Escribe el número del servicio."

        servicio_id = int(mensaje)

        if servicio_id not in SERVICIOS:
            return "❌ Servicio inválido."

        servicio = SERVICIOS[servicio_id]

        texto = f"""
💈 *{servicio['nombre']} seleccionado*

Ahora elige un barbero:

"""

        for b in barberos:
            texto += f"{b['menu_id']}️⃣ {b['nombre']}\n"

        user_states[telefono] = {
            "estado": "esperando_barbero",
            "servicio": servicio["nombre"]
        }

        return texto

    # ------------------------------------------------
    # ESPERANDO BARBERO
    # ------------------------------------------------

    if estado == "esperando_barbero":

        barbero = None

        if mensaje.isdigit():

            opcion = int(mensaje)

            barbero = next(
                (b for b in barberos if b["menu_id"] == opcion),
                None
            )

        else:

            barbero = next(
                (b for b in barberos if b["nombre"].lower() == mensaje),
                None
            )

        if not barbero:

            texto = "❌ No encontré ese barbero.\n\n"

            for b in barberos:
                texto += f"{b['menu_id']}️⃣ {b['nombre']}\n"

            return texto

        user_states[telefono] = {
            "estado": "esperando_fecha",
            "barbero_id": barbero["id"],
            "barbero_nombre": barbero["nombre"],
            "servicio": estado_data.get("servicio")
        }

        return f"""
💈 *{barbero['nombre']} seleccionado*

¿Para qué fecha quieres tu cita?

• hoy
• mañana
• 2026-03-20
"""

    # ------------------------------------------------
    # ESPERANDO FECHA
    # ------------------------------------------------

    if estado == "esperando_fecha":

        barbero_id = estado_data["barbero_id"]

        fecha_final = fecha if fecha else mensaje

        try:

            horarios = obtener_horarios_disponibles(barbero_id, fecha_final)

        except:

            return "❌ No entendí la fecha.\nEjemplo: mañana"

        horarios_disponibles = [h for h in horarios if h["disponible"]]

        if not horarios_disponibles:
            return "❌ No hay horarios disponibles ese día."

        texto = f"📅 *Horarios disponibles {fecha_final}*\n\n"

        for i, h in enumerate(horarios_disponibles):

            texto += f"{i+1}️⃣ {h['hora']} 🟢\n"

        texto += "\nElige el número del horario."

        user_states[telefono] = {
            "estado": "esperando_hora",
            "barbero_id": barbero_id,
            "barbero_nombre": estado_data["barbero_nombre"],
            "fecha": fecha_final,
            "horarios": horarios_disponibles,
            "servicio": estado_data.get("servicio")
        }

        return texto

    # ------------------------------------------------
    # ESPERANDO HORA
    # ------------------------------------------------

    if estado == "esperando_hora":

        if not mensaje.isdigit():
            return "❌ Escribe el número del horario."

        index = int(mensaje) - 1

        horarios = estado_data["horarios"]

        if index < 0 or index >= len(horarios):
            return "❌ Ese número no es válido."

        hora = horarios[index]["hora"]

        user_states[telefono] = {
            "estado": "esperando_confirmacion",
            "barbero_id": estado_data["barbero_id"],
            "barbero_nombre": estado_data["barbero_nombre"],
            "fecha": estado_data["fecha"],
            "hora": hora,
            "servicio": estado_data.get("servicio")
        }

        return f"""
💈 Barbero: {estado_data["barbero_nombre"]}
💇 Servicio: {estado_data.get("servicio","Corte")}

📅 Fecha: {estado_data["fecha"]}
⏰ Hora: {hora}

1️⃣ Confirmar cita
2️⃣ Elegir otro horario
"""

    # ------------------------------------------------
    # CONFIRMAR
    # ------------------------------------------------

    if estado == "esperando_confirmacion":

        if mensaje == "1":

            ok, msg = crear_cita(
                nombre=nombre_cliente if nombre_cliente else "Cliente",
                telefono=telefono_limpio,
                barbero_id=estado_data["barbero_id"],
                fecha=estado_data["fecha"],
                hora=estado_data["hora"],
                servicio=estado_data.get("servicio")
            )

            user_states[telefono] = {"estado": "inicio"}

            if not ok:
                return msg

            return f"""
✅ *Cita confirmada*

💈 Barbero: {estado_data["barbero_nombre"]}
💇 Servicio: {estado_data.get("servicio")}

📅 Fecha: {estado_data["fecha"]}
⏰ Hora: {estado_data["hora"]}

Te esperamos 💈
"""

        elif mensaje == "2":

            user_states[telefono] = {
                "estado": "esperando_fecha",
                "barbero_id": estado_data["barbero_id"],
                "barbero_nombre": estado_data["barbero_nombre"],
                "servicio": estado_data.get("servicio")
            }

            return "Perfecto 👍\nDime otra fecha."

        else:

            return "Escribe 1 para confirmar o 2 para cambiar."

    # ------------------------------------------------

    return "❌ No entendí tu mensaje.\nEscribe *hola* para ver el menú."