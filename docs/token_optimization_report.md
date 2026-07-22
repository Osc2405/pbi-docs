# Informe de Optimización de Tokens — JSON vs TOON vs PBIP/TMDL crudo

**Fecha:** 2026-07-15  
**Modelo de referencia:** `files_test/Supply Chain Sample.pbip` (7 tablas, 4 measures, 2 relaciones)

---

## 1. Metodología

No hay tokenizador real de Claude disponible offline en este entorno, y agregar uno (ej. `tiktoken`) violaría el principio de cero dependencias externas del proyecto para un script de un solo uso. Se usa la aproximación estándar **caracteres ÷ 4** para texto en inglés/JSON/DAX, señalada explícitamente como aproximación en cada tabla. Los conteos de bytes son exactos (medidos directo del disco, no tipeados a mano).

**Actualización (2026-07-16):** ya existe `scripts/count_tokens.py`, que reemplaza esta
aproximación por un conteo real vía la API de Anthropic (`count_tokens`). No se corrió en esta
sesión porque el entorno no tiene `ANTHROPIC_API_KEY` configurada ni el paquete `anthropic`
instalado (ninguno de los dos es dependencia del proyecto). Para actualizar este informe con
conteos reales:
```
pip install anthropic
export ANTHROPIC_API_KEY=...
python scripts/count_tokens.py "files_test/Supply Chain Sample.SemanticModel/definition/tables"
python scripts/count_tokens.py "output/Supply Chain Sample/tables" "output/Supply Chain Sample/relationships.json"
```
Este ítem queda **bloqueado**, no simulado — las cifras de aproximación de abajo siguen siendo
caracteres÷4, no tokens reales, hasta que alguien con esas credenciales corra el script.

Se excluye `cultures/en-US.tmdl` de la comparación 'raw TMDL' porque `pbip_extractor.py` nunca lo parsea (metadata lingüística, no semántica del modelo) — son 118,945 bytes adicionales que un agente ingenuo podría leer igual si simplemente vuelca la carpeta `definition/` completa; se reportan aparte como el peor caso.

`.pbit` (ZIP + TMSL binario) no tiene equivalente de 'uso regular de archivo' — un agente no puede leerlo como texto sin extraerlo primero, así que esta comparación es específica a proyectos `.pbip`/TMDL, que sí son texto plano legible directamente.

---

## 2. Hallazgo cualitativo: ruido estructural en TMDL crudo

Los archivos `.tmdl` reales (excluyendo `cultures/`) contienen **222 líneas** de `lineageTag:`, `annotation`, `changedProperty` o `summarizeBy:` — GUIDs de linaje y metadata de edición del Desktop, cero valor semántico para responder preguntas sobre el modelo, y **nunca parseadas** por `pbip_extractor.py` (se descartan silenciosamente ya en el parser).

| Archivo | Líneas de ruido |
|---|---|
| `Supply Analytics.tmdl` | 59 |
| `Backorder Percentage.tmdl` | 55 |
| `DateTableTemplate_6de7953b-39de-41ab-b96b-cebbc3f3ccc1.tmdl` | 36 |
| `Risk.tmdl` | 25 |
| `Explanations.tmdl` | 22 |
| `Month.tmdl` | 13 |
| `Logo.tmdl` | 9 |
| `model.tmdl` | 3 |
| **Total** | **222** |

---

## 3. Comparación por escenario de uso

Los tres escenarios reflejan cómo el skill `analyze-pbi-model` (agregado la sesión pasada) realmente le indica a un agente que cargue archivos — nunca 'todo', primero `index.json`, y solo la(s) tabla(s) que la pregunta necesita.

### Escenario 1 — "¿Qué hay en este modelo?" (overview)

| Enfoque | Archivo(s) | Bytes | Tokens aprox. |
|---|---|---|---|
| Raw TMDL (core, sin `cultures/`) | 10 archivos `.tmdl` | 25,518 | 6,380 |
| Raw TMDL (dump ingenuo, con `cultures/`) | 11 archivos `.tmdl` | 144,463 | 36,116 |
| pbi-docs JSON | `index.json` | 2,307 | 577 |
| pbi-docs TOON | `index.json` (índice no usa TOON) | 2,307 | 577 |

