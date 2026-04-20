# Plan de implementación: Fase 1 — Confianza y seguridad

**Spec:** `2026-04-20-fase1-confianza-design.md`
**Estado:** Implementado

---

## Cambios en main.py

### Funciones nuevas (después de `send_interactive_buttons`)

- `send_reaction(to, message_id, emoji)` — POST al WA API con `type: "reaction"`
- `error_servicio(servicio)` — retorna mensaje de error específico por servicio (notion/calendar/gmail)

### 1a — Reaction ✅

En `enqueue_message`, después de deduplicación y antes del if/elif de tipos:
```python
if msg_type != "reaction" and msg_id:
    asyncio.create_task(send_reaction(phone, msg_id, "✅"))
```

### 1b — Confirmación antes de eliminar

**Funciones refactorizadas** (add `phone` param, send buttons instead of deleting):
- `eliminar_gasto(text, phone=None)` — si phone: envía botones + sets confirm_delete pending_state, retorna `(True, "")`
- `eliminar_planta(text, phone=None)` — ídem
- `eliminar_reunion(text, phone=None)` — ídem

**En `handle_evento_agent`** (tool `eliminar_evento`):
- Reemplaza el bloque de delete directo por: envía botones, sets confirm_delete con `page_id = ev["id"]`, retorna tool_result "Pedí confirmación..."
- Al final del agente: si `pending_state[phone].type == "confirm_delete"` → return None (no enviar respuesta del agente)

**En `handle_salud_agent`** (tool `eliminar_registro_salud`):
- Reemplaza delete directo por: envía botones + sets confirm_delete (action: "health_record")
- Antes del final Claude call: si confirm_delete → return None

**En `handle_fitness_agent`** (tool `eliminar_actividad`):
- Reemplaza delete directo por: envía botones + sets confirm_delete (action: "fitness_entry")
- Antes del final Claude call: si confirm_delete → return None

**Callers en `process_single_item`**:
- `ELIMINAR_GASTO`, `ELIMINAR_PLANTA`, `ELIMINAR_REUNION`: pasan `phone`, solo `send_message(phone, msg)` si `msg` es no-vacío

**Handler en `handle_pending_state`** (antes de litros_followup):
- `confirm_delete`: chequea expiry (5 min), ejecuta delete según action, o cancela
- Actions: expense → archive_expense, plant → archive_plant, meeting → archive_meeting, event → GCal DELETE, health_record → archive_health_record, fitness_entry → archive_fitness

### 1c — Undo posterior a creaciones

**Nuevos `undo_window` pending_state en:**
- `handle_gasto_agent`: en else branch (cuando no es fuel ni factura_note) + cuando hay factura pero no impaga
- `process_single_item` PLANTA: después de `create_planta` exitosa
- `handle_reunion`: después de `_ds.create_meeting` (agrega `phone` param)
- `handle_deuda_agent`: después de `create_finance_invoice` exitosa

**`create_planta` modificada**: retorna `(True, plant.id)` en lugar de `(True, "")`

**`handle_reunion` modificada**: agrega `phone=None` param; captura return value de `_ds.create_meeting`; agrega `reply += "\n\n_Si algo no quedó bien, avisame._"` si phone

**Handler en `handle_pending_state`** (antes de litros_followup):
- `undo_window`: chequea expiry (60s), detecta `is_undo` via señales de lenguaje natural
- Si expired o no es undo → `del pending_state[phone]; return False` (procesa normalmente)
- Si es undo → ejecuta archive según action (expense/plant/meeting/finance_invoice)
- Actions no soportadas (event, etc.) → no implementadas en v1

### 1d — Errores de servicios externos

- `create_planta` except: retorna `error_servicio("notion")` en lugar de `str(e)`
- `handle_reunion` except `_ds.create_meeting`: retorna `error_servicio("notion")`
- `handle_pending_state` confirm_delete action=event: usa `error_servicio("calendar")` si falla
- `error_servicio` disponible para uso futuro en otros puntos críticos

---

## Estimación de riesgo

| Cambio | Riesgo | Nota |
|--------|--------|------|
| send_reaction | Bajo | Fire-and-forget, fallo silencioso |
| confirm_delete eliminar_* | Bajo | Agrega un paso, no rompe nada existente |
| confirm_delete en agentes | Medio | Suprime respuesta del agente, podría quedar silencioso si falla |
| undo_window gastos | Bajo | Solo en else branch, no afecta fuel ni facturas |
| undo_window plantas | Bajo | Solo cambia valor de retorno de create_planta |
| undo_window reuniones | Bajo | phone param es opcional, retrocompat garantizada |
| error_servicio | Bajo | Mejora mensajes existentes |
