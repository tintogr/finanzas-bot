# Bitácora de Knot — sesión de desarrollo (junio–julio 2026)

Documento extenso con **todo** lo que hablamos, cambiamos y decidimos, para retomar
sin perder contexto. El `CLAUDE.md` es el resumen corto; esto es el detalle.

---

## 0. Contexto
Knot es el bot personal de WhatsApp de Martin (Python/FastAPI en Render). Esta tanda de
trabajo arrancó cazando bugs del "buenos días" y terminó construyendo un sistema de
servicios completo, arreglando ~12 bugs de conversación y limpiando las finanzas de junio.
Workflow: se mergea a `main` y Render deploya solo. Commits relevantes citados abajo.

---

## 1. Model IDs retirados y centralización
**Problema:** el modelo `claude-sonnet-4-20250514` fue retirado por Anthropic → `404
NotFoundError` en cada llamada (registrar un gasto rompía todo). Estaba hardcodeado en ~45
lugares.
**Fix:** reemplazado por `claude-sonnet-4-6` y **centralizado** en `state.py` como
`SONNET_MODEL` / `HAIKU_MODEL` (overridables por env var). `claude_create()` default-ea a
`SONNET_MODEL`. Commits `1e3bb3d`, `e8db681`.
**Regla a futuro:** nunca hardcodear model IDs; usar las constantes.

## 2. Clima y resúmenes
- `get_weather()` fallaba silencioso → se agregó logging y (en trabajo paralelo) fallback a
  wttr.in si Open-Meteo falla.
- Se crean al startup los campos `Latitude`/`Longitude`/`City` en la Config DB de Notion
  (antes `save_location` fallaba silencioso porque no existían → el clima quedaba sin coords
  tras cada reinicio).
- **Resumen nocturno/dominical:** disparaba con `minute == 0` exacto; si el cron corría 1
  minuto tarde se perdía. Ahora tiene ventana de 3 min con tracking (igual que el diario).

## 3. Bugs de conversación (la familia más grande)
Todos eran "Knot se pierde o cruza los datos":

- **Comprobantes leídos al revés** (`92e1516`): un pago tuyo (ej: expensas, De: Martin →
  Para: Consorcio) se registraba como **ingreso/Sueldo**. Se agregaron reglas de dirección
  De/Para al prompt del agente de gastos: si el remitente es el usuario → EGRESO.

- **"¿Con qué pagaste?" (ask_payment_method) inteligente** (`92e1516` y afinado después):
  si respondías otra cosa, consumía el mensaje y lo perdía. Ahora combina scoring + una
  desambiguación con Haiku (método / SKIP / otra intención) y, si es otra intención, suelta
  el estado y **re-rutea** el mensaje.

- **Responder/citar mensajes viejos de WhatsApp** (`65b9dd7`): el webhook ignoraba
  `message.context` (la cita). Ahora se guarda un mapa `wamid → texto` de entrantes y
  salientes (`state.recent_message_texts` + `record_message_text`, y `wa_utils` registra el
  id de cada mensaje que manda), y cuando citás un mensaje se inyecta como contexto al
  clasificar. Limitación: el mapa vive en memoria, no sobrevive reinicios de Render.

- **Gastos en USD** (`25e8376`): "gasté 250 usd en X" convertía a pesos pero **no
  registraba** — preguntaba el método en texto libre y perdía el contexto. Ahora el prompt
  obliga a convertir USD→ARS y registrar igual (con "(USD X)" en notas), sin preguntar el
  método de palabra (de eso se encarga el flujo ask_payment_method).

- **El agente de gastos ahora tiene historial** (`624f21b`): `handle_gasto_agent` procesaba
  cada mensaje aislado. "supermercado" ... "42000" en mensajes separados nunca se juntaban.
  Ahora recibe `get_history(phone)` (mismo patrón que el agente de eventos) y acumula datos
  multi-mensaje; con salvaguarda de no re-registrar gastos ya confirmados (con ✅).