**Ahorro vs raw TMDL (core): 91.0%** — `index.json` no existe en absoluto en un proyecto PBIP crudo; sin pbi-docs, un agente no tiene otra opción que abrir archivos de tabla individuales para siquiera saber cuántas tablas hay.

### Escenario 2 — "Explica las measures de Backorder Percentage" (tabla más grande)

| Enfoque | Archivo(s) | Bytes | Tokens aprox. |
|---|---|---|---|
| Raw TMDL | `Backorder Percentage.tmdl` | 6,661 | 1,665 |
| pbi-docs JSON | `tables/Backorder Percentage.json` | 4,304 | 1,076 |
| pbi-docs TOON | `tables/Backorder Percentage.json` | 3,595 | 899 |

**Ahorro vs raw TMDL:** JSON 35.4%, TOON 46.0%. **TOON vs JSON en esta tabla: -16.5%** (TOON gana aquí — 14 columnas + 4 measures es un array lo bastante grande y uniforme para que el wrapper `{__fields, __rows}` se amortice).

### Escenario 3 — Deep-dive completo (todas las tablas + relaciones)

| Enfoque | Archivo(s) | Bytes | Tokens aprox. |
|---|---|---|---|
| Raw TMDL (core) | 10 archivos | 25,518 | 6,380 |
| pbi-docs JSON | `tables/*.json` + `relationships.json` | 12,082 | 3,020 |
| pbi-docs TOON | `tables/*.json` + `relationships.json` | 11,670 | 2,918 |
| pbi-docs `metadata.json` (dump único, referencia) | `metadata.json` | 14,575 | 3,644 |

**Ahorro vs raw TMDL:** JSON 52.7%, TOON 54.3%. **TOON vs JSON agregado: -3.4%** — con este modelo (mayoría de tablas pequeñas), el agregado de TOON casi no gana sobre JSON plano; el ahorro real de TOON está concentrado en la tabla grande del escenario 2, no distribuido parejo.

---

## 4. TOON tabla por tabla — no es un ahorro uniforme

| Tabla | JSON (bytes) | TOON (bytes) | TOON vs JSON |
|---|---|---|---|
| `Backorder Percentage` | 4,304 | 3,595 | -16.5% |
| `Supply Analytics` | 2,997 | 2,515 | -16.1% |
| `DateTableTemplate_6de7953b-39de-41ab-b96b-cebbc3f3ccc1` | 1,425 | 1,391 | -2.4% |
| `Risk` | 1,122 | 1,216 | +8.4% |
| `Explanations` | 885 | 1,043 | +17.9% |
| `Month` | 482 | 768 | +59.3% |
| `Logo` | 295 | 645 | +118.6% |

Confirma empíricamente lo que `CLAUDE.md` ya establecía como principio de diseño (sección "Formato de serialización (TOON)"): TOON gana en arrays uniformes de tamaño considerable y puede *perder* contra JSON plano en tablas chicas, porque el overhead fijo del wrapper `{__toon, __fields, __rows}` no se amortiza con pocas filas. Confirma que el alcance acotado de TOON (no aplicarlo a texto libre / DAX, y aceptar que algunas tablas pequeñas no ganan) fue la decisión correcta, no una simplificación de más.

---

## 5. Conclusión

- pbi-docs JSON ahorra **91–53%** de tokens frente a leer TMDL crudo, dependiendo del escenario — el mayor ahorro es no tener que abrir ningún archivo en absoluto para preguntas de overview (`index.json` sustituye la necesidad de abrir cualquier `.tmdl`).

- TOON agrega un ahorro adicional **solo cuando la tabla es grande y uniforme** (hasta 16% adicional en la tabla más grande), pero puede costar más en tablas chicas — el ahorro agregado sobre el modelo completo es marginal (-3.4%) porque la mayoría de las tablas de este modelo son chicas.

- El ahorro dominante no viene del formato de serialización (JSON vs TOON), viene de **no cargar contenido irrelevante en absoluto** — `index.json` + carga selectiva de tablas. Esto es evidencia a favor de invertir en una interfaz de consulta bajo demanda (ej. servidor MCP) por sobre seguir optimizando el formato de codificación.
