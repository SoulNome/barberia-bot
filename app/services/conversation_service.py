import re
from app.services.nlp_service import interpretar_mensaje, detectar_servicio_por_nombre, detectar_barbero
from app.services.disponibilidad_service import obtener_horarios_disponibles, normalizar_fecha as _normalizar_fecha_raw
from app.services.agenda_service import crear_cita, obtener_cita_cliente, cancelar_cita
from app.services.clientes_service import obtener_cliente_por_telefono
from app.services.state_service import get_state, set_state
from app.models import Barbero
from datetime import datetime, date, timedelta

try:
    from app.services.lista_espera_service import agregar_a_espera
    _WAITLIST = True
except ImportError:
    _WAITLIST = False

DIAS_ES  = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES_ES = ["enero", "febrero", "marzo", "abril", "mayo", "junio",
            "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]

# ── Helpers de lenguaje natural ───────────────────────────────────────────────

_AFIRMATIVOS = {
    "si", "sí", "1", "dale", "ok", "va", "listo", "bueno", "claro",
    "yes", "yep", "confirmar", "confirmo", "perfecto", "de acuerdo",
    "está bien", "esta bien", "adelante", "sure", "eso", "correcto",
    "exacto", "venga", "vamos", "oka", "oki", "okey", "obvio",
    "por supuesto", "simon", "simón", "s", "jp", "x",
}

_NEGATIVOS = {
    "no", "2", "nope", "nel", "nunca", "nop", "n", "negativo",
    "cambiar", "otro", "otra", "diferente", "no gracias", "cancelar",
    "mejor no", "jamas", "jamás",
}


def _es_si(msg: str) -> bool:
    """Acepta afirmaciones naturales como confirmación."""
    msg = msg.strip().lower()
    return msg in _AFIRMATIVOS


def _es_no(msg: str) -> bool:
    """Acepta negaciones naturales."""
    msg = msg.strip().lower()
    return msg in _NEGATIVOS


def es_semana_cumpleanos(cliente):
    if not cliente or not cliente.fecha_cumpleanos:
        return False
    try:
        hoy   = (datetime.utcnow() - timedelta(hours=5)).date()
        cumple = cliente.fecha_cumpleanos.replace(year=hoy.year)
        lunes  = cumple - timedelta(days=cumple.weekday())
        return lunes <= hoy <= lunes + timedelta(days=6)
    except Exception:
        return False


def formatear_fecha(fecha_str):
    try:
        f = datetime.strptime(fecha_str, "%Y-%m-%d")
        return f"{DIAS_ES[f.weekday()]} {f.day} de {MESES_ES[f.month - 1]}"
    except Exception:
        return fecha_str


def _ampm(hora_str: str) -> str:
    """Convierte '14:30' → '2:30 PM' (formato amigable para WhatsApp)."""
    try:
        h, m = map(int, hora_str.split(":"))
        periodo = "AM" if h < 12 else "PM"
        h12 = h % 12 or 12
        if m:
            return f"{h12}:{m:02d} {periodo}"
        return f"{h12}:00 {periodo}"
    except Exception:
        return hora_str


from app.models.barberia import DEFAULT_SERVICIOS as _DEFAULT_SERVICIOS


def _servicios_como_dict(lista):
    """Convierte lista [{id,nombre,precio}] → dict {id: {nombre,precio}}"""
    return {s["id"]: {"nombre": s["nombre"], "precio": s["precio"]} for s in lista}


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
6️⃣ Reagendar cita
7️⃣ Ver precios
8️⃣ Ayuda

0️⃣ Volver al menú
"""


def ordenar_barberos(barberos):
    barberos = sorted(barberos, key=lambda b: 0 if b["nombre"].lower() == "hermes" else 1)
    for i, b in enumerate(barberos):
        b["menu_id"] = i + 1
    return barberos


# ------------------------------------------------
# CONVERSACIÓN PRINCIPAL
# ------------------------------------------------

def manejar_mensaje(telefono, mensaje, barberos, barberia_id=None):

    mensaje = mensaje.strip().lower()
    telefono_limpio = telefono.replace("whatsapp:", "")

    barberos = ordenar_barberos(barberos)

    # Cargar config de la barbería (servicios/precios propios o defaults)
    _barberia = None
    if barberia_id:
        try:
            from app.models.barberia import Barberia
            _barberia = Barberia.query.get(barberia_id)
        except Exception:
            pass
    SERVICIOS = _servicios_como_dict(
        _barberia.get_servicios() if _barberia else _DEFAULT_SERVICIOS
    )

    estado_data  = get_state(telefono, barberia_id)
    estado       = estado_data["estado"]

    cliente      = obtener_cliente_por_telefono(telefono_limpio, barberia_id)
    nombre_cliente = cliente.nombre if cliente else ""

    # ── Volver al menú ────────────────────────────────────────────────────────
    _reset_words = {"hola", "menu", "menú", "volver", "inicio", "0", "start",
                    "comenzar", "empezar", "principal", "regresar"}
    if mensaje in _reset_words or mensaje.startswith("hola "):
        set_state(telefono, {"estado": "inicio"}, barberia_id)
        return menu_principal(nombre_cliente)

    # ── Menú numérico (solo en estado inicio) ─────────────────────────────────
    accion = None

    if estado == "inicio":
        if    mensaje in ("1",): accion = "agendar"
        elif  mensaje in ("2",): accion = "barberos"
        elif  mensaje in ("3",): accion = "horarios"
        elif  mensaje in ("4",): accion = "cancelar_menu"
        elif  mensaje in ("5",): accion = "ver_cita"
        elif  mensaje in ("6",): accion = "reagendar"
        elif  mensaje in ("7",): accion = "precios"
        elif  mensaje in ("8",): accion = "ayuda"

    if accion is None:
        nlp    = interpretar_mensaje(mensaje, barberos)
        accion = nlp.get("accion")
        fecha  = nlp.get("fecha")
    else:
        fecha = None

    # ── Cancelar cita ─────────────────────────────────────────────────────────
    if mensaje.startswith("cancelar") or accion in ("cancelar_menu", "cancelar"):

        cita = obtener_cita_cliente(telefono_limpio, barberia_id)

        if not cita:
            set_state(telefono, {"estado": "inicio"}, barberia_id)
            return "❌ No tienes citas registradas.\n\nEscribe *hola* para volver al menú."

        fecha_cita = cita.fecha
        hora_cita  = cita.hora.strftime("%H:%M")   # guardado internamente en 24h

        set_state(telefono, {
            "estado": "confirmando_cancelacion",
            "fecha":  str(fecha_cita),
            "hora":   hora_cita
        }, barberia_id)

        return f"""
❗ *¿Seguro que quieres cancelar tu cita?*

📅 {formatear_fecha(str(fecha_cita))}
⏰ {_ampm(hora_cita)}

Responde *sí* para cancelar o *no* para mantener tu cita.
"""

    # ── Confirmando cancelación ───────────────────────────────────────────────
    if estado == "confirmando_cancelacion":

        if _es_si(mensaje):
            ok, msg = cancelar_cita(
                telefono_limpio,
                estado_data["fecha"],
                estado_data["hora"],
                barberia_id
            )
            set_state(telefono, {"estado": "inicio"}, barberia_id)
            if not ok:
                return f"❌ No se pudo cancelar: {msg}\n\nEscribe *hola* para volver al menú."
            return f"""
✅ *Cita cancelada correctamente*

📅 {formatear_fecha(estado_data["fecha"])}
⏰ {_ampm(estado_data["hora"])}

Escribe *hola* para volver al menú.
"""
        elif _es_no(mensaje):
            set_state(telefono, {"estado": "inicio"}, barberia_id)
            return "👍 Tu cita se mantiene.\n\nEscribe *hola* para volver al menú."
        else:
            return (
                f"❗ *¿Cancelar tu cita?*\n\n"
                f"📅 {formatear_fecha(estado_data.get('fecha', ''))}  "
                f"⏰ {_ampm(estado_data.get('hora', ''))}\n\n"
                f"Responde *sí* para cancelar o *no* para mantener tu cita."
            )

    # ── Ver mi cita ───────────────────────────────────────────────────────────
    if accion == "ver_cita":

        cita = obtener_cita_cliente(telefono_limpio, barberia_id)

        if not cita:
            return "❌ No tienes citas registradas.\n\nEscribe *hola* para volver al menú."

        hora_cita      = cita.hora.strftime("%H:%M")
        barbero        = Barbero.query.get(cita.barbero_id)
        barbero_nombre = barbero.nombre if barbero else "N/A"

        return f"""
📋 *Tu cita*

💈 Barbero: {barbero_nombre}
💇 Servicio: {cita.servicio or "N/A"}
📅 Fecha: {formatear_fecha(str(cita.fecha))}
⏰ Hora: {_ampm(hora_cita)}

Escribe *cancelar* si deseas cancelarla.
"""

    # ── Ver precios ───────────────────────────────────────────────────────────
    if accion == "precios":
        texto = "💈 *Servicios BarberIA*\n\n"
        for i, s in SERVICIOS.items():
            precio = f"${s['precio']:,}".replace(",", ".")
            texto += f"{i}️⃣ {s['nombre']} — {precio}\n"
        texto += "\nEscribe *1* para agendar."
        return texto

    # ── Ver barberos ──────────────────────────────────────────────────────────
    if accion == "barberos":
        texto = "💈 *Nuestros barberos*\n\n"
        for b in barberos:
            texto += f"{b['menu_id']}️⃣ {b['nombre']}\n"
        texto += "\nEscribe *1* para agendar."
        return texto

    # ── Ver horarios ──────────────────────────────────────────────────────────
    if accion == "horarios":
        set_state(telefono, {"estado": "consultando_horarios"}, barberia_id)
        return "📅 ¿Para qué fecha quieres ver los horarios?\n\nEjemplos: *hoy*, *mañana*, *lunes*"

    if estado == "consultando_horarios":
        barbero = barberos[0]
        fecha_consulta = fecha if fecha else mensaje
        resultado = obtener_horarios_disponibles(barbero["id"], fecha_consulta, barberia_id)
        _fn = _normalizar_fecha_raw(fecha_consulta)
        if _fn:
            fecha_consulta = _fn.strftime("%Y-%m-%d")
        set_state(telefono, {"estado": "inicio"}, barberia_id)

        if resultado == "domingo":
            return "📅 Los domingos no trabajamos.\n\nEscribe *hola* para ver el menú."
        if resultado == "festivo":
            return "📅 Ese día es festivo y no trabajamos.\n\nEscribe *hola* para ver el menú."
        if resultado == "cerrado":
            return "📅 Ese día la barbería está cerrada.\n\nPrueba con otra fecha 😊"
        if not resultado or resultado is None:
            return "❌ No entendí la fecha. Intenta con *hoy*, *mañana* o *lunes*."

        disponibles   = [h for h in resultado if h["disponible"]]
        fecha_bonita  = formatear_fecha(fecha_consulta) if "-" in str(fecha_consulta) else fecha_consulta

        if not disponibles:
            return f"📅 No hay turnos libres para *{fecha_bonita}*.\n\nEscribe *1* para agendar."

        texto = f"📅 *{fecha_bonita}*\n\n"
        for h in disponibles:
            texto += f"🟢 {_ampm(h['hora'])}\n"
        texto += "\nEscribe *1* para agendar."
        return texto

    # ── Agendar ───────────────────────────────────────────────────────────────
    if accion == "agendar" and estado == "inicio":

        if not cliente:
            set_state(telefono, {"estado": "esperando_nombre"}, barberia_id)
            return "Para agendar tu cita necesito saber tu nombre 😊\n\n¿Cómo te llamas?"

        texto = "💈 *Selecciona un servicio*\n\n"
        for i, s in SERVICIOS.items():
            precio = f"${s['precio']:,}".replace(",", ".")
            texto += f"{i}️⃣ {s['nombre']} — {precio}\n"

        set_state(telefono, {"estado": "esperando_servicio"}, barberia_id)
        return texto

    # ── Esperando nombre ──────────────────────────────────────────────────────
    if estado == "esperando_nombre":
        # Rechazar si parece un comando o número puro
        if mensaje.isdigit():
            return "Por favor escribe tu *nombre completo* para continuar.\nEjemplo: *Juan Pérez*"
        nombre = mensaje.strip().title()
        if len(nombre) < 2:
            return "❌ Escribe tu nombre completo para continuar."
        # Rechazar nombres con solo números o caracteres raros
        if not re.search(r'[a-záéíóúüñA-ZÁÉÍÓÚÜÑ]', nombre):
            return "Por favor escribe tu *nombre* (solo letras).\nEjemplo: *Juan Pérez*"

        texto = f"Hola *{nombre}* 👋\n\n💈 *Selecciona un servicio*\n\n"
        for i, s in SERVICIOS.items():
            precio = f"${s['precio']:,}".replace(",", ".")
            texto += f"{i}️⃣ {s['nombre']} — {precio}\n"

        set_state(telefono, {"estado": "esperando_servicio", "nombre": nombre}, barberia_id)
        return texto

    # ── Esperando servicio ────────────────────────────────────────────────────
    if estado == "esperando_servicio":
        servicio_id = None

        # Primero: número directo
        if mensaje.isdigit() and int(mensaje) in SERVICIOS:
            servicio_id = int(mensaje)
        else:
            # Segundo: buscar por nombre (fuzzy)
            servicio_id = detectar_servicio_por_nombre(mensaje, SERVICIOS)

        if servicio_id is None:
            texto = "Elige el número o escribe el nombre del servicio:\n\n"
            for i, s in SERVICIOS.items():
                precio = f"${s['precio']:,}".replace(",", ".")
                texto += f"{i}️⃣ {s['nombre']} — {precio}\n"
            return texto

        servicio = SERVICIOS[servicio_id]
        texto = f"💈 *{servicio['nombre']} seleccionado*\n\nAhora elige un barbero:\n\n"
        for b in barberos:
            texto += f"{b['menu_id']}️⃣ {b['nombre']}\n"

        set_state(telefono, {
            "estado":   "esperando_barbero",
            "servicio": servicio["nombre"],
            "nombre":   estado_data.get("nombre"),
        }, barberia_id)
        return texto

    # ── Esperando barbero ─────────────────────────────────────────────────────
    if estado == "esperando_barbero":
        barbero = None

        if mensaje.isdigit():
            opcion  = int(mensaje)
            barbero = next((b for b in barberos if b["menu_id"] == opcion), None)

        if not barbero:
            # Coincidencia exacta por nombre
            barbero = next((b for b in barberos if b["nombre"].lower() == mensaje), None)

        if not barbero:
            # Fuzzy: detectar nombre de barbero en el mensaje
            nombre_detectado = detectar_barbero(mensaje, barberos)
            if nombre_detectado:
                barbero = next((b for b in barberos if b["nombre"].lower() == nombre_detectado), None)

        if not barbero:
            texto = "No encontré ese barbero 🤔 Elige una opción:\n\n"
            for b in barberos:
                texto += f"{b['menu_id']}️⃣ {b['nombre']}\n"
            return texto

        set_state(telefono, {
            "estado":        "esperando_cantidad",
            "barbero_id":    barbero["id"],
            "barbero_nombre": barbero["nombre"],
            "servicio":      estado_data.get("servicio"),
            "nombre":        estado_data.get("nombre"),
        }, barberia_id)

        return (
            f"💈 *{barbero['nombre']} seleccionado*\n\n"
            f"¿Para cuántas personas es el turno?\n\n"
            f"Escribe el número (1 a 7)\nEjemplo: *1* si vas solo, *3* si van tres"
        )

    # ── Esperando cantidad ────────────────────────────────────────────────────
    if estado == "esperando_cantidad":
        # Aceptar también "uno", "dos", "tres"...
        _palabras_num = {"uno":1,"una":1,"dos":2,"tres":3,"cuatro":4,
                         "cinco":5,"seis":6,"siete":7,"solo":1,"sola":1,"solito":1}
        _cant_msg = mensaje.strip().lower()
        if _cant_msg in _palabras_num:
            mensaje = str(_palabras_num[_cant_msg])
        if not mensaje.isdigit() or not (1 <= int(mensaje) <= 7):
            return "Escribe un número del *1* al *7* según cuántas personas van.\nEjemplo: *1* si vas solo, *3* si van tres."

        cantidad = int(mensaje)
        set_state(telefono, {
            "estado":        "esperando_fecha",
            "barbero_id":    estado_data["barbero_id"],
            "barbero_nombre": estado_data["barbero_nombre"],
            "servicio":      estado_data.get("servicio"),
            "nombre":        estado_data.get("nombre"),
            "cantidad":      cantidad,
        }, barberia_id)
        return "¿Para qué fecha quieres tu cita?\n\nEjemplos: *hoy*, *mañana*, *lunes*, *viernes*"

    # ── Esperando fecha ───────────────────────────────────────────────────────
    if estado == "esperando_fecha":
        barbero_id = estado_data["barbero_id"]
        cantidad   = estado_data.get("cantidad", 1)
        fecha_final = fecha if fecha else mensaje

        try:
            horarios = obtener_horarios_disponibles(barbero_id, fecha_final, barberia_id)
        except Exception:
            return "❌ No entendí la fecha. Intenta con:\n• *hoy*\n• *mañana*\n• *2026-03-20*"

        if horarios is None:
            return "❌ Hubo un problema consultando los horarios. Intenta de nuevo."
        if horarios == "domingo":
            return "📅 Los domingos no trabajamos.\n\nPrueba con otra fecha 😊"
        if horarios == "festivo":
            return "📅 Ese día es festivo y no trabajamos.\n\nPrueba con otra fecha 😊"
        if horarios == "cerrado":
            return "📅 Ese día la barbería está cerrada.\n\nPrueba con otra fecha 😊"
        if not horarios:
            return "❌ No hay horarios disponibles para ese día.\n\nPrueba con otra fecha."

        _fn = _normalizar_fecha_raw(fecha_final)
        if _fn:
            fecha_final = _fn.strftime("%Y-%m-%d")

        if cantidad > 1:
            from datetime import datetime as _dt, timedelta as _td
            disponibles_set = {h["hora"] for h in horarios if h["disponible"]}
            horarios_disponibles = []
            for h in horarios:
                if not h["disponible"]:
                    continue
                todos_libres = all(
                    (_dt.strptime(h["hora"], "%H:%M") + _td(minutes=30*k)).strftime("%H:%M") in disponibles_set
                    for k in range(1, cantidad)
                )
                if todos_libres:
                    horarios_disponibles.append(h)
                if len(horarios_disponibles) >= 20:
                    break
        else:
            horarios_disponibles = [h for h in horarios if h["disponible"]][:20]

        if not horarios_disponibles:
            if _WAITLIST:
                set_state(telefono, {
                    "estado":         "espera_confirmar",
                    "barbero_id":     barbero_id,
                    "barbero_nombre": estado_data.get("barbero_nombre", ""),
                    "fecha":          fecha_final,
                    "servicio":       estado_data.get("servicio"),
                    "nombre":         estado_data.get("nombre"),
                    "cantidad":       cantidad,
                }, barberia_id)
                fecha_bonita = formatear_fecha(fecha_final)
                return (
                    f"😕 No hay turnos libres para *{fecha_bonita}*.\n\n"
                    f"¿Quieres quedar en lista de espera? Si alguien cancela te avisamos de inmediato.\n\n"
                    f"Responde *sí* para apuntarte o *no* para elegir otra fecha."
                )
            return "❌ No hay turnos libres para ese día.\n\nPrueba con otra fecha."

        fecha_bonita = formatear_fecha(fecha_final)
        texto = f"📅 *{fecha_bonita}*\n\n"
        for i, h in enumerate(horarios_disponibles):
            if cantidad > 1:
                from datetime import datetime as _dt, timedelta as _td
                slots_txt = _ampm(h["hora"])
                for k in range(1, cantidad):
                    sig = (_dt.strptime(h["hora"], "%H:%M") + _td(minutes=30*k)).strftime("%H:%M")
                    slots_txt += f" · {_ampm(sig)}"
                texto += f"{i+1}️⃣ {slots_txt}\n"
            else:
                texto += f"{i+1}️⃣ {_ampm(h['hora'])}\n"
        texto += "\nElige el número del horario."

        set_state(telefono, {
            "estado":         "esperando_hora",
            "barbero_id":     barbero_id,
            "barbero_nombre": estado_data["barbero_nombre"],
            "fecha":          fecha_final,
            "horarios":       horarios_disponibles,
            "servicio":       estado_data.get("servicio"),
            "nombre":         estado_data.get("nombre"),
            "cantidad":       cantidad,
        }, barberia_id)
        return texto

    # ── Esperando hora ────────────────────────────────────────────────────────
    if estado == "esperando_hora":
        horarios = estado_data.get("horarios", [])
        cantidad = estado_data.get("cantidad", 1)

        def _mostrar_horarios():
            fecha_e        = estado_data.get("fecha", "")
            fecha_bonita_e = formatear_fecha(fecha_e) if "-" in str(fecha_e) else fecha_e
            txt = f"Elige el número del horario 👇\n\n📅 *{fecha_bonita_e}*\n\n"
            for idx, h in enumerate(horarios):
                if cantidad > 1:
                    from datetime import datetime as _dt2, timedelta as _td2
                    slots_txt = h["hora"]
                    for k in range(1, cantidad):
                        sig = (_dt2.strptime(h["hora"], "%H:%M") + _td2(minutes=30*k)).strftime("%H:%M")
                        slots_txt += f" · {_ampm(sig)}"
                    txt += f"{idx+1}️⃣ {slots_txt}\n"
                else:
                    txt += f"{idx+1}️⃣ {_ampm(h['hora'])}\n"
            return txt

        index = None

        if mensaje.isdigit():
            index = int(mensaje) - 1
        else:
            # Intentar interpretar la hora desde el texto ("a las 3", "3pm", "10:00")
            from app.services.nlp_service import detectar_hora as _detectar_hora
            hora_escrita = _detectar_hora(mensaje)
            if hora_escrita:
                # Buscar cuál slot corresponde a esa hora
                for idx_h, h in enumerate(horarios):
                    if h["hora"] == hora_escrita or h["hora"].startswith(hora_escrita[:2]):
                        index = idx_h
                        break

        if index is None or index < 0 or index >= len(horarios):
            return _mostrar_horarios()

        hora     = horarios[index]["hora"]
        cantidad = estado_data.get("cantidad", 1)

        from datetime import datetime as _dt, timedelta as _td
        horas_extra = [
            (_dt.strptime(hora, "%H:%M") + _td(minutes=30*k)).strftime("%H:%M")
            for k in range(1, cantidad)
        ]

        cumpleanos = es_semana_cumpleanos(cliente)

        set_state(telefono, {
            "estado":         "esperando_confirmacion",
            "barbero_id":     estado_data["barbero_id"],
            "barbero_nombre": estado_data["barbero_nombre"],
            "fecha":          estado_data["fecha"],
            "hora":           hora,
            "horas_extra":    horas_extra,
            "servicio":       estado_data.get("servicio"),
            "cumpleanos":     cumpleanos,
            "nombre":         estado_data.get("nombre"),
            "cantidad":       cantidad,
        }, barberia_id)

        if cumpleanos:
            return f"""
🎂 *¡Esta semana es tu cumpleaños!*

¡Feliz cumpleaños {nombre_cliente or ''}! 🎉
Tu corte de hoy es *GRATIS* 🎁

💈 Barbero: {estado_data["barbero_nombre"]}
📅 Fecha: {formatear_fecha(estado_data["fecha"])}
⏰ Hora: {_ampm(hora)}

Responde *sí* para confirmar o *no* para elegir otro horario.
"""
        if cantidad > 1:
            lineas_horas = f"⏰ Turno 1: {_ampm(hora)}\n"
            for k, h in enumerate(horas_extra, 2):
                lineas_horas += f"⏰ Turno {k}: {_ampm(h)}\n"
            return f"""
💈 Barbero: {estado_data["barbero_nombre"]}
💇 Servicio: {estado_data.get("servicio", "Corte")}

📅 Fecha: {formatear_fecha(estado_data["fecha"])}
{lineas_horas}
Responde *sí* para confirmar ({cantidad} turnos) o *no* para elegir otro horario.
"""
        return f"""
💈 Barbero: {estado_data["barbero_nombre"]}
💇 Servicio: {estado_data.get("servicio", "Corte")}

📅 Fecha: {formatear_fecha(estado_data["fecha"])}
⏰ Hora: {_ampm(hora)}

Responde *sí* para confirmar o *no* para elegir otro horario.
"""

    # ── Confirmar cita ────────────────────────────────────────────────────────
    if estado == "esperando_confirmacion":

        if _es_si(mensaje):
            cumpleanos     = estado_data.get("cumpleanos", False)
            servicio_final = "🎂 Cumpleaños" if cumpleanos else estado_data.get("servicio")
            cantidad       = estado_data.get("cantidad", 1)
            horas_extra    = estado_data.get("horas_extra", [])

            ok, msg = crear_cita(
                nombre     = nombre_cliente or estado_data.get("nombre") or "Cliente",
                telefono   = telefono_limpio,
                barbero_id = estado_data["barbero_id"],
                fecha      = estado_data["fecha"],
                hora       = estado_data["hora"],
                servicio   = servicio_final,
                barberia_id= barberia_id,
            )
            set_state(telefono, {"estado": "inicio"}, barberia_id)

            if not ok:
                return f"❌ No se pudo crear la cita: {msg}"

            for k, hora_extra in enumerate(horas_extra, 2):
                crear_cita(
                    nombre      = nombre_cliente or estado_data.get("nombre") or "Cliente",
                    telefono    = telefono_limpio,
                    barbero_id  = estado_data["barbero_id"],
                    fecha       = estado_data["fecha"],
                    hora        = hora_extra,
                    servicio    = f"{servicio_final or 'Corte'} (persona {k})",
                    skip_client_check=True,
                    barberia_id = barberia_id,
                )

            if cumpleanos:
                return f"""
✅ *Cita confirmada* 🎂

💈 Barbero: {estado_data["barbero_nombre"]}
🎁 Corte de cumpleaños GRATIS

📅 Fecha: {formatear_fecha(estado_data["fecha"])}
⏰ Hora: {_ampm(estado_data["hora"])}

¡Te esperamos y feliz cumpleaños! 🎉
"""
            if cantidad > 1:
                lineas = f"⏰ Turno 1: {_ampm(estado_data['hora'])}\n"
                for k, h in enumerate(horas_extra, 2):
                    lineas += f"⏰ Turno {k}: {_ampm(h)}\n"
                return f"""
✅ *{cantidad} turnos confirmados*

💈 Barbero: {estado_data["barbero_nombre"]}
💇 Servicio: {servicio_final}

📅 Fecha: {formatear_fecha(estado_data["fecha"])}
{lineas}
¡Los esperamos! 💈
"""
            return f"""
✅ *Cita confirmada*

💈 Barbero: {estado_data["barbero_nombre"]}
💇 Servicio: {estado_data.get("servicio")}

📅 Fecha: {formatear_fecha(estado_data["fecha"])}
⏰ Hora: {_ampm(estado_data["hora"])}

Te esperamos 💈
"""

        elif _es_no(mensaje):
            set_state(telefono, {
                "estado":         "esperando_fecha",
                "barbero_id":     estado_data["barbero_id"],
                "barbero_nombre": estado_data["barbero_nombre"],
                "servicio":       estado_data.get("servicio"),
                "nombre":         estado_data.get("nombre"),
                "cantidad":       estado_data.get("cantidad", 1),
            }, barberia_id)
            return "Perfecto 👍\nDime otra fecha."

        else:
            _hora = estado_data.get("hora", "")
            _cant = estado_data.get("cantidad", 1)
            _extras = estado_data.get("horas_extra", [])
            if _cant > 1:
                _lineas = f"⏰ Turno 1: {_ampm(_hora)}\n"
                for _k, _h in enumerate(_extras, 2):
                    _lineas += f"⏰ Turno {_k}: {_ampm(_h)}\n"
                return (
                    f"💈 {estado_data['barbero_nombre']}\n"
                    f"📅 {formatear_fecha(estado_data['fecha'])}\n{_lineas}\n"
                    f"Responde *sí* para confirmar o *no* para cambiar horario."
                )
            return (
                f"💈 {estado_data['barbero_nombre']}\n"
                f"📅 {formatear_fecha(estado_data['fecha'])}  ⏰ {_ampm(_hora)}\n\n"
                f"Responde *sí* para confirmar o *no* para cambiar horario."
            )

    # ── Lista de espera ───────────────────────────────────────────────────────
    if estado == "espera_confirmar":

        if _es_si(mensaje) and _WAITLIST:
            ok, msg_espera = agregar_a_espera(
                telefono   = telefono_limpio,
                barbero_id = estado_data.get("barbero_id"),
                fecha      = estado_data.get("fecha"),
                servicio   = estado_data.get("servicio"),
                barberia_id= barberia_id,
            )
            set_state(telefono, {"estado": "inicio"}, barberia_id)
            if ok:
                fecha_bonita = formatear_fecha(estado_data.get("fecha", ""))
                return (
                    f"✅ *Quedaste en lista de espera*\n\n"
                    f"📅 {fecha_bonita}\n"
                    f"💈 {estado_data.get('barbero_nombre', '')}\n\n"
                    f"Si se libera un turno te avisamos por aquí de inmediato 🔔\n\n"
                    f"Escribe *hola* para volver al menú."
                )
            return f"❌ {msg_espera}\n\nEscribe *hola* para volver al menú."

        elif _es_no(mensaje):
            set_state(telefono, {
                "estado":         "esperando_fecha",
                "barbero_id":     estado_data.get("barbero_id"),
                "barbero_nombre": estado_data.get("barbero_nombre", ""),
                "servicio":       estado_data.get("servicio"),
                "nombre":         estado_data.get("nombre"),
                "cantidad":       estado_data.get("cantidad", 1),
            }, barberia_id)
            return "Perfecto. ¿Para qué otra fecha quieres tu cita?\n\nEjemplos: *mañana*, *lunes*"

        _fecha_espera = formatear_fecha(estado_data.get("fecha", "")) if estado_data.get("fecha") else ""
        return (
            f"😕 No hay turnos libres para *{_fecha_espera}*.\n\n"
            f"Responde *sí* para quedar en lista de espera o *no* para elegir otra fecha."
        )

    # ── Confirmar slot de lista de espera ─────────────────────────────────────
    if estado == "espera_slot_ofrecido":
        if _es_si(mensaje):
            # Intentar agendar directamente el slot ofrecido
            ok, msg_c = crear_cita(
                nombre      = nombre_cliente or estado_data.get("nombre") or "Cliente",
                telefono    = telefono_limpio,
                barbero_id  = estado_data.get("barbero_id"),
                fecha       = estado_data.get("fecha"),
                hora        = estado_data.get("hora"),
                servicio    = estado_data.get("servicio") or "Corte",
                barberia_id = barberia_id,
            )
            set_state(telefono, {"estado": "inicio"}, barberia_id)
            if ok:
                fecha_bonita = formatear_fecha(estado_data.get("fecha", ""))
                return (
                    f"✅ *¡Turno confirmado!*\n\n"
                    f"💈 {estado_data.get('barbero_nombre', '')}\n"
                    f"📅 {fecha_bonita}\n"
                    f"⏰ {_ampm(estado_data.get('hora', ''))}\n\n"
                    f"¡Te esperamos! Escribe *hola* para ver el menú."
                )
            # Si el slot ya fue tomado, ofrecer menú
            return (
                f"😕 Lo sentimos, ese turno ya fue tomado por otro cliente.\n\n"
                f"Escribe *1* para buscar otro horario disponible."
            )

        elif _es_no(mensaje):
            set_state(telefono, {"estado": "inicio"}, barberia_id)
            return "Entendido 👍 Si cambias de opinión escribe *hola* y empieza de nuevo.\n\nEscribe *hola* para ver el menú."

        # Recordatorio del slot ofrecido
        fecha_bonita = formatear_fecha(estado_data.get("fecha", ""))
        return (
            f"🔔 Tienes un turno disponible esperando tu respuesta:\n\n"
            f"📅 {fecha_bonita}  ⏰ {_ampm(estado_data.get('hora', ''))}\n"
            f"💈 {estado_data.get('barbero_nombre', '')}\n\n"
            f"Responde *sí* para confirmar o *no* para rechazar."
        )

    # ── Encuesta post-corte ───────────────────────────────────────────────────
    if estado == "esperando_encuesta":
        if mensaje.isdigit() and 1 <= int(mensaje) <= 5:
            calificacion = int(mensaje)
            cita_id      = estado_data.get("encuesta_cita_id")

            try:
                from app.models.encuesta import Encuesta
                from app.extensions import db as _db
                enc = Encuesta(
                    barberia_id  = barberia_id,
                    cita_id      = cita_id,
                    cliente_id   = cliente.id if cliente else None,
                    calificacion = calificacion,
                )
                _db.session.add(enc)
                _db.session.commit()
            except Exception as _e:
                print(f"⚠ Error guardando encuesta: {_e}")
                try:
                    from app.extensions import db as _db2
                    _db2.session.rollback()
                except Exception:
                    pass

            set_state(telefono, {
                "estado":                  "esperando_comentario_encuesta",
                "encuesta_cita_id":        cita_id,
                "encuesta_calificacion":   calificacion,
            }, barberia_id)

            estrellas = "⭐" * calificacion
            if calificacion >= 4:
                return (
                    f"¡Gracias! {estrellas}\n\n"
                    f"Nos alegra que hayas tenido una buena experiencia 😊\n\n"
                    f"¿Quieres dejarnos un comentario?\n"
                    f"_(Escribe tu opinión o *no* para terminar)_"
                )
            elif calificacion == 3:
                return (
                    f"Gracias por tu calificación {estrellas}\n\n"
                    f"¿Qué podríamos mejorar?\n"
                    f"_(Escribe tu opinión o *no* para terminar)_"
                )
            else:
                return (
                    f"Lamentamos no haberte dado una buena experiencia {estrellas}\n\n"
                    f"¿Qué salió mal? Nos ayudas a mejorar.\n"
                    f"_(Escribe tu opinión o *no* para terminar)_"
                )

        return (
            "⭐ *Encuesta de satisfacción*\n\n"
            "¿Cómo estuvo tu visita? Responde con un número del *1* al *5*:\n\n"
            "1️⃣ Muy malo\n2️⃣ Malo\n3️⃣ Regular\n4️⃣ Bueno\n5️⃣ Excelente"
        )

    if estado == "esperando_comentario_encuesta":
        if mensaje not in ("no", "n", "no gracias", "skip"):
            comentario = mensaje.strip()[:500]
            cita_id    = estado_data.get("encuesta_cita_id")
            try:
                from app.models.encuesta import Encuesta
                from app.extensions import db as _db
                enc = Encuesta.query.filter_by(cita_id=cita_id).order_by(Encuesta.id.desc()).first()
                if enc:
                    enc.comentario = comentario
                    _db.session.commit()
            except Exception:
                try:
                    from app.extensions import db as _db2
                    _db2.session.rollback()
                except Exception:
                    pass

        set_state(telefono, {"estado": "inicio"}, barberia_id)
        return "¡Gracias por tu opinión! 🙏 Nos ayuda a mejorar cada día.\n\nEscribe *hola* para ver el menú."

    # ── Reagendar — iniciar ───────────────────────────────────────────────────
    if accion == "reagendar":

        cita = obtener_cita_cliente(telefono_limpio, barberia_id)

        if not cita:
            set_state(telefono, {"estado": "inicio"}, barberia_id)
            return "❌ No tienes citas registradas para reagendar.\n\nEscribe *1* para agendar una nueva."

        barbero  = Barbero.query.get(cita.barbero_id)
        hora_str = cita.hora.strftime("%H:%M")

        set_state(telefono, {
            "estado":         "reagendando_fecha",
            "cita_vieja_id":  cita.id,
            "barbero_id":     cita.barbero_id,
            "barbero_nombre": barbero.nombre if barbero else "Barbero",
            "servicio":       cita.servicio,
            "fecha_vieja":    str(cita.fecha),
            "hora_vieja":     hora_str,
        }, barberia_id)

        return f"""
🔄 *Reagendar cita*

Tu cita actual:
📅 {formatear_fecha(str(cita.fecha))}  ⏰ {_ampm(hora_str)}
💈 {barbero.nombre if barbero else ""}

¿Para qué nueva fecha la quieres?
Ejemplos: *mañana*, *lunes*, *viernes*
"""

    # ── Reagendando — nueva fecha ─────────────────────────────────────────────
    if estado == "reagendando_fecha":
        barbero_id   = estado_data["barbero_id"]
        fecha_final  = fecha if fecha else mensaje

        try:
            horarios = obtener_horarios_disponibles(barbero_id, fecha_final, barberia_id)
        except Exception:
            return "❌ No entendí la fecha. Intenta con *mañana*, *lunes* o *2026-04-10*."

        if horarios is None:
            return "❌ Problema consultando horarios. Intenta de nuevo."
        if horarios == "domingo":
            return "📅 Los domingos no trabajamos. Prueba otra fecha."
        if horarios == "festivo":
            return "📅 Ese día es festivo. Prueba otra fecha."
        if horarios == "cerrado":
            return "📅 Ese día la barbería está cerrada. Prueba otra fecha."
        if not horarios:
            return "❌ No hay horarios para ese día. Prueba otra fecha."

        _fn = _normalizar_fecha_raw(fecha_final)
        if _fn:
            fecha_final = _fn.strftime("%Y-%m-%d")

        disponibles = [h for h in horarios if h["disponible"]][:20]
        if not disponibles:
            return "❌ No hay turnos libres ese día. Prueba otra fecha."

        fecha_bonita = formatear_fecha(fecha_final)
        texto = f"📅 *{fecha_bonita}*\n\n"
        for i, h in enumerate(disponibles):
            texto += f"{i+1}️⃣ {_ampm(h['hora'])}\n"
        texto += "\nElige el número del horario."

        set_state(telefono, {
            **estado_data,
            "estado":   "reagendando_hora",
            "fecha":    fecha_final,
            "horarios": disponibles,
        }, barberia_id)
        return texto

    # ── Reagendando — hora ────────────────────────────────────────────────────
    if estado == "reagendando_hora":
        horarios = estado_data.get("horarios", [])

        def _mostrar_horarios_reag():
            fecha_r = estado_data.get("fecha", "")
            fecha_bonita_r = formatear_fecha(fecha_r) if "-" in str(fecha_r) else fecha_r
            txt = f"Elige el número del horario 👇\n\n📅 *{fecha_bonita_r}*\n\n"
            for idx, h in enumerate(horarios):
                txt += f"{idx+1}️⃣ {_ampm(h['hora'])}\n"
            return txt

        if not mensaje.isdigit():
            return _mostrar_horarios_reag()
        index = int(mensaje) - 1
        if index < 0 or index >= len(horarios):
            return _mostrar_horarios_reag()

        hora = horarios[index]["hora"]
        set_state(telefono, {**estado_data, "estado": "reagendando_confirmar", "hora": hora}, barberia_id)

        return f"""
🔄 *Confirmar reagenda*

💈 {estado_data["barbero_nombre"]}
💇 {estado_data.get("servicio") or "Corte"}

📅 Nueva fecha: {formatear_fecha(estado_data["fecha"])}
⏰ Nueva hora:  {_ampm(hora)}

Responde *sí* para confirmar o *no* para elegir otra hora.
"""

    # ── Reagendando — confirmar ───────────────────────────────────────────────
    if estado == "reagendando_confirmar":

        if _es_no(mensaje):
            set_state(telefono, {**estado_data, "estado": "reagendando_hora"}, barberia_id)
            horarios_lista = estado_data.get("horarios", [])
            fecha_bonita   = formatear_fecha(estado_data.get("fecha", ""))
            texto_horas    = f"📅 *{fecha_bonita}*\n\n"
            for i, h in enumerate(horarios_lista):
                texto_horas += f"{i+1}️⃣ {_ampm(h['hora'])}\n"
            texto_horas += "\nElige el número del horario."
            return texto_horas

        if _es_si(mensaje):
            ok, msg = crear_cita(
                nombre      = nombre_cliente or "Cliente",
                telefono    = telefono_limpio,
                barbero_id  = estado_data["barbero_id"],
                fecha       = estado_data["fecha"],
                hora        = estado_data["hora"],
                servicio    = estado_data.get("servicio"),
                skip_client_check=True,
                barberia_id = barberia_id,
            )
            if not ok:
                set_state(telefono, {"estado": "inicio"}, barberia_id)
                return f"❌ No se pudo reagendar: {msg}\n\nTu cita anterior sigue activa. Escribe *hola* para volver al menú."

            cancelar_cita(telefono_limpio, estado_data["fecha_vieja"], estado_data["hora_vieja"], barberia_id)
            set_state(telefono, {"estado": "inicio"}, barberia_id)

            return f"""
✅ *Cita reagendada*

💈 {estado_data["barbero_nombre"]}
💇 {estado_data.get("servicio") or "Corte"}
📅 {formatear_fecha(estado_data["fecha"])}
⏰ {_ampm(estado_data["hora"])}

¡Te esperamos! Escribe *hola* para volver al menú.
"""

        _hora_r = estado_data.get("hora", "")
        return (
            f"🔄 *Confirmar reagenda*\n\n"
            f"💈 {estado_data.get('barbero_nombre', '')}\n"
            f"📅 {formatear_fecha(estado_data.get('fecha', ''))}  ⏰ {_ampm(_hora_r)}\n\n"
            f"Responde *sí* para confirmar o *no* para cambiar la hora."
        )

    # ── Ayuda ─────────────────────────────────────────────────────────────────
    if accion == "ayuda":
        return """
🆘 *Ayuda BarberIA*

Puedes escribirme de forma natural o usar el menú:

• *hola* — Ver menú principal
• *1* — Agendar cita
• *6* — Reagendar cita
• *cancelar* — Cancelar tu cita
• *0* — Volver al menú en cualquier momento
"""

    # ── Fallbacks por estado ──────────────────────────────────────────────────
    if estado == "esperando_nombre":
        return "¿Cómo te llamás? Escribí tu nombre para continuar."

    if estado == "esperando_servicio":
        texto = "Elegí el número del servicio:\n\n"
        for i, s in SERVICIOS.items():
            precio = f"${s['precio']:,}".replace(",", ".")
            texto += f"{i}️⃣ {s['nombre']} — {precio}\n"
        return texto

    if estado == "esperando_barbero":
        texto = "Elegí un barbero:\n\n"
        for b in barberos:
            texto += f"{b['menu_id']}️⃣ {b['nombre']}\n"
        return texto

    if estado == "esperando_cantidad":
        return "¿Para cuántas personas es el turno?\n\nEscribí un número del *1* al *7*."

    if estado == "esperando_fecha":
        return "¿Para qué fecha querés la cita?\n\nEjemplos: *hoy*, *mañana*, *lunes*, *viernes*"

    if estado == "esperando_hora":
        _hs = estado_data.get("horarios", [])
        if _hs:
            _fe = estado_data.get("fecha", "")
            _fb = formatear_fecha(_fe) if "-" in str(_fe) else _fe
            txt = f"Elige el número del horario 👇\n\n📅 *{_fb}*\n\n"
            for _i, _h in enumerate(_hs):
                txt += f"{_i+1}️⃣ {_ampm(_h['hora'])}\n"
            return txt
        return "Elige el número del horario."

    if estado == "esperando_confirmacion":
        _hora_f = estado_data.get("hora", "")
        return (
            f"💈 {estado_data.get('barbero_nombre', '')}\n"
            f"📅 {formatear_fecha(estado_data.get('fecha', ''))}  ⏰ {_ampm(_hora_f)}\n\n"
            f"Responde *sí* para confirmar o *no* para cambiar horario."
        )

    if estado == "confirmando_cancelacion":
        return (
            f"❗ *¿Cancelar tu cita?*\n\n"
            f"📅 {formatear_fecha(estado_data.get('fecha', ''))}  "
            f"⏰ {_ampm(estado_data.get('hora', ''))}\n\n"
            f"Responde *sí* para cancelar o *no* para mantener tu cita."
        )

    if estado == "reagendando_fecha":
        return "¿Para qué nueva fecha quieres la cita?\n\nEjemplos: *mañana*, *lunes*, *viernes*"

    if estado == "reagendando_hora":
        _hs_r = estado_data.get("horarios", [])
        if _hs_r:
            _fe_r = estado_data.get("fecha", "")
            _fb_r = formatear_fecha(_fe_r) if "-" in str(_fe_r) else _fe_r
            txt = f"Elige el número del horario 👇\n\n📅 *{_fb_r}*\n\n"
            for _i, _h in enumerate(_hs_r):
                txt += f"{_i+1}️⃣ {_ampm(_h['hora'])}\n"
            return txt

    if estado == "reagendando_confirmar":
        _hora_rc = estado_data.get("hora", "")
        return (
            f"🔄 *Confirmar reagenda*\n\n"
            f"💈 {estado_data.get('barbero_nombre', '')}\n"
            f"📅 {formatear_fecha(estado_data.get('fecha', ''))}  ⏰ {_ampm(_hora_rc)}\n\n"
            f"Responde *sí* para confirmar o *no* para cambiar la hora."
        )

    if estado == "espera_confirmar":
        _fecha_ec = formatear_fecha(estado_data.get("fecha", "")) if estado_data.get("fecha") else ""
        return (
            f"😕 No hay turnos libres para *{_fecha_ec}*.\n\n"
            f"Responde *sí* para quedar en lista de espera o *no* para elegir otra fecha."
        )

    if estado == "esperando_encuesta":
        return (
            "⭐ *Encuesta de satisfacción*\n\n"
            "¿Cómo estuvo tu visita? Responde con un número del *1* al *5*:\n\n"
            "1️⃣ Muy malo\n2️⃣ Malo\n3️⃣ Regular\n4️⃣ Bueno\n5️⃣ Excelente"
        )

    if estado == "esperando_comentario_encuesta":
        return "¿Quieres añadir un comentario? _(Escribe tu opinión o *no* para terminar)_"

    return menu_principal(nombre_cliente)
