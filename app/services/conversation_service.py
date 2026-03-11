from app.services.nlp_service import interpretar_mensaje

user_states = {}

def manejar_mensaje(telefono, mensaje, barberos):

    estado = user_states.get(telefono, "inicio")

    nlp = interpretar_mensaje(mensaje, barberos)

    accion = nlp["accion"]
    fecha = nlp["fecha"]
    hora = nlp["hora"]
    barbero = nlp["barbero"]

    # SALUDO
    if mensaje in ["hola", "menu"]:

        user_states[telefono] = "inicio"

        return """
Hola 👋 soy BarberIA 💈

Puedes decir:

• quiero una cita
• ver barberos
• horarios mañana
• cancelar cita
"""

    # VER BARBEROS
    if accion == "barberos":

        texto = "💈 Nuestros barberos:\n\n"

        for b in barberos:
            texto += f"{b['id']}️⃣ {b['nombre']}\n"

        return texto

    # INICIAR CITA
    if accion == "agendar":

        texto = "Perfecto 💈 Vamos a agendar tu cita.\n\n"

        texto += "¿Con qué barbero?\n"

        for b in barberos:
            texto += f"{b['id']}️⃣ {b['nombre']}\n"

        user_states[telefono] = "esperando_barbero"

        return texto

    return "No entendí tu mensaje 🤔"