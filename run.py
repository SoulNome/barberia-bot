from app import create_app, db
from app.models import Barberia, UserState

app = create_app()

with app.app_context():
    # create_app() ya ejecutó db.create_all(); repetirlo aquí solo añadía una
    # ronda de introspección de tablas en cada arranque del worker.

    # Migración: agregar columnas nuevas si no existen
    from sqlalchemy import text
    try:
        db.session.execute(text(
            "ALTER TABLE clientes ADD COLUMN IF NOT EXISTS fijo BOOLEAN DEFAULT FALSE"
        ))
        db.session.execute(text(
            "ALTER TABLE clientes ADD COLUMN IF NOT EXISTS horario_fijo VARCHAR(100)"
        ))
        db.session.commit()
    except Exception:
        db.session.rollback()

    # Migración: índice único para evitar turno doble (barbero+fecha+hora)
    try:
        db.session.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_cita_barbero_fecha_hora "
            "ON citas(barbero_id, fecha, hora)"
        ))
        db.session.commit()
    except Exception:
        db.session.rollback()

if __name__ == "__main__":
    app.run(debug=True)