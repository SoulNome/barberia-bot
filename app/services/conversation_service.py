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


def manejar_mensaje(telefono, mensaje, barberos):

    mensaje = mensaje.strip().lower()
    telefono_limpio = telefono.replace("whatsapp:", "")

    estado = user_states.get(telefono, "inicio")

    cliente = obtener_cliente_por_telefono(telefono_limpio)
    nombre_cliente = cliente.nombre if cliente else ""

    nlp = interpretar_mensaje(mensaje, barberos)

    accion = nlp.get("accion")
    fecha = nlp.get("fecha")

    # ------------------------------------------------
    # VOLVER AL MENU
    # ------------------------------------------------

    if mensaje in ["hola", "menu", "volver", "inicio", "0"]:

        user_states[telefono] = "inicio"

        return menu_principal(nombre_cliente)

    # ------------------------------------------------
    # MENU NUMERICO
    # ------------------------------------------------

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
    # VER BARBEROS
    # ------------------------------------------------

    if accion == "barberos":

        texto = "💈 *Nuestros barberos*\n\n"

        # CAMBIO 1 (numeración visual)
        for i, b in enumerate(barberos, start=1):
            texto += f"{i}️⃣ {b['nombre']}\n"

        texto += "\nEscribe *1* para agendar."

        return texto

    # ------------------------------------------------
    # AGENDAR
    # ------------------------------------------------

    if accion == "agendar":

        texto = "💈 *Selecciona un servicio*\n\n"

        for i, s in SERVICIOS.items():

            precio = f"${s['precio']:,}".replace(",", ".")

            texto += f"{i}️⃣ {s['nombre']} — {precio}\n"

        user_states[telefono] = "esperando_servicio"

        return texto

    # ------------------------------------------------
    # ESTADO: ESPERANDO SERVICIO
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

        # CAMBIO 2
        for i, b in enumerate(barberos, start=1):
            texto += f"{i}️⃣ {b['nombre']}\n"

        user_states[telefono] = {
            "estado": "esperando_barbero",
            "servicio": servicio["nombre"],
            "barberos": barberos
        }

        return texto

    # ------------------------------------------------
    # ESTADO: ESPERANDO BARBERO
    # ------------------------------------------------

    if isinstance(estado, dict) and estado.get("estado") == "esperando_barbero":

        lista_barberos = estado["barberos"]

        if not mensaje.isdigit():
            return "❌ Escribe el número del barbero."

        # CAMBIO 3
        indice = int(mensaje) - 1

        if indice < 0 or indice >= len(lista_barberos):
            return "❌ Ese barbero no existe."

        barbero = lista_barberos[indice]

        user_states[telefono] = {
            "estado": "esperando_fecha",
            "barbero_id": barbero["id"],
            "servicio": estado["servicio"]
        }

        return f"""
💈 *{barbero['nombre']} seleccionado*

¿Para qué fecha quieres tu cita?

Puedes escribir:

• hoy
• mañana
• 2026-03-12
"""

    # ------------------------------------------------
    # RESTO DEL CÓDIGO (SIN CAMBIOS)
    # ------------------------------------------------

    if isinstance(estado, dict) and estado.get("estado") == "esperando_fecha":

        barbero_id = estado["barbero_id"]

        fecha_final = fecha if fecha else mensaje

        try:
            horarios = obtener_horarios_disponibles(barbero_id, fecha_final)
        except:
            return "❌ No entendí la fecha."

        if not horarios:
            return "❌ No hay horarios disponibles ese día."

        texto = f"📅 *Horarios disponibles {fecha_final}*\n\n"

        for i, h in enumerate(horarios):

            icono = "🟢" if h["disponible"] else "🔴"

            texto += f"{i+1}️⃣ {h['hora']} {icono}\n"

        texto += "\nElige el número del horario."

        user_states[telefono] = {
            "estado": "esperando_hora",
            "barbero_id": barbero_id,
            "fecha": fecha_final,
            "horarios": horarios,
            "servicio": estado.get("servicio")
        }

        return texto

    if isinstance(estado, dict) and estado.get("estado") == "esperando_hora":

        if not mensaje.isdigit():
            return "❌ Escribe el número del horario."

        index = int(mensaje) - 1

        if index < 0 or index >= len(estado["horarios"]):
            return "❌ Ese número no es válido."

        horario = estado["horarios"][index]

        if not horario["disponible"]:
            return "❌ Ese horario ya está ocupado."

        hora_seleccionada = horario["hora"]

        user_states[telefono] = {
            "estado": "esperando_confirmacion",
            "barbero_id": estado["barbero_id"],
            "fecha": estado["fecha"],
            "hora": hora_seleccionada,
            "servicio": estado.get("servicio")
        }

        return f"""
💈 Servicio: {estado.get("servicio","Corte")}

📅 Fecha: {estado['fecha']}
⏰ Hora: {hora_seleccionada}

1️⃣ Confirmar cita
2️⃣ Elegir otro horario
"""

    return "❌ No entendí tu mensaje.\nEscribe *hola* para ver el menú."