"""
Panel super-admin — gestión de barberías.
Acceso: /admin?key=<ADMIN_KEY>
Protegido con la variable de entorno ADMIN_KEY (independiente del PANEL_KEY).
"""
import os
import json
from flask import Blueprint, request, jsonify, render_template
from app.extensions import db
from app.models.barberia import Barberia, DEFAULT_HORARIOS, DEFAULT_SERVICIOS
from app.models.cliente import Cliente
from app.models.cita import Cita
from app.models.barbero import Barbero
from datetime import datetime, timedelta, date

admin_bp = Blueprint("admin", __name__)


def _check_key(key):
    admin_key = os.getenv("ADMIN_KEY")
    return admin_key and key == admin_key


def _colombia_today():
    return (datetime.utcnow() - timedelta(hours=5)).date()


def _stats_barberia(barberia_id):
    hoy = _colombia_today()
    inicio_semana = hoy - timedelta(days=hoy.weekday())
    return {
        "clientes":      Cliente.query.filter_by(barberia_id=barberia_id).count(),
        "barberos":      Barbero.query.filter_by(barberia_id=barberia_id).count(),
        "citas_hoy":     Cita.query.filter_by(barberia_id=barberia_id, fecha=hoy).filter(Cita.estado != "cancelada").count(),
        "citas_semana":  Cita.query.filter(
                             Cita.barberia_id == barberia_id,
                             Cita.fecha >= inicio_semana,
                             Cita.fecha <= hoy,
                             Cita.estado != "cancelada"
                         ).count(),
    }


# ──────────────────────────────────────────────────────────────────────────────
# HTML
# ──────────────────────────────────────────────────────────────────────────────

@admin_bp.route("/admin")
def admin_panel():
    key = request.args.get("key")
    if not _check_key(key):
        return "No autorizado", 401

    barberias = Barberia.query.order_by(Barberia.id).all()
    datos = []
    for b in barberias:
        try:
            stats = _stats_barberia(b.id)
        except Exception as e:
            print(f"[ADMIN] Error al cargar stats de barbería {b.id}: {e}")
            stats = {"clientes": 0, "barberos": 0, "citas_hoy": 0, "citas_semana": 0}
        datos.append({
            "barberia": b,
            "stats":    stats,
        })

    return render_template(
        "admin.html",
        key=key,
        datos=datos,
        default_horarios=json.dumps(
            {str(k): list(v) for k, v in DEFAULT_HORARIOS.items()}, indent=2
        ),
        default_servicios=json.dumps(DEFAULT_SERVICIOS, indent=2),
    )


# ──────────────────────────────────────────────────────────────────────────────
# API — Crear barbería
# ──────────────────────────────────────────────────────────────────────────────

@admin_bp.route("/admin/crear-barberia", methods=["POST"])
def crear_barberia():
    key = request.args.get("key") or (request.get_json(silent=True) or {}).get("key")
    if not _check_key(key):
        return jsonify({"success": False, "mensaje": "No autorizado"}), 401

    data = request.get_json(silent=True) or {}

    nombre    = (data.get("nombre") or "").strip()
    slug      = (data.get("slug") or "").strip().lower().replace(" ", "-")
    panel_key = (data.get("panel_key") or "").strip()

    if not nombre or not slug or not panel_key:
        return jsonify({"success": False, "mensaje": "nombre, slug y panel_key son obligatorios"})

    if Barberia.query.filter_by(slug=slug).first():
        return jsonify({"success": False, "mensaje": f"El slug '{slug}' ya está en uso"})

    if Barberia.query.filter_by(panel_key=panel_key).first():
        return jsonify({"success": False, "mensaje": "Ese panel_key ya está en uso"})

    # Validar y guardar horarios/servicios si vienen
    horarios_json  = None
    servicios_json = None

    if data.get("horarios"):
        try:
            horarios_json = json.dumps(data["horarios"])
        except Exception:
            return jsonify({"success": False, "mensaje": "horarios inválidos (debe ser JSON)"})

    if data.get("servicios"):
        try:
            servicios_json = json.dumps(data["servicios"])
        except Exception:
            return jsonify({"success": False, "mensaje": "servicios inválidos (debe ser JSON)"})

    try:
        b = Barberia(
            nombre             = nombre,
            slug               = slug,
            panel_key          = panel_key,
            telefono           = (data.get("telefono") or "").strip() or None,
            direccion          = (data.get("direccion") or "").strip() or None,
            evolution_api_url  = (data.get("evolution_api_url") or "").strip() or None,
            evolution_api_key  = (data.get("evolution_api_key") or "").strip() or None,
            evolution_instance = (data.get("evolution_instance") or "").strip() or None,
            whatsapp_barbero   = (data.get("whatsapp_barbero") or "").strip() or None,
            horarios_json      = horarios_json,
            servicios_json     = servicios_json,
        )
        db.session.add(b)
        db.session.commit()
        return jsonify({
            "success": True,
            "mensaje": f"Barbería '{nombre}' creada correctamente",
            "id":      b.id,
            "slug":    b.slug,
            "webhook": f"/bot/{b.slug}",
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "mensaje": str(e)})


