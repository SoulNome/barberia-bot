from app.services.nlp_service import interpretar_mensaje
from app.services.disponibilidad_service import obtener_horarios_disponibles, normalizar_fecha as _normalizar_fecha_raw
from app.services.agenda_service import crear_cita, obtener_cita_cliente, cancelar_cita
from app.services.clientes_service import obtener_cliente_por_telefono
from app.services.state_service import get_state, set_state
from app.models import Barbero
from datetime import datetime, date, timedelta

# Import waitlist service (soft — graceful if not available yet)
try:
    from app.services.lista_espera_service import agregar_a_espera
    _WAITLIST = True
except ImportError:
    _WAITLIST = False

DIAS_ES   = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES_ES  = ["enero", "febrero", "marzo", "abril", "mayo", "junio",
             "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]

def es_semana_cumpleanos(cliente):
    if not cliente or not cliente.fecha_cumpleanos:
        return False
    try:
        hoy = date.today()
        cumple = cliente.fecha_cumpleanos.replace(year=hoy.year)
        lunes  = cumple - timedelta(days=cumple.weekday())
        return lunes <= hoy <= lunes + timedelta(days=6)
    except Exception:
        return False


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
6️⃣ Reagendar cita
7️⃣ Ver precios
8️⃣ Ayuda

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
            accion = "reagendar"
        elif mensaje == "7":
            accion = "precios"
        elif mensaje == "8":
            accion = "ayuda"

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
            return (
                f"❗ *¿Cancelar tu cita?*\n\n"
                f"📅 {estado_data.get('fecha', '')}  "
                f"⏰ {estado_data.get('hora', '')}\n\n"
                f"1️⃣ Sí, cancelar\n"
                f"2️⃣ No, mantener cita"
            )

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

        # Normalizar para mostrar fecha bonita
        _fn = _normalizar_fecha_raw(fecha_consulta)
        if _fn:
            fecha_consulta = _fn.strftime("%Y-%m-%d")

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

        if not mensaje.isdigit() or int(mensaje) not in SERVICIOS:
            texto = "Elige el número del servicio:\n\n"
            for i, s in SERVICIOS.items():
                precio = f"${s['precio']:,}".replace(",", ".")
                texto += f"{i}️⃣ {s['nombre']} — {precio}\n"
            return texto

        servicio_id = int(mensaje)

        servicio = SERVICIOS[servicio_id]

        texto = f"💈 *{servicio['nombre']} seleccionado*\n\nAhora elige un barbero:\n\n"

        for b in barberos:
            texto += f"{b['menu_id']}️⃣ {b['nombre']}\n"

        set_state(telefono, {
            "estado": "esperando_barbero",
            "servicio": servicio["nombre"],
            "nombre": estado_data.get("nombre")
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
            "estado": "esperando_cantidad",
            "barbero_id": barbero["id"],
            "barbero_nombre": barbero["nombre"],
            "servicio": estado_data.get("servicio"),
            "nombre": estado_data.get("nombre")
        })

        return f"💈 *{barbero['nombre']} seleccionado*\n\n¿Para cuántas personas es el turno?\n\nEscribe el número (1 a 7)\nEjemplo: *1* si vas solo, *3* si van tres"

    # ------------------------------------------------
    # ESPERANDO CANTIDAD (1 o 2 turnos)
    # ------------------------------------------------

    if estado == "esperando_cantidad":

        if not mensaje.isdigit() or not (1 <= int(mensaje) <= 7):
            return "Escribe un número del 1 al 7 según cuántas personas van.\nEjemplo: *1* si vas solo, *3* si van tres."

        cantidad = int(mensaje)

        set_state(telefono, {
            "estado": "esperando_fecha",
            "barbero_id": estado_data["barbero_id"],
            "barbero_nombre": estado_data["barbero_nombre"],
            "servicio": estado_data.get("servicio"),
            "nombre": estado_data.get("nombre"),
            "cantidad": cantidad
        })

        return "¿Para qué fecha quieres tu cita?\n\nEjemplos: *hoy*, *mañana*, *lunes*, *viernes*"

    # ------------------------------------------------
    # ESPERANDO FECHA
    # FIX: manejo robusto cuando NLP no parsea la fecha
    # ------------------------------------------------

    if estado == "esperando_fecha":

        barbero_id = estado_data["barbero_id"]
        cantidad   = estado_data.get("cantidad", 1)

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

        # Normalizar fecha a ISO antes de guardar en estado
        _fn = _normalizar_fecha_raw(fecha_final)
        if _fn:
            fecha_final = _fn.strftime("%Y-%m-%d")

        if cantidad > 1:
            # Para N personas: solo mostrar turnos donde hay N slots consecutivos libres
            from datetime import datetime as _dt, timedelta as _td
            disponibles_set = {h["hora"] for h in horarios if h["disponible"]}
            horarios_disponibles = []
            for h in horarios:
                if not h["disponible"]:
                    continue
                # Verificar que los N-1 slots siguientes también estén libres
                todos_libres = True
                for k in range(1, cantidad):
                    sig = (_dt.strptime(h["hora"], "%H:%M") + _td(minutes=30*k)).strftime("%H:%M")
                    if sig not in disponibles_set:
                        todos_libres = False
                        break
                if todos_libres:
                    horarios_disponibles.append(h)
                if len(horarios_disponibles) >= 9:
                    break
        else:
            horarios_disponibles = [h for h in horarios if h["disponible"]][:9]

        if not horarios_disponibles:
            if _WAITLIST:
                set_state(telefono, {
                    "estado":      "espera_confirmar",
                    "barbero_id":  barbero_id,
                    "barbero_nombre": estado_data.get("barbero_nombre", ""),
                    "fecha":       fecha_final,
                    "servicio":    estado_data.get("servicio"),
                    "nombre":      estado_data.get("nombre"),
                    "cantidad":    cantidad,
                })
                fecha_bonita = formatear_fecha(fecha_final)
                return (
                    f"😕 No hay turnos libres para *{fecha_bonita}*.\n\n"
                    f"¿Quieres quedar en lista de espera? Si alguien cancela te avisamos de inmediato.\n\n"
                    f"1️⃣ Sí, apuntarme\n2️⃣ No, elegir otra fecha"
                )
            return "❌ No hay turnos libres para ese día.\n\nPrueba con otra fecha."

        fecha_bonita = formatear_fecha(fecha_final)
        texto = f"📅 *{fecha_bonita}*\n\n"

        for i, h in enumerate(horarios_disponibles):
            if cantidad > 1:
                from datetime import datetime as _dt, timedelta as _td
                slots_txt = h["hora"]
                for k in range(1, cantidad):
                    sig = (_dt.strptime(h["hora"], "%H:%M") + _td(minutes=30*k)).strftime("%H:%M")
                    slots_txt += f" · {sig}"
                texto += f"{i+1}️⃣ {slots_txt}\n"
            else:
                texto += f"{i+1}️⃣ {h['hora']}\n"

        texto += "\nElige el número del horario."

        set_state(telefono, {
            "estado": "esperando_hora",
            "barbero_id": barbero_id,
            "barbero_nombre": estado_data["barbero_nombre"],
            "fecha": fecha_final,
            "horarios": horarios_disponibles,
            "servicio": estado_data.get("servicio"),
            "nombre": estado_data.get("nombre"),
            "cantidad": cantidad
        })

        return texto

    # ------------------------------------------------
    # ESPERANDO HORA
    # ------------------------------------------------

    if estado == "esperando_hora":

        horarios = estado_data.get("horarios", [])
        cantidad = estado_data.get("cantidad", 1)

        def _mostrar_horarios():
            fecha_e = estado_data.get("fecha", "")
            fecha_bonita_e = formatear_fecha(fecha_e) if "-" in str(fecha_e) else fecha_e
            txt = f"Elegí el número del horario 👇\n\n📅 *{fecha_bonita_e}*\n\n"
            for idx, h in enumerate(horarios):
                if cantidad > 1:
                    from datetime import datetime as _dt2, timedelta as _td2
                    slots_txt = h["hora"]
                    for k in range(1, cantidad):
                        sig = (_dt2.strptime(h["hora"], "%H:%M") + _td2(minutes=30*k)).strftime("%H:%M")
                        slots_txt += f" · {sig}"
                    txt += f"{idx+1}️⃣ {slots_txt}\n"
                else:
                    txt += f"{idx+1}️⃣ {h['hora']}\n"
            return txt

        if not mensaje.isdigit():
            return _mostrar_horarios()

        index = int(mensaje) - 1

        if index < 0 or index >= len(horarios):
            return _mostrar_horarios()

        hora = horarios[index]["hora"]
        cantidad = estado_data.get("cantidad", 1)

        # Calcular horas extra si son N personas
        from datetime import datetime as _dt, timedelta as _td
        horas_extra = []
        for k in range(1, cantidad):
            horas_extra.append((_dt.strptime(hora, "%H:%M") + _td(minutes=30*k)).strftime("%H:%M"))
        hora2 = horas_extra[0] if horas_extra else None

        cumpleanos = es_semana_cumpleanos(cliente)

        set_state(telefono, {
            "estado": "esperando_confirmacion",
            "barbero_id": estado_data["barbero_id"],
            "barbero_nombre": estado_data["barbero_nombre"],
            "fecha": estado_data["fecha"],
            "hora": hora,
            "hora2": hora2,
            "horas_extra": horas_extra,
            "servicio": estado_data.get("servicio"),
            "cumpleanos": cumpleanos,
            "nombre": estado_data.get("nombre"),
            "cantidad": cantidad
        })

        if cumpleanos:
            return f"""
🎂 *¡Esta semana es tu cumpleaños!*

¡Feliz cumpleaños {nombre_cliente or ''}! 🎉
Tu corte de hoy es *GRATIS* 🎁

💈 Barbero: {estado_data["barbero_nombre"]}
📅 Fecha: {estado_data["fecha"]}
⏰ Hora: {hora}

1️⃣ Confirmar cita
2️⃣ Elegir otro horario
"""

        if cantidad > 1:
            lineas_horas = f"⏰ Turno 1: {hora}\n"
            for k, h in enumerate(horas_extra, 2):
                lineas_horas += f"⏰ Turno {k}: {h}\n"
            return f"""
💈 Barbero: {estado_data["barbero_nombre"]}
💇 Servicio: {estado_data.get("servicio", "Corte")}

📅 Fecha: {estado_data["fecha"]}
{lineas_horas}
1️⃣ Confirmar ({cantidad} turnos)
2️⃣ Elegir otro horario
"""

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

            cumpleanos     = estado_data.get("cumpleanos", False)
            servicio_final = "🎂 Cumpleaños" if cumpleanos else estado_data.get("servicio")
            cantidad       = estado_data.get("cantidad", 1)
            horas_extra    = estado_data.get("horas_extra", [])

            ok, msg = crear_cita(
                nombre=nombre_cliente or estado_data.get("nombre") or "Cliente",
                telefono=telefono_limpio,
                barbero_id=estado_data["barbero_id"],
                fecha=estado_data["fecha"],
                hora=estado_data["hora"],
                servicio=servicio_final
            )

            set_state(telefono, {"estado": "inicio"})

            if not ok:
                return f"❌ No se pudo crear la cita: {msg}"

            # Crear turnos extra si son más de 1 persona
            for k, hora_extra in enumerate(horas_extra, 2):
                crear_cita(
                    nombre=nombre_cliente or estado_data.get("nombre") or "Cliente",
                    telefono=telefono_limpio,
                    barbero_id=estado_data["barbero_id"],
                    fecha=estado_data["fecha"],
                    hora=hora_extra,
                    servicio=f"{servicio_final or 'Corte'} (persona {k})",
                    skip_client_check=True
                )

            if cumpleanos:
                return f"""
✅ *Cita confirmada* 🎂

💈 Barbero: {estado_data["barbero_nombre"]}
🎁 Corte de cumpleaños GRATIS

📅 Fecha: {estado_data["fecha"]}
⏰ Hora: {estado_data["hora"]}

¡Te esperamos y feliz cumpleaños! 🎉
"""

            if cantidad > 1:
                lineas = f"⏰ Turno 1: {estado_data['hora']}\n"
                for k, h in enumerate(horas_extra, 2):
                    lineas += f"⏰ Turno {k}: {h}\n"
                return f"""
✅ *{cantidad} turnos confirmados*

💈 Barbero: {estado_data["barbero_nombre"]}
💇 Servicio: {servicio_final}

📅 Fecha: {estado_data["fecha"]}
{lineas}
¡Los esperamos! 💈
"""

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
                "servicio": estado_data.get("servicio"),
                "nombre": estado_data.get("nombre"),
                "cantidad": estado_data.get("cantidad", 1),
            })

            return "Perfecto 👍\nDime otra fecha."

        else:
            # re-mostrar resumen de la cita
            _hora = estado_data.get("hora", "")
            _cant = estado_data.get("cantidad", 1)
            _extras = estado_data.get("horas_extra", [])
            if _cant > 1:
                _lineas = f"⏰ Turno 1: {_hora}\n"
                for _k, _h in enumerate(_extras, 2):
                    _lineas += f"⏰ Turno {_k}: {_h}\n"
                return (
                    f"💈 {estado_data['barbero_nombre']}\n"
                    f"📅 {estado_data['fecha']}\n{_lineas}\n"
                    f"Respondé *1* para confirmar o *2* para cambiar horario."
                )
            return (
                f"💈 {estado_data['barbero_nombre']}\n"
                f"📅 {estado_data['fecha']}  ⏰ {_hora}\n\n"
                f"Respondé *1* para confirmar o *2* para cambiar horario."
            )

    # ------------------------------------------------
    # LISTA DE ESPERA — confirmación
    # ------------------------------------------------

    if estado == "espera_confirmar":

        if mensaje == "1" and _WAITLIST:
            ok, msg_espera = agregar_a_espera(
                telefono   = telefono_limpio,
                barbero_id = estado_data.get("barbero_id"),
                fecha      = estado_data.get("fecha"),
                servicio   = estado_data.get("servicio"),
            )
            set_state(telefono, {"estado": "inicio"})
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

        elif mensaje == "2":
            set_state(telefono, {
                "estado":        "esperando_fecha",
                "barbero_id":    estado_data.get("barbero_id"),
                "barbero_nombre": estado_data.get("barbero_nombre", ""),
                "servicio":      estado_data.get("servicio"),
                "nombre":        estado_data.get("nombre"),
                "cantidad":      estado_data.get("cantidad", 1),
            })
            return "Perfecto. ¿Para qué otra fecha quieres tu cita?\n\nEjemplos: *mañana*, *lunes*"

        _fecha_espera = formatear_fecha(estado_data.get("fecha", "")) if estado_data.get("fecha") else ""
        return (
            f"😕 No hay turnos libres para *{_fecha_espera}*.\n\n"
            f"1️⃣ Sí, apuntarme a lista de espera\n"
            f"2️⃣ No, elegir otra fecha"
        )

    # ------------------------------------------------
    # REAGENDAR — iniciar
    # ------------------------------------------------

    if accion == "reagendar":

        cita = obtener_cita_cliente(telefono_limpio)

        if not cita:
            set_state(telefono, {"estado": "inicio"})
            return "❌ No tienes citas registradas para reagendar.\n\nEscribe *1* para agendar una nueva."

        barbero = Barbero.query.get(cita.barbero_id)
        hora_str = cita.hora.strftime("%H:%M")

        set_state(telefono, {
            "estado":        "reagendando_fecha",
            "cita_vieja_id": cita.id,
            "barbero_id":    cita.barbero_id,
            "barbero_nombre": barbero.nombre if barbero else "Barbero",
            "servicio":      cita.servicio,
            "fecha_vieja":   str(cita.fecha),
            "hora_vieja":    hora_str,
        })

        return f"""
🔄 *Reagendar cita*

Tu cita actual:
📅 {cita.fecha}  ⏰ {hora_str}
💈 {barbero.nombre if barbero else ""}

¿Para qué nueva fecha la quieres?
Ejemplos: *mañana*, *lunes*, *2026-04-10*
"""

    # ------------------------------------------------
    # REAGENDANDO — esperando nueva fecha
    # ------------------------------------------------

    if estado == "reagendando_fecha":

        barbero_id   = estado_data["barbero_id"]
        fecha_final  = fecha if fecha else mensaje

        try:
            horarios = obtener_horarios_disponibles(barbero_id, fecha_final)
        except Exception:
            return "❌ No entendí la fecha. Intenta con *mañana*, *lunes* o *2026-04-10*."

        if horarios is None:
            return "❌ Problema consultando horarios. Intenta de nuevo."
        if horarios == "domingo":
            return "📅 Los domingos no trabajamos. Prueba otra fecha."
        if horarios == "festivo":
            return "📅 Ese día es festivo. Prueba otra fecha."
        if not horarios:
            return "❌ No hay horarios para ese día. Prueba otra fecha."

        # Normalizar fecha a ISO antes de guardar en estado
        _fn = _normalizar_fecha_raw(fecha_final)
        if _fn:
            fecha_final = _fn.strftime("%Y-%m-%d")

        disponibles = [h for h in horarios if h["disponible"]][:9]

        if not disponibles:
            return "❌ No hay turnos libres ese día. Prueba otra fecha."

        fecha_bonita = formatear_fecha(fecha_final)
        texto = f"📅 *{fecha_bonita}*\n\n"
        for i, h in enumerate(disponibles):
            texto += f"{i+1}️⃣ {h['hora']}\n"
        texto += "\nElige el número del horario."

        set_state(telefono, {
            **estado_data,
            "estado":   "reagendando_hora",
            "fecha":    fecha_final,
            "horarios": disponibles,
        })

        return texto

    # ------------------------------------------------
    # REAGENDANDO — esperando hora
    # ------------------------------------------------

    if estado == "reagendando_hora":

        horarios = estado_data.get("horarios", [])

        def _mostrar_horarios_reag():
            fecha_r = estado_data.get("fecha", "")
            fecha_bonita_r = formatear_fecha(fecha_r) if "-" in str(fecha_r) else fecha_r
            txt = f"Elegí el número del horario 👇\n\n📅 *{fecha_bonita_r}*\n\n"
            for idx, h in enumerate(horarios):
                txt += f"{idx+1}️⃣ {h['hora']}\n"
            return txt

        if not mensaje.isdigit():
            return _mostrar_horarios_reag()

        index   = int(mensaje) - 1

        if index < 0 or index >= len(horarios):
            return _mostrar_horarios_reag()

        hora = horarios[index]["hora"]

        set_state(telefono, {
            **estado_data,
            "estado": "reagendando_confirmar",
            "hora":   hora,
        })

        return f"""
🔄 *Confirmar reagenda*

💈 {estado_data["barbero_nombre"]}
💇 {estado_data.get("servicio") or "Corte"}

📅 Nueva fecha: {estado_data["fecha"]}
⏰ Nueva hora:  {hora}

1️⃣ Confirmar cambio
2️⃣ Elegir otra hora
"""

    # ------------------------------------------------
    # REAGENDANDO — confirmar
    # ------------------------------------------------

    if estado == "reagendando_confirmar":

        if mensaje == "2":
            set_state(telefono, {
                **estado_data,
                "estado": "reagendando_hora",
            })
            horarios_lista = estado_data.get("horarios", [])
            fecha_bonita   = formatear_fecha(estado_data.get("fecha", ""))
            texto_horas    = f"📅 *{fecha_bonita}*\n\n"
            for i, h in enumerate(horarios_lista):
                texto_horas += f"{i+1}️⃣ {h['hora']}\n"
            texto_horas += "\nElige el número del horario."
            return texto_horas

        if mensaje == "1":

            # Crear nueva cita PRIMERO — si falla, la vieja queda intacta
            ok, msg = crear_cita(
                nombre      = nombre_cliente or "Cliente",
                telefono    = telefono_limpio,
                barbero_id  = estado_data["barbero_id"],
                fecha       = estado_data["fecha"],
                hora        = estado_data["hora"],
                servicio    = estado_data.get("servicio"),
                skip_client_check=True,
            )

            if not ok:
                set_state(telefono, {"estado": "inicio"})
                return f"❌ No se pudo reagendar: {msg}\n\nTu cita anterior sigue activa. Escribe *hola* para volver al menú."

            # Cancelar cita vieja solo si la nueva fue creada exitosamente
            cancelar_cita(
                telefono_limpio,
                estado_data["fecha_vieja"],
                estado_data["hora_vieja"],
            )

            set_state(telefono, {"estado": "inicio"})

            return f"""
✅ *Cita reagendada*

💈 {estado_data["barbero_nombre"]}
💇 {estado_data.get("servicio") or "Corte"}
📅 {estado_data["fecha"]}
⏰ {estado_data["hora"]}

¡Te esperamos! Escribe *hola* para volver al menú.
"""

        # re-mostrar resumen reagenda
        _hora_r = estado_data.get("hora", "")
        return (
            f"🔄 *Confirmar reagenda*\n\n"
            f"💈 {estado_data.get('barbero_nombre', '')}\n"
            f"📅 {estado_data.get('fecha', '')}  ⏰ {_hora_r}\n\n"
            f"Respondé *1* para confirmar o *2* para cambiar la hora."
        )

    # ------------------------------------------------
    # AYUDA
    # ------------------------------------------------

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

    # ------------------------------------------------
    # FALLBACK — re-prompt según el estado activo
    # ------------------------------------------------

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
            txt = f"Elegí el número del horario 👇\n\n📅 *{_fb}*\n\n"
            for _i, _h in enumerate(_hs):
                txt += f"{_i+1}️⃣ {_h['hora']}\n"
            return txt
        return "Elegí el número del horario."

    if estado == "esperando_confirmacion":
        _hora_f = estado_data.get("hora", "")
        return (
            f"💈 {estado_data.get('barbero_nombre', '')}\n"
            f"📅 {estado_data.get('fecha', '')}  ⏰ {_hora_f}\n\n"
            f"Respondé *1* para confirmar o *2* para cambiar horario."
        )

    if estado == "confirmando_cancelacion":
        return (
            f"❗ *¿Cancelar tu cita?*\n\n"
            f"📅 {estado_data.get('fecha', '')}  "
            f"⏰ {estado_data.get('hora', '')}\n\n"
            f"1️⃣ Sí, cancelar\n2️⃣ No, mantener cita"
        )

    if estado == "reagendando_fecha":
        return "¿Para qué nueva fecha querés la cita?\n\nEjemplos: *mañana*, *lunes*, *2026-04-10*"

    if estado == "reagendando_hora":
        _hs_r = estado_data.get("horarios", [])
        if _hs_r:
            _fe_r = estado_data.get("fecha", "")
            _fb_r = formatear_fecha(_fe_r) if "-" in str(_fe_r) else _fe_r
            txt = f"Elegí el número del horario 👇\n\n📅 *{_fb_r}*\n\n"
            for _i, _h in enumerate(_hs_r):
                txt += f"{_i+1}️⃣ {_h['hora']}\n"
            return txt

    if estado == "reagendando_confirmar":
        _hora_rc = estado_data.get("hora", "")
        return (
            f"🔄 *Confirmar reagenda*\n\n"
            f"💈 {estado_data.get('barbero_nombre', '')}\n"
            f"📅 {estado_data.get('fecha', '')}  ⏰ {_hora_rc}\n\n"
            f"Respondé *1* para confirmar o *2* para cambiar la hora."
        )

    if estado == "espera_confirmar":
        _fecha_ec = formatear_fecha(estado_data.get("fecha", "")) if estado_data.get("fecha") else ""
        return (
            f"😕 No hay turnos libres para *{_fecha_ec}*.\n\n"
            f"1️⃣ Sí, apuntarme a lista de espera\n"
            f"2️⃣ No, elegir otra fecha"
        )

    return menu_principal(nombre_cliente)