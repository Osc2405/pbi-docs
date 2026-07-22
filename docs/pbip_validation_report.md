# Informe de Validación — Soporte PBIP/TMDL

**Fecha:** 2026-07-15
**Fixture de prueba:** `files_test/Supply Chain Sample.pbip` (proyecto PBIP real, no sintético)
**Módulos bajo prueba:** `pbi_extractor/pbip_extractor.py`, `pbi_extractor/documentation.py`,
`pbi_extractor/indexed_output.py`, `pbi_extractor/toon_encoder.py`, `pbi_extractor/cli.py`

---

## 1. Resumen ejecutivo

Se ejecutó el pipeline completo de `pbi-docs` contra un modelo PBIP real (7 tablas, 4 measures,
2 relaciones, tabla de fechas oculta, columnas calculadas, measures multilínea) en lugar del
fixture sintético `tests/fixtures/minimal_pbip`. La prueba con datos reales expuso **5 bugs** que
no habían aparecido con el fixture sintético — todos corregidos y cubiertos con tests de
regresión. Tras las correcciones, la validación automatizada final sobre los archivos de salida
(formato `json` y `toon`) terminó en **PASS, 0 errores, 0 warnings**. Suite completa:
**125/125 tests pasando**.

**Estado global: ✅ APTO** — sujeto a los puntos "Fuera de alcance" (sección 5).

---

## 2. Bugs encontrados y corregidos

| # | Bug | Módulo | Severidad | Estado |
|---|-----|--------|-----------|--------|
| 1 | Los `.tmdl` reales viven bajo `<SemanticModel>/definition/`, no directo en `.SemanticModel/`. El extractor buscaba en la raíz → 0 tablas extraídas silenciosamente. | `pbip_extractor.py` (`find_semantic_model`, `parse_pbip_model`) | Crítica | Corregido |
| 2 | `_parse_table_column_ref` no quitaba comillas de la columna cuando la tabla no estaba entre comillas (`Explanations.'Product ID'` → columna quedaba `'Product ID'` con comillas literales). | `pbip_extractor.py` (`_parse_table_column_ref`) | Alta | Corregido |
| 3 | Columnas calculadas de una línea (`column 'Nombre' = <DAX>`) dejaban la expresión DAX pegada al nombre de la columna en vez de separarla. | `pbip_extractor.py` (`_parse_table_tmdl_file`) | Alta | Corregido |
| 4 | `model_documentation.md` generaba un header `### Tabla` vacío (sin columnas ni measures debajo) cuando una tabla visible tenía todas sus columnas individualmente ocultas. | `documentation.py` (`generate_markdown`) | Media | Corregido |
| 5 | Mismo bug que el #3 pero para columnas calculadas **multilínea** (`column 'Nombre' =` con el DAX en líneas siguientes) — encontrado en auditoría de seguimiento, sin ocurrencia real en el fixture pero mismo patrón que usan las measures multilínea. | `pbip_extractor.py` (`_parse_table_tmdl_file`) | Media (preventivo) | Corregido |

También se generalizó el parseo de relaciones (`_parse_model_tmdl` → `_parse_relationships_tmdl`)
para soportar los dos layouts reales de TMDL: relaciones embebidas en `model.tmdl` (anidadas) y el
archivo separado `relationships.tmdl` que usa este proyecto real (bloques a nivel raíz).

---

## 3. Validación de las salidas finales

### 3.1 Ejecución

Se corrió el CLI dos veces sobre el mismo modelo real, cubriendo ambos modos de índice:

```
pbi-docs -i "files_test/Supply Chain Sample.pbip" -o files_test/output
pbi-docs -i "files_test/Supply Chain Sample.pbip" -o files_test/output_toon --index-format toon
```

Resultado de extracción: **7 tablas, 4 measures, 2 relaciones, 13 columnas visibles, 9 líneas
JSONL** — en ambos modos.

También se verificaron los 3 puntos de entrada soportados (archivo `.pbip`, carpeta
`.SemanticModel/`, carpeta raíz del proyecto): los tres producen resultados idénticos.

### 3.2 Metodología

Script de validación cruzada (no persistido) que verificó, sobre los 7 archivos de salida +
`tables/*.json`:

