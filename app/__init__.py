import os
from flask import Flask
from config import Config
from app.extensions import db

def _run_startup_migrations(app):
    """
    Añade columnas multi-tenant a las tablas existentes si no están.
    Crea la barbería por defecto desde env vars si no existe ninguna.
    Asigna barberia_id al primer registro a todos los datos sin asignar.
    Idempotente: se puede ejecutar múltiples veces sin problema.
    """
    from sqlalchemy import text

    with app.app_context():
        with db.engine.connect() as conn:

            def col_exists(table, col):
                r = conn.execute(text(
                    "SELECT COUNT(*) FROM information_schema.columns "
                    "WHERE table_name = :t AND column_name = :c"
                ), {"t": table, "c": col})
                return r.scalar() > 0

            def index_exists(idx):
                r = conn.execute(text(
                    "SELECT COUNT(*) FROM pg_indexes WHERE indexname = :i"
                ), {"i": idx})
                return r.scalar() > 0

            changes = []

            # ── Columnas en barberias ─────────────────────────────────────────
            new_barberia_cols = [
                ("slug",              "VARCHAR(50)"),
                ("panel_key",         "VARCHAR(100)"),
                ("evolution_api_url", "VARCHAR(200)"),
                ("evolution_api_key", "VARCHAR(200)"),
                ("evolution_instance","VARCHAR(100)"),
                ("whatsapp_barbero",  "VARCHAR(20)"),
                ("horarios_json",     "TEXT"),
                ("servicios_json",    "TEXT"),
                ("dias_bloqueados_json", "TEXT"),
            ]
            for col, typ in new_barberia_cols:
                if not col_exists("barberias", col):
                    conn.execute(text(f"ALTER TABLE barberias ADD COLUMN {col} {typ}"))
                    changes.append(f"barberias.{col}")

            # ── barberia_id en tablas de datos ────────────────────────────────
            for table in ("clientes", "citas", "user_states", "lista_espera", "barberos"):
                if not col_exists(table, "barberia_id"):
                    conn.execute(text(
                        f"ALTER TABLE {table} ADD COLUMN barberia_id INTEGER REFERENCES barberias(id)"
                    ))
                    changes.append(f"{table}.barberia_id")

            conn.commit()
            if changes:
                print(f"[MIGRATION] Columnas añadidas: {changes}")

            # ── Barbería por defecto ──────────────────────────────────────────
            count = conn.execute(text("SELECT COUNT(*) FROM barberias")).scalar()
            if count == 0:
                conn.execute(text("""
                    INSERT INTO barberias
                        (nombre, slug, panel_key, evolution_api_url, evolution_api_key,
                         evolution_instance, whatsapp_barbero)
                    VALUES
                        (:nombre, :slug, :panel_key, :evo_url, :evo_key, :evo_inst, :wa_barbero)
                """), {
                    "nombre":     os.getenv("BARBERIA_NOMBRE", "BarberIA"),
                    "slug":       os.getenv("BARBERIA_SLUG",   "default"),
                    "panel_key":  os.getenv("PANEL_KEY",       ""),
                    "evo_url":    os.getenv("EVOLUTION_API_URL",  ""),
                    "evo_key":    os.getenv("EVOLUTION_API_KEY",  ""),
                    "evo_inst":   os.getenv("EVOLUTION_INSTANCE", ""),
                    "wa_barbero": os.getenv("HERMES_PHONE",    ""),
                })
                conn.commit()
                print("[MIGRATION] Barbería por defecto creada desde env vars")

            # ── Asignar barberia_id a registros sin asignar ───────────────────
            first_id = conn.execute(
                text("SELECT id FROM barberias ORDER BY id LIMIT 1")
            ).scalar()
            if first_id:
                for table in ("clientes", "citas", "user_states", "lista_espera", "barberos"):
                    conn.execute(text(
                        f"UPDATE {table} SET barberia_id = :bid WHERE barberia_id IS NULL"
                    ), {"bid": first_id})
                conn.commit()

            # ── Índices únicos compuestos (telefono, barberia_id) ─────────────
            for table, idx in [
                ("clientes",    "uq_clientes_tel_barberia"),
                ("user_states", "uq_user_states_tel_barberia"),
            ]:
                if not index_exists(idx):
                    for old in (f"{table}_telefono_key", f"ix_{table}_telefono"):
                        try:
                            conn.execute(text(
                                f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {old}"
                            ))
                        except Exception:
                            pass
                        try:
                            conn.execute(text(f"DROP INDEX IF EXISTS {old}"))
                        except Exception:
                            pass
                    try:
                        conn.execute(text(
                            f"CREATE UNIQUE INDEX {idx} ON {table} (telefono, barberia_id) "
                            f"WHERE barberia_id IS NOT NULL"
                        ))
                        print(f"[MIGRATION] Índice {idx} creado")
                    except Exception as e:
                        print(f"[MIGRATION] Aviso índice {idx}: {e}")
                    conn.commit()

            # ── Columna bot_activo en barberias ──────────────────────────────
            if not col_exists("barberias", "bot_activo"):
                conn.execute(text(
                    "ALTER TABLE barberias ADD COLUMN bot_activo BOOLEAN NOT NULL DEFAULT TRUE"
                ))
                conn.commit()
                print("[MIGRATION] barberias.bot_activo añadida")

            # ── Horarios Bulls: Lun-Jue 09-12 y 14-18 (Vie y Sáb libres) ────
            try:
                bulls_hor = ('{"0":[["09:00","12:00"],["14:00","18:00"]],'
                             '"1":[["09:00","12:00"],["14:00","18:00"]],'
                             '"2":[["09:00","12:00"],["14:00","18:00"]],'
                             '"3":[["09:00","12:00"],["14:00","18:00"]]}')
                result = conn.execute(text("""
                    UPDATE barberias SET horarios_json = :h
                    WHERE (slug ILIKE '%bulls%' OR nombre ILIKE '%bulls%')
                """), {"h": bulls_hor})
                if result.rowcount > 0:
                    conn.commit()
                    print("[MIGRATION] Horarios Bulls: Lun-Jue 09:00-12:00 / 14:00-18:00")
            except Exception as e:
                print(f"[MIGRATION] Aviso horarios Bulls: {e}")

            # ── Bot Bulls desactivado (barbero gestiona desde el panel) ───────
            try:
                result = conn.execute(text("""
                    UPDATE barberias SET bot_activo = FALSE
                    WHERE (slug ILIKE '%bulls%' OR nombre ILIKE '%bulls%')
                    AND bot_activo = TRUE
                """))
                if result.rowcount > 0:
                    conn.commit()
                    print("[MIGRATION] Bot Bulls desactivado")
            except Exception as e:
                print(f"[MIGRATION] Aviso bot Bulls: {e}")


def create_app():

    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)

    with app.app_context():
        db.create_all()

    # Migraciones automáticas para multi-tenancy
    _run_startup_migrations(app)

    from app.routes.agenda_routes       import agenda_bp
    from app.routes.disponibilidad_routes import disponibilidad_bp
    from app.routes.barberos_routes     import barberos_bp
    from app.routes.bot_routes          import bot_bp
    from app.services.scheduler_service import iniciar_scheduler
    from app.routes.panel_routes        import panel_bp
    from app.routes.admin_routes        import admin_bp

    app.register_blueprint(agenda_bp,          url_prefix="/agenda")
    app.register_blueprint(disponibilidad_bp,  url_prefix="/agenda")
    app.register_blueprint(barberos_bp,        url_prefix="/barberos")
    app.register_blueprint(bot_bp)
    app.register_blueprint(panel_bp)
    app.register_blueprint(admin_bp)
    iniciar_scheduler(app)

    return app
