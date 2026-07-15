import os
import random

from apscheduler.schedulers.background import BackgroundScheduler
from app.extensions import db
from app.models import Cita, Cliente
from datetime import datetime, timedelta, date

# Máximo de reactivaciones por barbería por corrida — los mensajes iniciados
# por el negocio a clientes inactivos son los que más bloqueos generan.
_REACTIVACION_MAX = int(os.getenv("REACTIVACION_MAX", "15"))


def enviar_recordatorios_fijos(app):
    with app.app_context():
        from app.models.barberia import Barberia
        from app.services.recordatorio_service import enviar_recordatorio_fijo, pausa_anti_ban

        for barberia in Barberia.query.all():
            clientes = Cliente.query.filter_by(fijo=True, barberia_id=barberia.id).all()
            enviados = 0
            for c in clientes:
                if c.telefono and c.horario_fijo:
                    if enviados:
                        pausa_anti_ban()
                    ok = enviar_recordatorio_fijo(c.telefono, c.nombre, c.horario_fijo, barberia)
                    if ok:
                        enviados += 1
            if clientes:
                print(f"📲 [{barberia.nombre}] Recordatorios fijos enviados: {enviados}/{len(clientes)}")


def crear_citas_fijos(app):
    """
    Crea citas reales en la BD para clientes fijos de cada barbería.
    Se ejecuta diariamente. Itera por barbería para respetar el aislamiento multi-tenant.
    """
    with app.app_context():
        from app.models.barbero import Barbero
        from app.models.barberia import Barberia
        from app.services.disponibilidad_service import _parsear_horario_fijo, FESTIVOS

        hoy = (datetime.utcnow() - timedelta(hours=5)).date()

        for barberia in Barberia.query.all():

            barbero_default = Barbero.query.filter_by(
                barberia_id=barberia.id
            ).order_by(Barbero.id).first()

            if not barbero_default:
                continue

            clientes_fijos = Cliente.query.filter_by(fijo=True, barberia_id=barberia.id).all()
            creadas = 0

            for cf in clientes_fijos:
                if not cf.horario_fijo or not cf.telefono:
                    continue

                for dias_ahead in range(7):
                    fecha_cita = hoy + timedelta(days=dias_ahead)
                    fecha_str  = fecha_cita.strftime("%Y-%m-%d")

                    if fecha_cita.weekday() == 6 or fecha_str in FESTIVOS:
                        continue

                    dia_semana = fecha_cita.weekday()
                    hora_str   = _parsear_horario_fijo(cf.horario_fijo, dia_semana)
                    if not hora_str:
                        continue

                    hora = datetime.strptime(hora_str, "%H:%M").time()

                    ya_existe = Cita.query.filter_by(
                        cliente_id=cf.id,
                        fecha=fecha_cita,
                        hora=hora
                    ).first()

                    if ya_existe:
                        if ya_existe.estado == "cancelada":
                            hoy_co = (datetime.utcnow() - timedelta(hours=5)).date()
                            if fecha_cita >= hoy_co:
                                continue
                            else:
                                db.session.delete(ya_existe)
                                db.session.flush()
                        else:
                            continue

                    # No crear si el cliente ya reagendó ese día
                    reagendo = Cita.query.filter(
                        Cita.cliente_id == cf.id,
                        Cita.fecha == fecha_cita,
                        Cita.hora != hora,
                        Cita.estado != "cancelada"
                    ).first()
                    if reagendo:
                        continue

                    # No crear si el slot fue tomado por otro
                    conflicto = Cita.query.filter(
                        Cita.barbero_id == barbero_default.id,
                        Cita.fecha == fecha_cita,
                        Cita.hora == hora,
                        Cita.estado != "cancelada"
                    ).first()
                    if conflicto:
                        print(f"⚠ [{barberia.nombre}] Slot fijo {cf.nombre} {fecha_str} {hora_str} ocupado")
                        continue

                    nueva = Cita(
                        cliente_id  = cf.id,
                        barbero_id  = barbero_default.id,
                        fecha       = fecha_cita,
                        hora        = hora,
                        servicio    = "📌 Turno fijo",
                        barberia_id = barberia.id,
                    )
                    db.session.add(nueva)
                    creadas += 1

            try:
                db.session.commit()
                if creadas:
                    print(f"📌 [{barberia.nombre}] Citas fijas creadas: {creadas}")
            except Exception as e:
                db.session.rollback()
                print(f"⚠ [{barberia.nombre}] Error creando citas fijas: {e}")


