import json
import re
from app.extensions import db


def precio_de_servicio(precios, servicio):
    """
    Precio de un servicio a partir del dict {nombre: precio}.
    Entiende el sufijo de citas grupales "X (persona N)" que generan el bot
    y la página de reservas — sin esto, los turnos extra del grupo suman $0.
    """
    if not servicio:
        return 0
    if servicio in precios:
        return precios[servicio]
    base = re.sub(r"\s*\(persona \d+\)$", "", servicio)
    return precios.get(base, 0)


# ──────────────────────────────────────────────────────────────────────────────
# Valores por defecto (se usan cuando la barbería no tiene config propia)
# ──────────────────────────────────────────────────────────────────────────────

DEFAULT_HORARIOS = {
    0: [("10:00", "12:00"), ("16:00", "21:30")],  # Lunes
    1: [("10:00", "12:00"), ("16:00", "21:30")],  # Martes
    2: [("10:00", "12:00"), ("16:00", "21:30")],  # Miércoles
    3: [("10:00", "13:00"), ("14:00", "21:30")],  # Jueves
    4: [("09:00", "13:00"), ("14:00", "17:00")],  # Viernes
    5: [("09:00", "13:00"), ("14:00", "21:30")],  # Sábado
    # 6 = Domingo: cerrado (sin entrada)
}

DEFAULT_SERVICIOS = [
    {"id": 1, "nombre": "Corte niños",                       "precio": 15000},
    {"id": 2, "nombre": "Corte normal",                      "precio": 20000},
    {"id": 3, "nombre": "Corte + barba + tinte",             "precio": 25000},
    {"id": 4, "nombre": "Corte + barba + tinte + alisadora", "precio": 30000},
    {"id": 5, "nombre": "Pigmentación cejas",                "precio": 10000},
]


class Barberia(db.Model):

    __tablename__ = "barberias"

    id = db.Column(db.Integer, primary_key=True)

    nombre = db.Column(db.String(100), nullable=False)

    # Identificador único para URL del webhook: /bot/<slug>
    slug = db.Column(db.String(50), unique=True)

    telefono  = db.Column(db.String(20))
    direccion = db.Column(db.String(200))
    whatsapp_number = db.Column(db.String(20))

    # Acceso al panel
    panel_key = db.Column(db.String(100))

    # Credenciales Evolution API
    evolution_api_url  = db.Column(db.String(200))
    evolution_api_key  = db.Column(db.String(200))
    evolution_instance = db.Column(db.String(100))

    # Número del barbero principal (recibe notificaciones de nuevas citas)
    whatsapp_barbero = db.Column(db.String(20))

    # Configuración operativa (JSON)
    # horarios_json: {"0": [["10:00","12:00"],["16:00","21:30"]], "5": [...], ...}
    horarios_json  = db.Column(db.Text, nullable=True)

    # servicios_json: [{"id":1,"nombre":"Corte niños","precio":15000}, ...]
    servicios_json = db.Column(db.Text, nullable=True)

    # dias_bloqueados_json: ["2024-12-25", "2024-12-31", ...]
    # Fechas en las que la barbería está cerrada (vacaciones, festivos propios, etc.)
    dias_bloqueados_json = db.Column(db.Text, nullable=True)

    # Si False, el webhook del bot no responde mensajes (el barbero gestiona todo desde el panel)
    bot_activo = db.Column(db.Boolean, default=True, nullable=False, server_default='true')

    # ── Helpers ───────────────────────────────────────────────────────────────

    def get_horarios(self):
        """
        Devuelve dict {int_dia: [(str_inicio, str_fin), ...]} con los horarios
        de la barbería. Si no tiene config propia, usa DEFAULT_HORARIOS.
        """
        if not self.horarios_json:
            return DEFAULT_HORARIOS
        try:
            raw = json.loads(self.horarios_json)
            # Las claves JSON son strings; convertir a int
            return {int(k): [tuple(b) for b in v] for k, v in raw.items()}
        except Exception:
            return DEFAULT_HORARIOS

    def get_servicios(self):
        """
        Devuelve lista de dicts {id, nombre, precio}.
        Si no hay config propia, usa DEFAULT_SERVICIOS.
        """
        if not self.servicios_json:
            return DEFAULT_SERVICIOS
        try:
            return json.loads(self.servicios_json)
        except Exception:
            return DEFAULT_SERVICIOS

    def get_precios(self):
        """
        Devuelve dict {nombre_servicio: precio} para cálculo de ingresos en el panel.
        """
        return {s["nombre"]: s["precio"] for s in self.get_servicios()}

    def set_horarios(self, horarios_dict):
        """horarios_dict: {int: [(str,str)]}"""
        self.horarios_json = json.dumps({str(k): list(v) for k, v in horarios_dict.items()})

    def set_servicios(self, servicios_list):
        """servicios_list: [{"id", "nombre", "precio"}]"""
        self.servicios_json = json.dumps(servicios_list)

    def get_dias_bloqueados(self):
        """Devuelve set de strings 'YYYY-MM-DD'."""
        if not self.dias_bloqueados_json:
            return set()
        try:
            return set(json.loads(self.dias_bloqueados_json))
        except Exception:
            return set()

    def bloquear_dia(self, fecha_str):
        """Agrega una fecha al bloqueo. fecha_str: 'YYYY-MM-DD'."""
        dias = self.get_dias_bloqueados()
        dias.add(fecha_str)
        self.dias_bloqueados_json = json.dumps(sorted(dias))

    def desbloquear_dia(self, fecha_str):
        """Elimina una fecha del bloqueo."""
        dias = self.get_dias_bloqueados()
        dias.discard(fecha_str)
        self.dias_bloqueados_json = json.dumps(sorted(dias)) if dias else None

    def __repr__(self):
        return f"<Barberia {self.id} {self.nombre} slug={self.slug}>"
