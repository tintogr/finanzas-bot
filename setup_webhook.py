#!/usr/bin/env python3
"""
Ejecutar una vez después del deploy para registrar el webhook en Telegram.
Uso: python setup_webhook.py https://tu-app.railway.app
"""
import sys
import httpx

if len(sys.argv) < 2:
    print("Uso: python setup_webhook.py https://tu-url-de-deploy.app")
    sys.exit(1)

import os
from dotenv import load_dotenv
load_dotenv()

TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TOKEN:
    print("Error: TELEGRAM_TOKEN no encontrado en .env")
    sys.exit(1)

url = sys.argv[1].rstrip("/")
webhook_url = f"{url}/webhook"

response = httpx.post(
    f"https://api.telegram.org/bot{TOKEN}/setWebhook",
    json={"url": webhook_url}
)

data = response.json()
if data.get("ok"):
    print(f"✅ Webhook registrado correctamente: {webhook_url}")
else:
    print(f"❌ Error: {data}")