- **La pregunta de método no se come gastos nuevos** (`cfda87c`, `4cc73d6`): una pregunta
  "¿con qué pagaste?" quedó abierta 2 días; el mensaje "carne y atun 93mil la anonima
  **efectivo**" la respondió sin querer → le puso Efectivo a Camuzzi y **el gasto de $93.000
  se perdió**. Fix: si el mensaje parece un **gasto nuevo completo** (monto + ≥3 palabras y el
  número no es un last4 de tarjeta), NO es respuesta al método → se re-rutea como gasto nuevo,
  aunque diga "efectivo". (Se probó un timeout de 1h pero se quitó: la regla contextual
  alcanza — decisión de Martin.)

- **Día recurrente del calendario** (`111525e`): "no voy más los jueves" hacía que el agente
  llamara a borrar una vez por cada jueves futuro → 3 confirmaciones "¿Eliminás Funcional?" y
  encima no podía apuntar solo a esa serie. Ahora `eliminar_evento` tiene un param `weekday`:
  si dejás de ir un día recurrente, borra **solo esa serie** (matcheando por
  `recurringEventId` de las instancias de ese día) con **una** confirmación. Se distingue
  "el jueves 25 no voy" (target_date) de "no voy más los jueves" (weekday). También se
  arregló que `confirm_delete` borre los `extra_events` (antes se guardaban pero no se
  borraban).

- **Emails de servicios pagados** (`09498fa`): el mail "Abono vencido" del gimnasio seguía
  apareciendo en "Emails importantes" aunque estuviera pagado. Ahora `get_important_emails`
  le pasa al clasificador la lista de servicios conocidos (empresas + aliases de la DB
  Servicios) con la orden de **ignorar** recordatorios de pago/abono/vencimiento de esos
  servicios.

## 4. Facturas — lectura con visión y dedup
El "buenos días" creaba facturas duplicadas y con montos inventados. Evolución del fix:

- **Leer los PDF adjuntos con visión** (`a339356`): antes las facturas que se creaban en
  Notion salían de re-parsear un resumen de texto de 5 líneas con Haiku (perdía montos). Se
  creó `get_invoices_from_gmail(now)` en `summaries.py`: descarga los PDF adjuntos y se los
  pasa a Sonnet como document blocks → lee el "TOTAL A PAGAR" real. Canoniza el proveedor
  contra la DB Servicios.

- **Dedup robusto** (varios commits):
  - `4327eba`: match por **tokens** del proveedor (no substring): "CALF Energía" = "CALF
    (Luz)"; "calf" no colisiona con "calfibra".
  - `785fcbe`: también por el **mes del campo Date** (las entradas reales se llaman
    "Expensas", "Calf Energía" sin el mes en el nombre) y por **monto** (±2%, ≤45 días).
  - `6ea4ff8`: **no crear facturas en $0** (avisos "abono vencido" sin importe).
  - `bae7796`: buscar candidatos por **cada token** del proveedor (así "Interfast Expensas"
    encuentra la entrada "Expensas").
  - `532159a`: dedup **alias-aware** vía `service_of` (Interfast ↔ Expensas).

## 5. Sistema de Servicios (lo más grande — nuevo)
DB Notion **"Servicios"** creada bajo la página Networth. Es la **fuente de verdad** para
identificar servicios aunque el nombre varíe.
- Database id `922e0822baee4d1bba19e778e0e177d4`; data source `2d3de41d-6d68-4f7f-bbf8-87bb6d5762a0`.
- Campos: **Servicio** (título), **Empresa**, **Aliases** (palabras clave separadas por coma),
  **Categoría** (Recurrente/Servicio/Impuestos/Suscripciones), **Tipo** (Hogar/Suscripción/
  Impuesto), **Frecuencia** (Mensual/Bimestral/Trimestral/Anual), **Pagado hasta** (fecha,
  para prepagos/anuales — Knot no lo marca pendiente antes), **Vence dia**, **Llega por mail**
  (checkbox), **Activo** (checkbox).
- **13 servicios cargados:**
  - Hogar: Luz (CALF), Internet (Calfibra), Gas (Camuzzi, bimestral), Expensas (Interfast /
    Consorcio ARIES VI), Agua (EPAS — Llega por mail ☐), Teléfono (Movistar), Gimnasio (Box
    Gym Neuquén).
  - Impuesto: Monotributo (ARCA — Llega por mail ☐).
  - Suscripciones: OneDrive (Microsoft, anual, pagado hasta ~abr 2027), Render (mensual,
    compartida con Tincho — un mes cada uno, USD 38), Photoshop (Adobe, 3 meses gratis por
    retención hasta ~jul 2026, activo), iCloud (Apple), Real-Debrid (trimestral, USD 12 c/3
    meses, pagado hasta ~ago 2026).