def enviar_recordatorios_regulares(app):
    """
    Envía recordatorio el día anterior a todos los clientes con cita
    (no fijos — esos ya tienen su propio recordatorio semanal).
    Se ejecuta cada día a las 17:00 Colombia (22:00 UTC).
    """
    with app.app_context():
        from app.models.barberia import Barberia
        from app.services.recordatorio_service import enviar_recordatorio, pausa_anti_ban

        manana = (datetime.utcnow() - timedelta(hours=5)).date() + timedelta(days=1)

        for barberia in Barberia.query.all():
            citas = (
                Cita.query
                .filter(
                    Cita.barberia_id == barberia.id,
                    Cita.fecha == manana,
                    Cita.estado != "cancelada",
                )
                .all()
            )

            enviados = 0
            for cita in citas:
                cliente = Cliente.query.get(cita.cliente_id)
                if not cliente or not cliente.telefono:
                    continue
                # Los fijos ya reciben recordatorio semanal; no duplicar
                if cliente.fijo:
                    continue
                fecha_str = manana.strftime("%d/%m/%Y")
                hora_str  = cita.hora.strftime("%H:%M") if cita.hora else "—"
                if enviados:
                    pausa_anti_ban()
                ok = enviar_recordatorio(
                    cliente.telefono, cliente.nombre,
                    fecha_str, hora_str,
                    barberia,
                )
                if ok:
                    enviados += 1

            if citas:
                print(f"📲 [{barberia.nombre}] Recordatorios mañana: {enviados}/{len(citas)}")


