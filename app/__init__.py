from flask import Flask
from config import Config
from app.extensions import db

def create_app():

    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)

    from app.routes.agenda_routes import agenda_bp
    from app.routes.disponibilidad_routes import disponibilidad_bp

    app.register_blueprint(agenda_bp)
    app.register_blueprint(disponibilidad_bp)

    return app