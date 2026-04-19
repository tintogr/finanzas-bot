# Sistema unificado de facturas e historial de pagos

**Fecha:** 2026-04-19
**Estado:** Aprobado

## Problema

El sistema actual crea tasks en Notion cuando se detecta una factura en Gmail y las marca como "Listo" cuando el usuario confirma el pago. Esto tiene tres problemas:

1. Al marcar como pagada, la task desaparece y se pierde todo contexto (cuánto se pagó, cuándo, por qué difirió el monto).
2. El cruce de facturas en el resumen diario usa a Claude como árbitro entre Gmail y Finanzas, lo que produce falsos positivos (ej: $9500 matcheando una factura de $6500).
3. No existe forma de registrar deudas genéricas ("le debo $4000 a Sofi") de manera estructurada.

## Solución

La DB de Finanzas pasa a ser la fuente de verdad de todo movimiento de dinero — pagado o pendiente. Las Tasks siguen existiendo como cola de acción/recordatorio, pero el estado real vive en Finanzas.

## Cambios en Notion

### Finanzas DB — dos campos nuevos

- `Estado` (select): `Impaga` | `Pagada`. Entradas sin este campo = tratadas como Pagada por el código (retrocompatibilidad, sin migración).
- `Medio de Pago` (select): lista configurable por usuario en user_prefs. Default: `BBVA, Mercado Pago, Efectivo, Transferencia, Débito, Crédito, Contado`.

## Flujos

### Flujo 1 — Detección de factura en Gmail (resumen diario)

1. Se detecta factura de proveedor X por $N en Gmail.
2. Knot busca en Finanzas:
   - ¿Entrada Impaga para proveedor X en el período actual? → ya existe, no crear duplicado.
   - ¿Entrada Pagada reciente (mes actual o anterior) con monto ±10%? → ya pagada, no mostrar.
   - ¿Entrada Pagada reciente con monto que difiere >10%? → preguntar al usuario (ver Flujo 4).
   - Ninguna de las anteriores → crear entrada Impaga + Task.
3. El resumen muestra solo las entradas Impaga activas. No hay cruce Gmail×Finanzas vía Claude.

### Flujo 2 — Usuario confirma pago

- *"Pagué Movistar"* / *"Pagué Movistar $6500 con BBVA"*
- Knot busca entradas Impaga para ese proveedor ordenadas por fecha desc. Si hay más de una (distintos períodos), usa la más reciente.
- Si el monto coincide con el de la entrada (±10%): marca Pagada + guarda medio de pago si se mencionó. Sin preguntas.
- Si el monto difiere >10%: pregunta por nota. El usuario puede aclarar ("debía del mes anterior"). La nota se guarda en el campo Notes de la entrada. Luego marca Pagada.
- Cierra la Task correspondiente en ambos casos. La Task almacena el `finance_page_id` en sus Notes (JSON) para poder referenciar la entrada exacta.

### Flujo 3 — Pago directo sin Impaga previa

- *"Pagué la luz $4500"*
- Knot busca entrada Impaga para ese proveedor.
- Si existe: la actualiza (Pagada + monto real + medio + nota si aplica).
- Si no existe: crea entrada nueva directamente como Pagada. Comportamiento idéntico al actual.

### Flujo 4 — Pre-pago (el usuario pagó antes de que llegue la factura)

- Usuario registra "Movistar $4999". Una semana después llega la factura por $6500.
- El resumen detecta la factura. Encuentra una entrada Pagada de $4999 para Movistar en el período.
- Diferencia >10% → Knot pregunta: *"Registraste $4999 para Movistar, la factura llegó por $6500. ¿Ya está cubierto o falta pagar la diferencia?"*
- Usuario responde → Knot actualiza según corresponda (agrega nota o crea nueva entrada Impaga por la diferencia).

### Flujo 5 — Deuda genérica

- *"Le debo $4000 a Sofi"*
- Crea entrada en Finanzas (Estado=Impaga, categoría libre, nombre="Deuda Sofi") + Task recordatorio.
- El pago posterior sigue el Flujo 2 o 3 igual que cualquier otra deuda.

### Flujo 6 — Consulta de historial

- *"¿Cuándo pagué Movistar?"* / *"¿Por qué pagué de más en marzo?"*
- El agente de chat consulta Finanzas filtrando por nombre de proveedor + Estado=Pagada, ordenado por fecha descendente.
- Devuelve historial con montos, fechas, medio de pago y notas.

## Medio de pago

- Lista configurable guardada en user_prefs como `payment_methods: list[str]`.
- Default: `["BBVA", "Mercado Pago", "Efectivo", "Transferencia", "Débito", "Crédito", "Contado"]`.
- El usuario puede agregar o quitar opciones mediante comando de configuración.
- Se captura solo si el usuario lo menciona explícitamente. No es obligatorio.

## Retrocompatibilidad

- Entradas existentes en Finanzas sin campo `Estado`: tratadas como Pagada en toda la lógica nueva.
- Las Tasks existentes sin referencia a una entrada de Finanzas siguen funcionando igual hasta que venzan o se cierren.
- No se requiere migración de datos.

## Componentes a implementar

### Notion (una sola vez)
- Agregar campo `Estado` (select) a la DB de Finanzas.
- Agregar campo `Medio de Pago` (select) a la DB de Finanzas.

### notion_datastore.py
- `create_finance_invoice(provider, amount, period, due_date, category)` → crea entrada Impaga. Retorna `page_id`.
- `get_impaga_facturas(provider=None)` → lista de entradas Estado=Impaga, ordenadas por fecha desc.
- `get_finance_history_by_provider(provider, limit)` → entradas Estado=Pagada para ese proveedor, ordenadas por fecha desc.
- `mark_finance_paid(page_id, paid_amount, payment_method, notes)` → actualiza entrada a Pagada.
- Actualizar `create_entry` para aceptar `estado` y `medio_de_pago`.
- Actualizar `create_factura_task` para almacenar `finance_page_id` en el JSON de Notes de la Task.

### main.py
- Actualizar detección de facturas en `send_daily_summary` para usar `get_impaga_facturas()`.
- Actualizar handler de `marcar_factura_pagada` para detectar diferencia de monto y pedir nota.
- Actualizar `handle_gasto` para buscar Impaga antes de crear entrada nueva.
- Agregar tool `consultar_deudas` al agente de chat (lista de entradas Impaga).
- Agregar `payment_methods` a user_prefs y al flujo de configuración.