def enviar_reporte_semanal(app):
    """
    Envía al barbero un resumen de la semana anterior por WhatsApp.
    Se ejecuta cada lunes a las 09:00 Colombia (14:00 UTC).
    """
    with app.app_context():
        from app.models.barberia import Barberia
        from app.services.recordatorio_service import _enviar_whatsapp

        hoy      = (datetime.utcnow() - timedelta(hours=5)).date()
        lunes    = hoy - timedelta(days=hoy.weekday())      # lunes de esta semana
        semana_ini = lunes - timedelta(days=7)              # lunes semana pasada
        semana_fin = lunes - timedelta(days=1)              # domingo semana pasada

        DIAS_ES   = ["Lun","Mar","Mié","Jue","Vie","Sáb","Dom"]
        MESES_ES  = ["ene","feb","mar","abr","may","jun",
                     "jul","ago","sep","oct","nov","dic"]

        for barberia in Barberia.query.all():
            if not barberia.whatsapp_barbero:
                continue

            try:
                precios = barberia.get_precios()

                citas = Cita.query.filter(
                    Cita.barberia_id == barberia.id,
                    Cita.fecha >= semana_ini,
                    Cita.fecha <= semana_fin,
                    Cita.estado != "cancelada",
                ).all()

                canceladas = Cita.query.filter(
                    Cita.barberia_id == barberia.id,
                    Cita.fecha >= semana_ini,
                    Cita.fecha <= semana_fin,
                    Cita.estado == "cancelada",
                ).count()

                total_citas    = len(citas)
                ingresos       = sum(precios.get(c.servicio, 0) for c in citas)
                ticket_prom    = int(ingresos / total_citas) if total_citas else 0

                # Clientes nuevos esa semana
                clientes_nuevos = Cliente.query.filter(
                    Cliente.barberia_id == barberia.id,
                    Cliente.creado_en >= datetime.combine(semana_ini, datetime.min.time()),
                    Cliente.creado_en <= datetime.combine(semana_fin, datetime.max.time()),
                ).count()

                # Hora pico
                conteo_horas = {}
                for c in citas:
                    h = c.hora.strftime("%H:%M") if c.hora else "?"
                    conteo_horas[h] = conteo_horas.get(h, 0) + 1
                hora_pico = max(conteo_horas, key=conteo_horas.get) if conteo_horas else None

                # Día más ocupado
                conteo_dias = {}
                for c in citas:
                    d = DIAS_ES[c.fecha.weekday()]
                    conteo_dias[d] = conteo_dias.get(d, 0) + 1
                dia_pico = max(conteo_dias, key=conteo_dias.get) if conteo_dias else None

                # Servicio más pedido
                conteo_svc = {}
                for c in citas:
                    if c.servicio and not c.servicio.startswith("📌"):
                        conteo_svc[c.servicio] = conteo_svc.get(c.servicio, 0) + 1
                svc_top = max(conteo_svc, key=conteo_svc.get) if conteo_svc else None

                # Formatear rango de fechas
                fecha_rango = (
                    f"{semana_ini.day} {MESES_ES[semana_ini.month-1]} — "
                    f"{semana_fin.day} {MESES_ES[semana_fin.month-1]}"
                )

                # Comparación con semana anterior
                semana2_ini = semana_ini - timedelta(days=7)
                semana2_fin = semana_ini - timedelta(days=1)
                citas_ant   = Cita.query.filter(
                    Cita.barberia_id == barberia.id,
                    Cita.fecha >= semana2_ini,
                    Cita.fecha <= semana2_fin,
                    Cita.estado != "cancelada",
                ).count()
                tendencia = ""
                if citas_ant > 0:
                    diff = total_citas - citas_ant
                    pct  = int(abs(diff / citas_ant) * 100)
                    if diff > 0:
                        tendencia = f"↑ {pct}% vs semana anterior"
                    elif diff < 0:
                        tendencia = f"↓ {pct}% vs semana anterior"
                    else:
                        tendencia = "= igual que semana anterior"

                # Construir mensaje
                ingresos_fmt = f"${ingresos:,}".replace(",", ".")
                ticket_fmt   = f"${ticket_prom:,}".replace(",", ".")

                lineas = [
                    f"📊 *Reporte semanal — {barberia.nombre}*",
                    f"_{fecha_rango}_",
                    "",
                    f"✂️ Citas realizadas: *{total_citas}*" + (f"  {tendencia}" if tendencia else ""),
                    f"💵 Ingresos: *{ingresos_fmt}*",
                    f"🎯 Ticket promedio: *{ticket_fmt}*",
                ]
                if clientes_nuevos:
                    lineas.append(f"🆕 Clientes nuevos: *{clientes_nuevos}*")
                if canceladas:
                    lineas.append(f"❌ Cancelaciones: *{canceladas}*")
                if hora_pico:
                    lineas.append(f"🕐 Hora pico: *{hora_pico}*")
                if dia_pico:
                    lineas.append(f"📆 Día más ocupado: *{dia_pico}*")
                if svc_top:
                    lineas.append(f"💈 Servicio top: *{svc_top}*")

                lineas += ["", "¡Buena semana! 💪 _BarberIA_"]

                msg = "\n".join(lineas)
                ok  = _enviar_whatsapp(barberia.whatsapp_barbero, msg, barberia)
                print(f"📊 [{barberia.nombre}] Reporte semanal {'enviado' if ok else 'falló'}")

            except Exception as e:
                print(f"⚠ [{barberia.nombre}] Error reporte semanal: {e}")


