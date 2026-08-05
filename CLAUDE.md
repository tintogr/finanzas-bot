# Knot — estado del proyecto

Bot personal de WhatsApp (Python / FastAPI) desplegado en **Render** (auto-deploy al pushear a `main`).
El dueño es **Martin** (arquitecto, no programador — todo el código lo genera Claude).

## Archivos
- `main.py` — webhook, clasificador, handlers de agentes (gastos, eventos, etc.), lógica de negocio.
- `notion_datastore.py` — `NotionDataStore`: acceso a las DBs de Notion (finanzas, servicios, etc.).
- `summaries.py` — resúmenes diario/nocturno, clima, lectura de facturas de Gmail (con visión de PDFs).
- `state.py` — globals compartidos, constantes, `SONNET_MODEL` / `HAIKU_MODEL`, `_ds`.
- `config.py`, `wa_utils.py`, `gcal.py` — config de usuario, WhatsApp, Google Calendar.

## Workflow de git
Somos los únicos dos devs. **Mergear directo a `main` y pushear** (Render deploya solo). No hace falta PR.
Verificar sintaxis antes de commitear: `python -c "import ast; ast.parse(open('main.py',encoding='utf-8').read())"`.
Nunca usar comillas tipográficas en el código. Model IDs centralizados en `state.py` (`SONNET_MODEL`/`HAIKU_MODEL`).

## Sistema de Servicios (fuente de verdad)
DB Notion **"Servicios"** (database `922e0822baee4d1bba19e778e0e177d4`, data source `2d3de41d-6d68-4f7f-bbf8-87bb6d5762a0`).
Cada servicio: Servicio, Empresa, **Aliases**, Categoría, Tipo (Hogar/Suscripción/Impuesto), Frecuencia, Pagado hasta, Vence dia, Llega por mail, Activo.
`_ds.load_services()` la carga al startup; `_ds.service_of(text)` mapea texto→servicio vía aliases (ej: "interfast" → Expensas). Se usa en el dedup de facturas y en la canonización del extractor.
DB Finanzas: data source `2b717b92-440a-4d78-a59a-723c913d6f5c`. Categoría "Suscripciones" para apps.

## Contexto que Knot usa para clasificar
- **Rafael Lorenzo** = jefe de Martin → sus transferencias por MP = **Sueldo**.
- Facturas de servicios: se leen del PDF adjunto del mail (montos reales) y se deduplican por proveedor (tokens + aliases) + mes + monto.

## Trabajo reciente (feat/fix ya deployados)
- Lectura de PDFs de facturas con visión; dedup robusto (no recrea pagadas ni crea $0).
- DB Servicios + aliases + categoría Suscripciones.
- Bugs de conversación: comprobantes con dirección De/Para, método de pago inteligente, respuestas a mensajes citados, gastos en USD, historial en el agente de gastos, día recurrente del calendario con una sola confirmación, emails de servicios pagados que no molestan.

## Hoja de ruta pendiente
1. **Aprendizaje de aliases**: cuando Martin aclara un proveedor nuevo, agregar el alias a la DB Servicios solo.
2. Usar `service_of` para clasificar **pagos** ("pagué interfast" → Expensas) en el agente de gastos.
3. **Recordatorios automáticos** de servicios con `Llega por mail = ☐` (EPAS, Monotributo) usando `Vence dia`.
4. **Comparar facturas mes a mes** y explicar subas (ej: "¿por qué la luz salió cara?") — se apoya en la lectura de PDFs.
5. **Ingesta de resúmenes PDF de Mercado Pago** (parsear movimientos + clasificar + dedup).

## Reglas críticas
- Timezone: usar `now_argentina()`, nunca `datetime.now()` naive.
- Notion: nunca crear páginas/DBs sin pedir; `except Exception: pass` esconde errores — verificar contenido real.
- WhatsApp: número entrante `549...`, saliente `541...`; límite 1024 chars en interactivos.
