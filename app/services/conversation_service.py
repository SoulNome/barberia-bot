from app.services.nlp_service import interpretar_mensaje
from app.services.disponibilidad_service import obtener_horarios_disponibles
from app.services.agenda_service import crear_cita, obtener_cita_cliente, cancelar_cita
from app.services.clientes_service import obtener_cliente_por_telefono

user_states = {}


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
    # CANCELAR DIRECTO
    # ------------------------------------------------

    if mensaje.startswith("cancelar"):

        partes = mensaje.split()

        try:

            if len(partes) >= 3:

                fecha = partes[1]
                hora = partes[2]

            else:

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

            user_states[telefono] = "inicio"

            return f"{msg}\n\nEscribe *hola* para volver al menú."

        except:

            return "❌ Formato incorrecto.\nEjemplo:\ncancelar 2026-03-20 15:00"

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
        accion = "cancelar"

    elif mensaje == "5":
        accion = "ver_cita"

    elif mensaje == "6":
        accion = "ayuda"

    # ------------------------------------------------
    # ESTADO: ESPERANDO BARBERO
    # ------------------------------------------------

    if estado == "esperando_barbero":

        barbero = None

        if mensaje.isdigit():

            barbero_id = int(mensaje)

            barbero = next(
                (b for b in barberos if b["id"] == barbero_id),
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
                texto += f"{b['id']}️⃣ {b['nombre']}\n"

            return texto

        user_states[telefono] = {
            "estado": "esperando_fecha",
            "barbero_id": barbero["id"]
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
    # ESTADO: ESPERANDO FECHA
    # ------------------------------------------------

    if isinstance(estado, dict) and estado.get("estado") == "esperando_fecha":

        barbero_id = estado["barbero_id"]

        fecha_final = fecha if fecha else mensaje

        try:

            horarios = obtener_horarios_disponibles(barbero_id, fecha_final)

        except:

            return "❌ No entendí la fecha.\nEjemplo: mañana"

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
            "horarios": horarios
        }

        return texto

    # ------------------------------------------------
    # ESTADO: ESPERANDO HORA
    # ------------------------------------------------

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
            "hora": hora_seleccionada
        }

        return f"""
📅 Fecha: {estado['fecha']}
⏰ Hora: {hora_seleccionada}

1️⃣ Confirmar cita
2️⃣ Elegir otro horario
"""

    # ------------------------------------------------
    # CONFIRMAR CITA
    # ------------------------------------------------

    if isinstance(estado, dict) and estado.get("estado") == "esperando_confirmacion":

        if mensaje == "1":

            ok, mensaje_cita = crear_cita(
                nombre=nombre_cliente if nombre_cliente else "Cliente",
                telefono=telefono_limpio,
                barbero_id=estado["barbero_id"],
                fecha=estado["fecha"],
                hora=estado["hora"]
            )

            user_states[telefono] = "inicio"

            if not ok:
                return mensaje_cita

            return f"""
✅ *Cita confirmada*

📅 Fecha: {estado['fecha']}
⏰ Hora: {estado['hora']}

Te esperamos 💈
"""

        elif mensaje == "2":

            user_states[telefono] = {
                "estado": "esperando_fecha",
                "barbero_id": estado["barbero_id"]
            }

            return "Perfecto 👍\nDime otra fecha."

        else:

            return "Escribe 1 para confirmar o 2 para cambiar."

    # ------------------------------------------------
    # VER BARBEROS
    # ------------------------------------------------

    if accion == "barberos":

        texto = "💈 *Nuestros barberos*\n\n"

        for b in barberos:
            texto += f"{b['id']}️⃣ {b['nombre']}\n"

        texto += "\nEscribe *1* para agendar."

        return texto

    # ------------------------------------------------
    # AGENDAR
    # ------------------------------------------------

    if accion == "agendar":

        texto = "💈 *Vamos a agendar tu cita*\n\n"

        texto += "Selecciona un barbero:\n\n"

        for b in barberos:
            texto += f"{b['id']}️⃣ {b['nombre']}\n"

        user_states[telefono] = "esperando_barbero"

        return texto

    # ------------------------------------------------
    # VER MI CITA
    # ------------------------------------------------

    if accion == "ver_cita":

        cita = obtener_cita_cliente(telefono_limpio)

        if not cita:
            return "❌ No tienes citas registradas."

        hora = cita.hora.strftime("%H:%M")

        return f"""
📅 *Tu próxima cita*

Fecha: {cita.fecha}
Hora: {hora}

Para cancelarla escribe:

cancelar
"""

    # ------------------------------------------------
    # AYUDA
    # ------------------------------------------------

    if accion == "ayuda":

        return """
💡 Puedes escribir:

1 agendar cita
2 ver barberos
3 ver horarios
4 cancelar cita
5 ver mi cita
"""

    return "❌ No entendí tu mensaje.\nEscribe *hola* para ver el menú."