def enviar_reactivaciones(app):
    """
    Detecta clientes que no tienen cita en los últimos 30 días y no tienen
    ninguna cita futura agendada, y les manda un mensaje de reactivación.
    Se ejecuta cada miércoles a las 10:00 Colombia (15:00 UTC).
    Evita re-enviar al mismo cliente más de una vez cada 30 días guardando
    la fecha del último envío en user_states.
    """
    with app.app_context():
        from app.models.barberia import Barberia
        from app.services.recordatorio_service import _enviar_whatsapp, pausa_anti_ban

        hoy      = (datetime.utcnow() - timedelta(hours=5)).date()
        hace30   = hoy - timedelta(days=30)
        hace60   = hoy - timedelta(days=60)   # solo contactar si vino alguna vez en los últimos 60 días

        for barberia in Barberia.query.all():
            if not barberia.evolution_api_url or not barberia.evolution_instance:
                continue

            try:
                # Clientes activos (tuvieron cita entre hace 60 y hace 30 días)
                clientes_recientes = (
                    db.session.query(Cita.cliente_id)
                    .filter(
                        Cita.barberia_id == barberia.id,
                        Cita.fecha >= hace60,
                        Cita.fecha <= hace30,
                        Cita.estado != "cancelada",
                    )
                    .distinct()
                    .all()
                )
                ids_recientes = {r[0] for r in clientes_recientes}

                # Excluir los que ya tienen cita futura o vinieron en los últimos 30 días
                ids_con_cita_reciente = (
                    db.session.query(Cita.cliente_id)
                    .filter(
                        Cita.barberia_id == barberia.id,
                        Cita.fecha >= hace30,
                        Cita.estado != "cancelada",
                    )
                    .distinct()
                    .all()
                )
                ids_excluir = {r[0] for r in ids_con_cita_reciente}

                ids_dormiados = ids_recientes - ids_excluir
                if not ids_dormiados:
                    continue

                enviados = 0
                for cliente_id in ids_dormiados:
                    # Tope por corrida: los que no alcancen hoy siguen dormidos
                    # y entrarán en la corrida de la próxima semana.
                    if enviados >= _REACTIVACION_MAX:
                        break
                    cliente = Cliente.query.get(cliente_id)
                    if not cliente or not cliente.telefono:
                        continue

                    # Verificar que no le hayamos enviado reactivación hace menos de 30 días
                    from app.models.user_state import UserState
                    us = UserState.query.filter_by(
                        telefono=cliente.telefono,
                        barberia_id=barberia.id,
                    ).first()
                    if us:
                        datos = us.get_data()
                        ultimo_envio = datos.get("reactivacion_enviada")
                        if ultimo_envio:
                            try:
                                fecha_envio = date.fromisoformat(ultimo_envio)
                                if (hoy - fecha_envio).days < 30:
                                    continue
                            except Exception:
                                pass

                    # Rotar entre variantes: el mismo texto idéntico enviado a
                    # muchos números es la firma de spam que detecta WhatsApp.
                    msg = random.choice([
                        (
                            f"💈 *¡Hola {cliente.nombre}!*\n\n"
                            f"Hace un tiempo que no te vemos por aquí 👋\n\n"
                            f"¿Quieres agendar tu próxima cita? Escríbenos *hola* "
                            f"y te reservamos el turno en segundos 😊\n\n"
                            f"_BarberIA · {barberia.nombre}_"
                        ),
                        (
                            f"Hola {cliente.nombre} 👋\n\n"
                            f"¡Ya toca retocar ese corte! ✂️ Si quieres agendar, "
                            f"escríbenos *hola* y te damos el turno que mejor te sirva.\n\n"
                            f"_BarberIA · {barberia.nombre}_"
                        ),
                        (
                            f"💈 {cliente.nombre}, ¡te extrañamos en {barberia.nombre}!\n\n"
                            f"Tenemos turnos disponibles esta semana. "
                            f"Escríbenos *hola* y agendas en segundos 😊"
                        ),
                    ])

                    if enviados:
                        pausa_anti_ban(45, 90)
                    ok = _enviar_whatsapp(cliente.telefono, msg, barberia)
                    if ok:
                        enviados += 1
                        # Guardar fecha de envío en el estado del usuario
                        try:
                            from app.services.state_service import get_state, set_state
                            datos_actuales = get_state(cliente.telefono, barberia.id)
                            datos_actuales["reactivacion_enviada"] = hoy.isoformat()
                            set_state(cliente.telefono, datos_actuales, barberia.id)
                        except Exception:
                            pass

                print(f"💤 [{barberia.nombre}] Reactivaciones enviadas: {enviados}/{len(ids_dormiados)}")

            except Exception as e:
                print(f"⚠ [{barberia.nombre}] Error reactivaciones: {e}")