# ──────────────────────────────────────────────────────────────────────────────
# API — Editar barbería
# ──────────────────────────────────────────────────────────────────────────────

@admin_bp.route("/admin/editar-barberia", methods=["POST"])
def editar_barberia():
    key = request.args.get("key") or (request.get_json(silent=True) or {}).get("key")
    if not _check_key(key):
        return jsonify({"success": False, "mensaje": "No autorizado"}), 401

    data        = request.get_json(silent=True) or {}
    barberia_id = data.get("id")
    if not barberia_id:
        return jsonify({"success": False, "mensaje": "id requerido"})

    b = Barberia.query.get(barberia_id)
    if not b:
        return jsonify({"success": False, "mensaje": f"Barbería {barberia_id} no encontrada"})

    campos_simples = [
        "nombre", "telefono", "direccion",
        "panel_key", "evolution_api_url", "evolution_api_key",
        "evolution_instance", "whatsapp_barbero",
    ]
    for campo in campos_simples:
        if campo in data:
            setattr(b, campo, (data[campo] or "").strip() or None)

    if "slug" in data:
        nuevo_slug = data["slug"].strip().lower().replace(" ", "-")
        existente  = Barberia.query.filter_by(slug=nuevo_slug).first()
        if existente and existente.id != b.id:
            return jsonify({"success": False, "mensaje": f"El slug '{nuevo_slug}' ya está en uso"})
        b.slug = nuevo_slug

    if "horarios" in data:
        try:
            b.horarios_json = json.dumps(data["horarios"]) if data["horarios"] else None
        except Exception:
            return jsonify({"success": False, "mensaje": "horarios inválidos"})

    if "servicios" in data:
        try:
            b.servicios_json = json.dumps(data["servicios"]) if data["servicios"] else None
        except Exception:
            return jsonify({"success": False, "mensaje": "servicios inválidos"})

    try:
        db.session.commit()
        return jsonify({"success": True, "mensaje": f"Barbería '{b.nombre}' actualizada"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "mensaje": str(e)})


# ──────────────────────────────────────────────────────────────────────────────
# API — Detalle de barbería (JSON)
# ──────────────────────────────────────────────────────────────────────────────

@admin_bp.route("/admin/barberia/<int:barberia_id>")
def detalle_barberia(barberia_id):
    key = request.args.get("key")
    if not _check_key(key):
        return jsonify({"success": False, "mensaje": "No autorizado"}), 401

    b = Barberia.query.get(barberia_id)
    if not b:
        return jsonify({"success": False, "mensaje": "No encontrada"}), 404

    return jsonify({
        "success": True,
        "barberia": {
            "id":                b.id,
            "nombre":            b.nombre,
            "slug":              b.slug,
            "panel_key":         b.panel_key,
            "telefono":          b.telefono,
            "direccion":         b.direccion,
            "evolution_api_url": b.evolution_api_url,
            "evolution_api_key": b.evolution_api_key,
            "evolution_instance":b.evolution_instance,
            "whatsapp_barbero":  b.whatsapp_barbero,
            "horarios":          b.get_horarios(),
            "servicios":         b.get_servicios(),
        },
        "stats": _stats_barberia(b.id),
    })


# ──────────────────────────────────────────────────────────────────────────────
# API — Lista de barberías (JSON)
# ──────────────────────────────────────────────────────────────────────────────

@admin_bp.route("/admin/barberias")
def listar_barberias():
    key = request.args.get("key")
    if not _check_key(key):
        return jsonify({"success": False, "mensaje": "No autorizado"}), 401

    barberias = Barberia.query.order_by(Barberia.id).all()
    return jsonify({
        "success": True,
        "barberias": [
            {
                "id":      b.id,
                "nombre":  b.nombre,
                "slug":    b.slug,
                "webhook": f"/bot/{b.slug}" if b.slug else None,
                "stats":   _stats_barberia(b.id),
            }
            for b in barberias
        ]
    })
