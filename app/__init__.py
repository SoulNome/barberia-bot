from flask import Flask
from config import Config
from app.extensions import db


def create_app():

    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)

    from app.routes.agenda_routes import agenda_bp
    from app.routes.disponibilidad_routes import disponibilidad_bp
    from app.routes.barberos_routes import barberos_bp
    from app.routes.bot_routes import bot_bp
    from app.services.scheduler_service import iniciar_scheduler
    from app.routes.panel_routes import panel_bp
    

    app.register_blueprint(agenda_bp, url_prefix="/agenda")
    app.register_blueprint(disponibilidad_bp, url_prefix="/agenda")
    app.register_blueprint(barberos_bp, url_prefix="/barberos")
    app.register_blueprint(bot_bp)
    app.register_blueprint(panel_bp)
    iniciar_scheduler(app)

    

    return app