def enviar_encuestas(app):
    """
    Envía encuesta de satisfacción al día siguiente de cada cita completada.
    Se ejecuta diariamente a las 10:00 Colombia (15:00 UTC).
    """
    with app.app_context():
        from app.models.barberia import Barberia
        from app.models.encuesta import Encuesta
        from app.services.recordatorio_service import _enviar_whatsapp, pausa_anti_ban
        from app.services.state_service import get_state, set_state

        ayer = (datetime.utcnow() - timedelta(hours=5)).date() - timedelta(days=1)

        for barberia in Barberia.query.all():
            if not barberia.evolution_api_url or not barberia.evolution_instance:
                continue

            citas_ayer = Cita.query.filter(
                Cita.barberia_id == barberia.id,
                Cita.fecha == ayer,
                Cita.estado != "cancelada",
            ).all()

            enviados = 0
            for cita in citas_ayer:
                cliente = Cliente.query.get(cita.cliente_id)
                if not cliente or not cliente.telefono:
                    continue

                # No reenviar si ya existe encuesta para esta cita
                if Encuesta.query.filter_by(cita_id=cita.id).first():
                    continue

                msg = (
                    f"💈 *¡Gracias por visitarnos, {cliente.nombre}!*\n\n"
                    f"¿Cómo estuvo tu experiencia?\n\n"
                    f"Calificanos del *1* al *5* ⭐\n\n"
                    f"1️⃣ Muy malo\n"
                    f"2️⃣ Malo\n"
                    f"3️⃣ Regular\n"
                    f"4️⃣ Bueno\n"
                    f"5️⃣ Excelente\n\n"
                    f"_(Solo responde con el número)_"
                )

                if enviados:
                    pausa_anti_ban()
                ok = _enviar_whatsapp(cliente.telefono, msg, barberia)
                if ok:
                    enviados += 1
                    try:
                        datos = get_state(cliente.telefono, barberia.id)
                        datos["estado"]              = "esperando_encuesta"
                        datos["encuesta_cita_id"]    = cita.id
                        set_state(cliente.telefono, datos, barberia.id)
                    except Exception as e:
                        print(f"⚠ Error set_state encuesta: {e}")

            if citas_ayer:
                print(f"⭐ [{barberia.nombre}] Encuestas enviadas: {enviados}/{len(citas_ayer)}")


def iniciar_scheduler(app):
    scheduler = BackgroundScheduler()

    # NOTA anti-ban: el recordatorio de clientes fijos es SEMANAL (solo lunes).
    # Antes había además un job diario con la misma función: cada cliente fijo
    # recibía el mismo texto todos los días (y doble los lunes) — patrón de
    # spam que provoca los bloqueos de 24h de WhatsApp.

    # Crear citas fijos — cada día a las 06:00 Colombia (11:00 UTC)
    scheduler.add_job(
        crear_citas_fijos,
        "cron",
        hour=11,
        minute=0,
        args=[app]
    )

    # Recordatorio clientes fijos — cada lunes a las 08:00 Colombia (13:00 UTC)
    scheduler.add_job(
        enviar_recordatorios_fijos,
        "cron",
        day_of_week="mon",
        hour=13,
        minute=0,
        args=[app]
    )

    # Recordatorio citas regulares del día siguiente — cada día a las 17:00 Colombia (22:00 UTC)
    scheduler.add_job(
        enviar_recordatorios_regulares,
        "cron",
        hour=22,
        minute=0,
        args=[app]
    )

    # Reporte semanal al barbero — cada lunes a las 09:00 Colombia (14:00 UTC)
    scheduler.add_job(
        enviar_reporte_semanal,
        "cron",
        day_of_week="mon",
        hour=14,
        minute=0,
        args=[app]
    )

    # Reactivación clientes dormidos — cada miércoles a las 11:00 Colombia (16:00 UTC).
    # A las 16:00 y no a las 15:00 para no solaparse con las encuestas diarias:
    # dos campañas despachando a la vez duplica el volumen por minuto.
    scheduler.add_job(
        enviar_reactivaciones,
        "cron",
        day_of_week="wed",
        hour=16,
        minute=0,
        args=[app]
    )

    # Encuesta post-corte — cada día a las 10:00 Colombia (15:00 UTC)
    scheduler.add_job(
        enviar_encuestas,
        "cron",
        hour=15,
        minute=0,
        args=[app]
    )

    scheduler.start()
    print("⏰ Scheduler iniciado")
