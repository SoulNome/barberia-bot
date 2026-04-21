# Guía de onboarding — Agregar barbería nueva

Pasos para conectar una barbería nueva al sistema BarberIA.

---

## 1. Crear instancia en Evolution API

1. Entra al manager: `https://evolution-api-production-75a8.up.railway.app/manager`
2. Clic en **Create Instance**
3. Rellena:
   - **Instance Name**: slug de la barbería (ej. `djoc`) — sin espacios, minúsculas
   - **Token**: mismo valor que el slug (ej. `djoc`)
   - **Channel**: Evolution
4. Clic en **Create** → luego **Connect** → escanea el QR con el WhatsApp del barbero
5. Espera que diga **Connected**

---

## 2. Configurar webhook de la instancia

Dentro de la instancia recién creada, busca **Webhook** o **Events**:

- **URL**: `https://web-production-81c2.up.railway.app/bot/<slug>`
  - Ejemplo: `https://web-production-81c2.up.railway.app/bot/djoc`
- **Eventos**: activar solo `MESSAGES_UPSERT`
- Guardar

---

## 3. Registrar la barbería en el admin panel

1. Entra a: `https://web-production-81c2.up.railway.app/admin?key=<ADMIN_KEY>`
   - El `ADMIN_KEY` está en Railway → servicio `web` → Variables
2. Clic en **Nueva barbería** y rellena:

| Campo | Valor |
|-------|-------|
| Nombre | Nombre visible (ej. "Barbería DJOC") |
| Slug | El mismo que usaste en Evolution (ej. `djoc`) |
| Panel Key | Contraseña que usará el barbero para entrar a su panel |
| Teléfono | Número de contacto de la barbería (opcional) |
| Dirección | Dirección física (opcional) |
| Evolution API URL | `https://evolution-api-production-75a8.up.railway.app` |
| Evolution API Key | Ver Railway → servicio `evolution-api` → Variables → `AUTHENTICATION_API_KEY` |
| Evolution Instance | El nombre que pusiste en el paso 1 (ej. `djoc`) |
| WhatsApp Barbero | Número del barbero que recibe notificaciones (ej. `573001234567`) |

3. Clic en **Crear barbería**

---

## 4. Agregar barberos al panel

1. Entra al panel de la barbería nueva: `https://web-production-81c2.up.railway.app/panel/login`
2. Ingresa con el `panel_key` que creaste
3. Los barberos se agregan directamente desde la base de datos por ahora
   (próximamente desde el panel)

---

## 5. Verificar que funciona

Envía un mensaje de WhatsApp al número conectado en el paso 1. El bot debe responder con el menú de bienvenida.

Si no responde:
- Verifica que el webhook esté bien configurado (paso 2)
- Verifica que el slug en la URL del webhook coincida exactamente con el slug de la barbería en la DB
- Revisa los logs en Railway → servicio `web` → **Logs**

---

## Datos para darle al barbero

| Qué | Valor |
|-----|-------|
| URL del panel | `https://web-production-81c2.up.railway.app/panel` |
| Contraseña | el `panel_key` que configuraste |
| WhatsApp del bot | el número conectado en el paso 1 |

---

## Notas

- Cada barbería tiene sus datos completamente aislados (clientes, citas, barberos)
- Los horarios y servicios se configuran en el admin panel → Editar barbería → sección Horarios/Servicios
- Si no se configuran, se usan los horarios y servicios por defecto del sistema
