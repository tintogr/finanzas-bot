# 🤖 KNOT — ASISTENTE PERSONAL

Bot que interpreta mensajes de texto e imágenes con Claude y los guarda automáticamente en tu base de datos Notion, con el tipo de cambio del día incluido.

---

## Setup en 4 pasos

### 1. Crear Notion Integration Token

1. Ir a https://www.notion.so/profile/integrations
2. Click en **"New integration"**
3. Nombre: "Finanzas Bot"
4. Tipo: **Internal**
5. Click en **Save** → copiar el token (empieza con `secret_...`)
6. Volver a tu base de datos en Notion → click en los **...** (arriba a la derecha) → **Connections** → agregar tu integración "Finanzas Bot"

### 2. Deploy en Railway

1. Ir a https://railway.app y crear cuenta (gratis)
2. **New Project** → **Deploy from GitHub repo**
   - Si no tenés repo: crear uno en GitHub, subir estos archivos, y conectarlo
   - O usar **Deploy from local** con el CLI de Railway
3. Una vez deployado, Railway te da una URL como `https://tu-app.up.railway.app`

#### Variables de entorno en Railway:
En tu proyecto Railway → **Variables** → agregar:

| Variable | Valor |
|---|---|
| `TELEGRAM_TOKEN` | tu token de BotFather |
| `ANTHROPIC_API_KEY` | tu API key de Anthropic |
| `NOTION_TOKEN` | el token `secret_...` del paso 1 |
| `NOTION_DATABASE_ID` | `fb6b174a-301f-43e5-81b0-64d0ba53e234` |

### 3. Registrar el webhook de Telegram

Una vez que Railway te dé la URL pública, ejecutar localmente:

```bash
pip install httpx python-dotenv
cp .env.example .env
# Completar .env con tus valores reales
python setup_webhook.py https://tu-app.up.railway.app
```

### 4. ¡Listo! Probalo en Telegram

Abrí el chat con tu bot y mandá:
- `"Verdulería 4000"`
- `"Supermercado Día 12500"`
- `"Cargué 35 litros a 1400, km 48500"`
- Una foto de una factura

---

## Ejemplos de mensajes que entiende

| Mensaje | Qué detecta |
|---|---|
| `"Verdulería 4000"` | Egreso, $4000, Tipo: Comida |
| `"Me pagó Juan Martin 150000"` | Ingreso, $150000, Client: Juan Martin |
| `"Cargué 30L a $1400, km 47200"` | Egreso, $42000, litros, precio/L, km |
| Foto de factura de luz | Egreso, monto, Tipo: Servicios, kWh si aparece |
| `"Netflix 6500"` | Egreso, $6500, Tipo: Ocio, Type: Suscription |

---

## Archivos

- `main.py` — servidor FastAPI con el webhook
- `requirements.txt` — dependencias Python
- `setup_webhook.py` — script para registrar el webhook en Telegram
- `Procfile` — configuración de deploy para Railway
- `.env.example` — template de variables de entorno
