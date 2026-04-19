# BarberIA — Contexto del proyecto

Bot de WhatsApp para barberías desplegado en Railway (Flask + PostgreSQL + Evolution API).
Arquitectura multi-tenant: cada barbería tiene sus propios datos, credenciales y URL de webhook.

---

## Roadmap / Pendientes

### 1. Horarios, precios y servicios configurables por barbería ✅ COMPLETADO
- Actualmente hardcodeados en `disponibilidad_service.py` y `conversation_service.py`
- Agregar campos JSON en el modelo `Barberia`: `horarios_json`, `precios_json`, `servicios_json`
- El bot y el panel deben leerlos desde la BD en vez del código
- Sin esto, todas las barberías comparten el mismo menú y horario → bloqueante para vender

### 2. Panel super-admin para crear y configurar barberías ✅ COMPLETADO
- No hay forma de onboardear un cliente nuevo sin tocar la DB directamente
- Crear ruta `/admin` protegida con clave maestra (`ADMIN_KEY` env var)
- Permite: crear barbería, asignar slug/panel_key/credenciales Evolution, configurar horarios y precios
- También: ver lista de barberías activas y sus métricas básicas

### 3. Recordatorios automáticos para citas regulares (no solo fijos) ⬅ SIGUIENTE
- Los clientes normales no reciben recordatorio el día anterior a su cita
- El scheduler ya corre diariamente; agregar job que envíe WhatsApp a todos con cita mañana
- Por barbería, usando sus propias credenciales de Evolution

### 4. Actualizar Evolution API a v2 (fix @lid)
- Usuarios con "confirmaciones de lectura" desactivadas generan JIDs `@lid`
- Evolution API v1.8.6 no puede enviarles mensajes
- v2 lo soporta nativamente
- Requiere actualizar el servicio en Railway y ajustar el webhook si cambia el formato

### 5. Autenticación real del panel
- La `panel_key` en la URL es débil: cualquiera que la vea puede entrar
- Implementar login con usuario/contraseña + sesión (Flask-Login o JWT)
- Antes de tener más de 2-3 clientes esto se vuelve un riesgo

### 6. Métricas e informes históricos
- El panel solo muestra el día actual
- Agregar vista de: ingresos por mes, citas por semana, clientes más frecuentes, días más ocupados
- Diferenciador clave a la hora de vender ("ve cómo está tu negocio")

---

## Arquitectura actual (multi-tenant)

- **Bot webhook**: `/bot` (cliente legacy, usa env vars) · `/bot/<slug>` (nuevo, por barbería)
- **Panel**: `/panel?key=<panel_key>` — cada barbería accede con su propia key
- **Migración startup**: al arrancar, añade columnas multi-tenant y crea barbería por defecto desde env vars
- **`barberia_id`** en: `clientes`, `citas`, `user_states`, `lista_espera`

## Stack

- Python · Flask · SQLAlchemy · PostgreSQL
- Evolution API (WhatsApp) — instancia en Railway
- APScheduler (recordatorios y citas fijas)
- Deploy: Railway (web + postgres)

## Variables de entorno del super-admin

```
ADMIN_KEY  → clave maestra para acceder a /admin (independiente de PANEL_KEY)
```

Acceso: `GET /admin?key=<ADMIN_KEY>`

## Variables de entorno requeridas por barbería

```
BARBERIA_NOMBRE   → nombre visible
BARBERIA_SLUG     → identificador URL del webhook (/bot/<slug>)
PANEL_KEY         → clave de acceso al panel
EVOLUTION_API_URL → URL de Evolution API
EVOLUTION_API_KEY → API key global de Evolution
EVOLUTION_INSTANCE → nombre de la instancia WhatsApp conectada
HERMES_PHONE      → número del barbero principal (recibe notificaciones de nuevas citas)
```
