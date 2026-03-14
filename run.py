from app import create_app, db
from app.models import Barberia, UserState

app = create_app()

with app.app_context():
    db.create_all()

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

if __name__ == "__main__":
    app.run(debug=True)