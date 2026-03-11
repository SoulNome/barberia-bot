from app.services.nlp_service import interpretar_mensaje
from app.services.disponibilidad_service import obtener_horarios_disponibles
from app.services.agenda_service import crear_cita, obtener_cita_cliente, cancelar_cita
from app.services.clientes_service import obtener_cliente_por_telefono

user_states = {}


def manejar_mensaje(telefono, mensaje, barberos):

    mensaje = mensaje.strip().lower()
    telefono_limpio = telefono.replace("whatsapp:", "")

    estado = user_states.get(telefono, "inicio")

    cliente = obtener_cliente_por_telefono(telefono_limpio)
    nombre_cliente = cliente.nombre if cliente else ""

    nlp = interpretar_mensaje(mensaje, barberos)

    accion = nlp.get("accion")
    fecha = nlp.get("fecha")
    hora = nlp.get("hora")

    # ------------------------------------------------
    # CANCELAR DIRECTO (MEJORADO)
    # ------------------------------------------------

    if mensaje.startswith("cancelar"):

        partes = mensaje.split()

        try:

            if len(partes) >= 3:

                fecha = partes[1]
                hora = partes[2]

            else:
                # cancelar última cita automáticamente
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

            return f"""
{msg}

Escribe *hola* para volver al menú.
"""

        except:

            return "Formato incorrecto.\nEjemplo:\ncancelar 2026-03-20 15:00"

    # ------------------------------------------------
    # VOLVER AL MENU
    # ------------------------------------------------

    if mensaje in ["0", "menu", "volver", "inicio"]:

        user_states[telefono] = "inicio"

        saludo = f"Hola {nombre_cliente} 👋" if nombre_cliente else "Hola 👋"

        return f"""
💈 {saludo}

Bienvenido a BarberIA

1️⃣ Agendar cita
2️⃣ Ver barberos
3️⃣ Ver horarios
4️⃣ Cancelar cita
5️⃣ Ver mi cita
6️⃣ Ayuda

Escribe solo el número.
"""

    # ------------------------------------------------
    # SALUDO
    # ------------------------------------------------

    if mensaje in ["hola", "hi"]:

        user_states[telefono] = "inicio"

        saludo = f"Hola {nombre_cliente} 👋" if nombre_cliente else "Hola 👋"

        return f"""
💈 {saludo}

Bienvenido a BarberIA

1️⃣ Agendar cita
2️⃣ Ver barberos
3️⃣ Ver horarios
4️⃣ Cancelar cita
5️⃣ Ver mi cita
6️⃣ Ayuda

Escribe solo el número.
"""

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
    # ESTADOS
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

            texto += "\nEscribe el número."

            return texto

        user_states[telefono] = {
            "estado": "esperando_fecha",
            "barbero_id": barbero["id"]
        }

        return f"""
💈 Perfecto

Seleccionaste a *{barbero['nombre']}*

¿Para qué fecha quieres la cita?

Puedes escribir:

• hoy
• mañana
• 2026-03-12
"""

    # ------------------------------------------------
    # ESPERANDO FECHA
    # ------------------------------------------------

    if isinstance(estado, dict) and estado.get("estado") == "esperando_fecha":

        barbero_id = estado["barbero_id"]

        fecha_final = fecha if fecha else mensaje

        try:

            horarios = obtener_horarios_disponibles(barbero_id, fecha_final)

        except:

            return """
❌ No entendí la fecha.

Puedes escribir:

• hoy
• mañana
• 2026-03-12
"""

        if not horarios:

            return "❌ No hay horarios disponibles ese día."

        texto = f"📅 Horarios disponibles para {fecha_final}\n\n"

        for i, h in enumerate(horarios):
            texto += f"{i+1}️⃣ {h}\n"

        texto += "\nEscribe el número del horario."

        user_states[telefono] = {
            "estado": "esperando_hora",
            "barbero_id": barbero_id,
            "fecha": fecha_final,
            "horarios": horarios
        }

        return texto

    # ------------------------------------------------
    # SELECCIONAR HORA
    # ------------------------------------------------

    if isinstance(estado, dict) and estado.get("estado") == "esperando_hora":

        try:

            index = int(mensaje) - 1
            hora_seleccionada = estado["horarios"][index]

        except:

            return "❌ Escribe el número del horario."

        barbero_id = estado["barbero_id"]
        fecha = estado["fecha"]

        ok, mensaje_cita = crear_cita(
            nombre=nombre_cliente if nombre_cliente else "Cliente",
            telefono=telefono_limpio,
            barbero_id=barbero_id,
            fecha=fecha,
            hora=hora_seleccionada
        )

        user_states[telefono] = "inicio"

        if not ok:
            return f"❌ {mensaje_cita}"

        return f"""
✅ *Cita confirmada*

📅 Fecha: {fecha}
⏰ Hora: {hora_seleccionada}

Te esperamos 💈
"""

    # ------------------------------------------------
    # VER BARBEROS
    # ------------------------------------------------

    if accion == "barberos":

        texto = "💈 Nuestros barberos\n\n"

        for b in barberos:
            texto += f"{b['id']}️⃣ {b['nombre']}\n"

        texto += "\nEscribe *1* para agendar."

        return texto

    # ------------------------------------------------
    # INICIAR AGENDAMIENTO
    # ------------------------------------------------

    if accion == "agendar":

        texto = "💈 Vamos a agendar tu cita.\n\n"

        texto += "Selecciona un barbero:\n\n"

        for b in barberos:
            texto += f"{b['id']}️⃣ {b['nombre']}\n"

        texto += "\nEscribe el número."

        user_states[telefono] = "esperando_barbero"

        return texto

    # ------------------------------------------------
    # VER HORARIOS
    # ------------------------------------------------

    if accion == "horarios":

        texto = "¿De qué barbero quieres ver horarios?\n\n"

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
            return "No tienes citas registradas."

        hora = cita.hora.strftime("%H:%M")

        return f"""
📅 Tu próxima cita

Fecha: {cita.fecha}
Hora: {hora}

Si deseas cancelarla escribe:

cancelar {cita.fecha} {hora}
"""

    # ------------------------------------------------
    # CANCELAR MENU
    # ------------------------------------------------

    if accion == "cancelar":

        return """
Para cancelar tu cita escribe:

cancelar AAAA-MM-DD HH:MM

Ejemplo:
cancelar 2026-03-20 15:00
"""

    # ------------------------------------------------
    # AYUDA
    # ------------------------------------------------

    if accion == "ayuda":

        return """
💡 Puedes escribir:

hola
1 agendar cita
2 ver barberos
3 ver horarios
4 cancelar cita
"""

    # ------------------------------------------------
    # DEFAULT
    # ------------------------------------------------

    return """
❌ No entendí tu mensaje.

Escribe *hola* para ver el menú.
"""