- Código: `_ds.load_services()` al startup (`state.SERVICES_DB_ID`, env `NOTION_SERVICES_DB_ID`);
  `_ds.service_of(text)` mapea texto→servicio vía aliases. Usado en el dedup y en el extractor.
- **Categoría "Suscripciones"** agregada a la DB Finanzas (se agregó preservando las 19
  categorías existentes; ojo: agregar opciones a un multi-select en la API **reemplaza** el
  set, hay que listar TODAS las opciones con sus colores exactos).

## 6. Limpieza de datos en Notion (finanzas)
- **Junio reconciliado** contra el resumen PDF de Mercado Pago: se cargaron ~24 gastos
  desglosados + 5 ingresos (sueldos de Rafael $2.5M, préstamo del papá $100k marcado
  pendiente, reembolsos de Mati/Ana). Excluidos: compra de dólar MEP, transferencias entre
  cuentas propias, rendimientos.
- **Duplicados de facturas removidos** (movidos fuera de Finanzas, reversible): variantes de
  CALF, Calfibra junio, Camuzzi en $0, y el **ingreso fantasma** "Transferencia MP - Varios
  +$102.250" (era el pago de expensas mal leído).
- **CALF explicado:** la de junio dio $91.618,57 (real, sin descuento) vs mayo $13.414,52
  (tenía devolución de anticipo). ~La mitad de la factura son impuestos/aportes, no luz.
- **Apple Watch:** corregido de USD 200 → **USD 250** (misma entrada, no duplicado).
- **Camuzzi 2 períodos / carne y atún:** Camuzzi corregido a MP Transferencia; el gasto
  perdido de **$93.000** (carne y atún, La Anónima, efectivo) recuperado y cargado; a la
  Verdulería $2.800 se le limpió el Efectivo mal asignado.
- **EPAS:** deuda acumulada $507.459,01 registrada (pagada 11/06); recordatorio mensual de
  calendario creado (día 10) porque EPAS no manda factura por mail.
- **Monotributo junio** ($42.386,74 pagado 13/06 vía ARCA) registrado; el recordatorio que se
  había creado se borró (ya estaba pago).

## 7. IDs de Notion clave
- Finanzas (data source): `2b717b92-440a-4d78-a59a-723c913d6f5c`
- Servicios (database): `922e0822baee4d1bba19e778e0e177d4` — (data source `2d3de41d-6d68-4f7f-bbf8-87bb6d5762a0`)
- Métodos de pago (data source): `61930ca6-a8e2-4238-9b2e-bc4a69844624`
- Página Networth (padre): `aa49a53f5ebf4cfd90b37843da1001fb`

## 8. Hoja de ruta pendiente
1. **Aprendizaje de aliases**: cuando Martin aclara un proveedor nuevo ("interfast es
   expensas"), agregar el alias a la DB Servicios automáticamente.
2. Usar `service_of` para clasificar **pagos** ("pagué interfast" → Expensas) en el agente
   de gastos (hoy solo se usa en facturas).
3. **Recordatorios automáticos** de servicios con `Llega por mail = ☐` (EPAS, Monotributo)
   usando `Vence dia`.
4. **Comparar facturas mes a mes** y explicar subas (ej: "¿por qué la luz salió cara?") — se
   apoya en la lectura de PDFs ya hecha. (Sugerencia: arrancar por acá.)
5. **Ingesta de resúmenes PDF de Mercado Pago**: que Martin mande el PDF y Knot reconcilie
   solo (parsear movimientos + clasificar con contexto + dedup contra Notion). La versión
   "en serio" de lo que hicimos a mano en junio.

## 9. Cosas para verificar / abiertas
- Verdulería $2.800 y Vianda $11.000 (22/07): quedaron **sin método de pago** confirmado.
- El mapa de mensajes citados no sobrevive reinicios de Render (aceptable para un bot
  personal; persistirlo sería un extra).
- Movistar tiene varias entradas históricas; se puede ordenar como se hizo con CALF si molesta.
