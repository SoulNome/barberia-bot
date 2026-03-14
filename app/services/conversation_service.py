from app.services.nlp_service import interpretar_mensaje
from app.services.disponibilidad_service import obtener_horarios_disponibles
from app.services.agenda_service import crear_cita, obtener_cita_cliente, cancelar_cita
from app.services.clientes_service import obtener_cliente_por_telefono
from app.services.state_service import get_state, set_state
from app.models import Barbero
from datetime import datetime

DIAS_ES   = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES_ES  = ["enero", "febrero", "marzo", "abril", "mayo", "junio",
             "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]

def formatear_fecha(fecha_str):
    try:
        f = datetime.strptime(fecha_str, "%Y-%m-%d")
        return f"{DIAS_ES[f.weekday()]} {f.day} de {MESES_ES[f.month - 1]}"
    except:
        return fecha_str

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

    estado_data = get_state(telefono)
    estado = estado_data["estado"]

    cliente = obtener_cliente_por_telefono(telefono_limpio)
    nombre_cliente = cliente.nombre if cliente else ""

    # ------------------------------------------------
    # VOLVER AL MENU — siempre tiene prioridad máxima
    # ------------------------------------------------

    if mensaje in ["hola", "menu", "volver", "inicio", "0"]:
        set_state(telefono, {"estado": "inicio"})
        return menu_principal(nombre_cliente)

    # ------------------------------------------------
    # MENU NUMERICO — solo en estado inicio, ANTES del NLP
    # para evitar que el NLP sobreescriba la selección
    # ------------------------------------------------

    accion = None  # FIX: inicializar accion antes del NLP

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

    # Solo llamar NLP si el menú numérico no resolvió la acción
    # FIX: evitar que NLP sobreescriba selección numérica del menú
    if accion is None:
        nlp = interpretar_mensaje(mensaje, barberos)
        accion = nlp.get("accion")
        fecha = nlp.get("fecha")
    else:
        fecha = None

    # ------------------------------------------------
    # CANCELAR CITA — palabra clave directa
    # FIX: también capturar accion "cancelar_menu" aquí
    # ------------------------------------------------

    if mensaje.startswith("cancelar") or accion in ("cancelar_menu", "cancelar"):

        cita = obtener_cita_cliente(telefono_limpio)

        if not cita:
            set_state(telefono, {"estado": "inicio"})
            return "❌ No tienes citas registradas.\n\nEscribe *hola* para volver al menú."

        fecha_cita = cita.fecha
        hora_cita = cita.hora.strftime("%H:%M")

        # FIX: preguntar confirmación antes de cancelar
        set_state(telefono, {
            "estado": "confirmando_cancelacion",
            "fecha": str(fecha_cita),
            "hora": hora_cita
        })

        return f"""
❗ *¿Seguro que quieres cancelar tu cita?*

📅 {fecha_cita}
⏰ {hora_cita}

1️⃣ Sí, cancelar
2️⃣ No, mantener cita
"""

    # ------------------------------------------------
    # CONFIRMANDO CANCELACION
    # ------------------------------------------------

    if estado == "confirmando_cancelacion":

        if mensaje == "1":

            ok, msg = cancelar_cita(
                telefono_limpio,
                estado_data["fecha"],
                estado_data["hora"]
            )

            set_state(telefono, {"estado": "inicio"})

            if not ok:
                return f"❌ No se pudo cancelar: {msg}\n\nEscribe *hola* para volver al menú."

            return f"""
✅ *Cita cancelada correctamente*

📅 {estado_data["fecha"]}
⏰ {estado_data["hora"]}

Escribe *hola* para volver al menú.
"""

        elif mensaje == "2":
            set_state(telefono, {"estado": "inicio"})
            return "👍 Tu cita se mantiene.\n\nEscribe *hola* para volver al menú."

        else:
            return "Escribe *1* para cancelar o *2* para mantener tu cita."

    # ------------------------------------------------
    # VER MI CITA
    # ------------------------------------------------

    if accion == "ver_cita":

        cita = obtener_cita_cliente(telefono_limpio)

        if not cita:
            return "❌ No tienes citas registradas.\n\nEscribe *hola* para volver al menú."

        hora_cita = cita.hora.strftime("%H:%M")
        barbero = Barbero.query.get(cita.barbero_id)
        barbero_nombre = barbero.nombre if barbero else "N/A"

        return f"""
📋 *Tu cita*

💈 Barbero: {barbero_nombre}
💇 Servicio: {cita.servicio or "N/A"}
📅 Fecha: {cita.fecha}
⏰ Hora: {hora_cita}

Escribe *cancelar* si deseas cancelarla.
"""

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
        set_state(telefono, {"estado": "consultando_horarios"})
        return "📅 ¿Para qué fecha quieres ver los horarios?\n\nEjemplos: *hoy*, *mañana*, *lunes*"

    # ------------------------------------------------
    # CONSULTANDO HORARIOS
    # ------------------------------------------------

    if estado == "consultando_horarios":

        barbero = barberos[0]
        fecha_consulta = fecha if fecha else mensaje

        resultado = obtener_horarios_disponibles(barbero["id"], fecha_consulta)

        set_state(telefono, {"estado": "inicio"})

        if resultado == "domingo":
            return "📅 Los domingos no trabajamos.\n\nEscribe *hola* para ver el menú."

        if resultado == "festivo":
            return "📅 Ese día es festivo y no trabajamos.\n\nEscribe *hola* para ver el menú."

        if not resultado or resultado is None:
            return "❌ No entendí la fecha. Intenta con *hoy*, *mañana* o *lunes*."

        disponibles = [h for h in resultado if h["disponible"]]
        fecha_bonita = formatear_fecha(fecha_consulta) if "-" in str(fecha_consulta) else fecha_consulta

        if not disponibles:
            return f"📅 No hay turnos libres para *{fecha_bonita}*.\n\nEscribe *1* para agendar."

        texto = f"📅 *{fecha_bonita}*\n\n"
        for h in disponibles:
            texto += f"🟢 {h['hora']}\n"
        texto += "\nEscribe *1* para agendar."

        return texto

    # ------------------------------------------------
    # AGENDAR
    # FIX: solo resetear el flujo si estamos en inicio,
    # no interrumpir si ya hay un flujo en progreso
    # ------------------------------------------------

    if accion == "agendar" and estado == "inicio":

        # Cliente nuevo → pedir nombre antes de continuar
        if not cliente:
            set_state(telefono, {"estado": "esperando_nombre"})
            return "Para agendar tu cita necesito saber tu nombre 😊\n\n¿Cómo te llamas?"

        texto = "💈 *Selecciona un servicio*\n\n"

        for i, s in SERVICIOS.items():
            precio = f"${s['precio']:,}".replace(",", ".")
            texto += f"{i}️⃣ {s['nombre']} — {precio}\n"

        set_state(telefono, {"estado": "esperando_servicio"})

        return texto

    # ------------------------------------------------
    # ESPERANDO NOMBRE — solo para clientes nuevos
    # ------------------------------------------------

    if estado == "esperando_nombre":

        nombre = mensaje.strip().title()

        if len(nombre) < 2:
            return "❌ Escribe tu nombre completo para continuar."

        texto = f"Hola *{nombre}* 👋\n\n💈 *Selecciona un servicio*\n\n"

        for i, s in SERVICIOS.items():
            precio = f"${s['precio']:,}".replace(",", ".")
            texto += f"{i}️⃣ {s['nombre']} — {precio}\n"

        set_state(telefono, {"estado": "esperando_servicio", "nombre": nombre})

        return texto

    # ------------------------------------------------
    # ESPERANDO SERVICIO
    # ------------------------------------------------

    if estado == "esperando_servicio":

        if not mensaje.isdigit():
            return "❌ Escribe el número del servicio."

        servicio_id = int(mensaje)

        if servicio_id not in SERVICIOS:
            return f"❌ Servicio inválido. Elige entre 1 y {len(SERVICIOS)}."

        servicio = SERVICIOS[servicio_id]

        texto = f"💈 *{servicio['nombre']} seleccionado*\n\nAhora elige un barbero:\n\n"

        for b in barberos:
            texto += f"{b['menu_id']}️⃣ {b['nombre']}\n"

        set_state(telefono, {
            "estado": "esperando_barbero",
            "servicio": servicio["nombre"]
        })

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
            texto = "❌ No encontré ese barbero. Elige una opción:\n\n"
            for b in barberos:
                texto += f"{b['menu_id']}️⃣ {b['nombre']}\n"
            return texto

        set_state(telefono, {
            "estado": "esperando_fecha",
            "barbero_id": barbero["id"],
            "barbero_nombre": barbero["nombre"],
            "servicio": estado_data.get("servicio")
        })

        return f"💈 *{barbero['nombre']} seleccionado*\n\n¿Para qué fecha quieres tu cita?\n\nEjemplos: *hoy*, *mañana*, *lunes*, *viernes*"

    # ------------------------------------------------
    # ESPERANDO FECHA
    # FIX: manejo robusto cuando NLP no parsea la fecha
    # ------------------------------------------------

    if estado == "esperando_fecha":

        barbero_id = estado_data["barbero_id"]

        # Usar fecha del NLP si existe, si no usar el mensaje crudo
        fecha_final = fecha if fecha else mensaje

        try:
            horarios = obtener_horarios_disponibles(barbero_id, fecha_final)
        except Exception:
            return "❌ No entendí la fecha. Intenta con:\n• *hoy*\n• *mañana*\n• *2026-03-20*"

        if horarios is None:
            return "❌ Hubo un problema consultando los horarios. Intenta de nuevo."

        if horarios == "domingo":
            return "📅 Los domingos no trabajamos.\n\nPrueba con otra fecha 😊"

        if horarios == "festivo":
            return "📅 Ese día es festivo y no trabajamos.\n\nPrueba con otra fecha 😊"

        if not horarios:
            return f"❌ No hay horarios disponibles para ese día.\n\nPrueba con otra fecha."

        horarios_disponibles = [h for h in horarios if h["disponible"]][:9]

        if not horarios_disponibles:
            return f"❌ No hay turnos libres para ese día.\n\nPrueba con otra fecha."

        fecha_bonita = formatear_fecha(fecha_final)
        texto = f"📅 *{fecha_bonita}*\n\n"

        for i, h in enumerate(horarios_disponibles):
            texto += f"{i+1}️⃣ {h['hora']}\n"

        texto += "\nElige el número del horario."

        set_state(telefono, {
            "estado": "esperando_hora",
            "barbero_id": barbero_id,
            "barbero_nombre": estado_data["barbero_nombre"],
            "fecha": fecha_final,
            "horarios": horarios_disponibles,
            "servicio": estado_data.get("servicio")
        })

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
            return f"❌ Ese número no es válido. Elige entre 1 y {len(horarios)}."

        hora = horarios[index]["hora"]

        set_state(telefono, {
            "estado": "esperando_confirmacion",
            "barbero_id": estado_data["barbero_id"],
            "barbero_nombre": estado_data["barbero_nombre"],
            "fecha": estado_data["fecha"],
            "hora": hora,
            "servicio": estado_data.get("servicio")
        })

        return f"""
💈 Barbero: {estado_data["barbero_nombre"]}
💇 Servicio: {estado_data.get("servicio", "Corte")}

📅 Fecha: {estado_data["fecha"]}
⏰ Hora: {hora}

1️⃣ Confirmar cita
2️⃣ Elegir otro horario
"""

    # ------------------------------------------------
    # CONFIRMAR CITA
    # ------------------------------------------------

    if estado == "esperando_confirmacion":

        if mensaje == "1":

            ok, msg = crear_cita(
                nombre=nombre_cliente or estado_data.get("nombre") or "Cliente",
                telefono=telefono_limpio,
                barbero_id=estado_data["barbero_id"],
                fecha=estado_data["fecha"],
                hora=estado_data["hora"],
                servicio=estado_data.get("servicio")
            )

            set_state(telefono, {"estado": "inicio"})

            if not ok:
                return f"❌ No se pudo crear la cita: {msg}"

            return f"""
✅ *Cita confirmada*

💈 Barbero: {estado_data["barbero_nombre"]}
💇 Servicio: {estado_data.get("servicio")}

📅 Fecha: {estado_data["fecha"]}
⏰ Hora: {estado_data["hora"]}

Te esperamos 💈
"""

        elif mensaje == "2":

            set_state(telefono, {
                "estado": "esperando_fecha",
                "barbero_id": estado_data["barbero_id"],
                "barbero_nombre": estado_data["barbero_nombre"],
                "servicio": estado_data.get("servicio")
            })

            return "Perfecto 👍\nDime otra fecha."

        else:
            return "Escribe *1* para confirmar o *2* para cambiar."

    # ------------------------------------------------
    # AYUDA
    # ------------------------------------------------

    if accion == "ayuda":
        return """
🆘 *Ayuda BarberIA*

Puedes escribirme de forma natural o usar el menú:

• *hola* — Ver menú principal
• *1* — Agendar cita
• *cancelar* — Cancelar tu cita
• *0* — Volver al menú en cualquier mometo
"""

    # ------------------------------------------------
    # FALLBACK
    # ----

    return "❌ No entendí tu mensaje.\nEscribe *hola* para ver el menú."