- Existencia de todos los archivos esperados (`metadata.json`, `model_documentation.md`,
  `agent_context.json`, `model_context.jsonl`, `index.json`, `relationships.json`, `tables/`).
- Validez JSON línea por línea de `model_context.jsonl`.
- Paridad de tablas entre `index.json` y `metadata.json` (sin huérfanos).
- Cada `path` referenciado en `index.json` resuelve a un archivo real, y sus conteos
  (`column_count`, `measure_count`) coinciden con el detalle del archivo.
- `relationships.json`: conteo coincide con `summary.total_relationships`, las tablas
  referenciadas existen, sin comillas residuales en los nombres (regresión del bug #2).
- Sin nombres de columna/measure corruptos con `= <expr>` pegado (regresión de bugs #3 y #5).
- En modo TOON: `measures_dax` y `measures_flat` referencian el mismo conjunto de measures, y
  `measures_dax` solo expone `name` + `formatted_expression` (cumple el alcance acotado de TOON
  definido en `CLAUDE.md` — nunca DAX bajo TOON).
- `agent_context.json`: las measures listadas referencian tablas existentes.
- `model_documentation.md`: sin headers de tabla vacíos (regresión del bug #4).
- Round-trip real de TOON (`decode_toon`) sobre `relationships.json` y columnas de tabla —
  no solo verificación estructural, sino decodificación efectiva de vuelta a diccionarios.

### 3.3 Resultado

| Formato de índice | Archivos generados | Errores | Warnings |
|---|---|---|---|
| `json` (default) | 7 + `tables/*.json` (7) | 0 | 0 |
| `toon` | 7 + `tables/*.json` (7) | 0 | 0 |

**PASS en ambos formatos.**

---

## 4. Cobertura de tests

- Suite completa: **125/125 passing** (`python -m pytest tests/ -q`).
- Fixture sintético `tests/fixtures/minimal_pbip` migrado a layout `definition/` para reflejar la
  estructura real (antes no la reflejaba, lo cual ocultó el bug #1 hasta la prueba con datos
  reales).
- Tests de regresión añadidos esta sesión:
  - `test_parse_table_column_ref_*` (4 casos: tabla/columna con y sin comillas, combinaciones).
  - `test_parse_standalone_relationships_file` (layout `relationships.tmdl` a nivel raíz).
  - `test_parse_calculated_column_name_strips_expression` (columna calculada de una línea).
  - `test_parse_multiline_calculated_column_name_strips_expression` (columna calculada
    multilínea).
  - Test de "no header vacío" implícito en la validación de salida final (no unit test dedicado
    todavía — ver sección 5).

---

## 5. Fuera de alcance / pendientes (sin acción tomada, por diseño)

- **Contenido de particiones** (`mode`/`source`, query M): se descarta; el contrato actual solo
  usa `partition_count`, que es correcto. Ampliar el schema requeriría una decisión explícita
  (no tomada, per `CLAUDE.md`).
- **Propiedades TMDL de bajo riesgo** ignoradas silenciosamente sin corromper salida:
  `summarizeBy`, `sortByColumn`, `changedProperty`, `annotation` anidadas.
- **`cultures/*.tmdl`, `diagramLayout.json`, `definition.pbism`**: fuera del alcance explícito de
  esta fase (PBIR/reporte visual no se parsea, según `CLAUDE.md` sección 1).
- **No hay unit test dedicado** para el bug #4 (header vacío en markdown) — la cobertura actual es
  vía el script de validación de esta sesión, no persistido en `tests/`. Recomendado para una
  próxima iteración.
- **Nada de esta fase está commiteado todavía** — es una decisión pendiente del usuario, no
  técnica.

---

## 6. Conclusión

El soporte PBIP/TMDL, la salida indexada (`index.json` + `tables/*.json`) y el alcance acotado de
TOON están **implementados, verificados end-to-end contra un modelo real, y sin errores
pendientes conocidos** dentro del alcance definido en `CLAUDE.md`. Los 5 bugs encontrados durante
esta sesión de prueba con datos reales fueron específicos de patrones TMDL que no estaban
representados en el fixture sintético original — quedan corregidos y cubiertos por tests, con
excepción del hueco de cobertura anotado en la sección 5.
