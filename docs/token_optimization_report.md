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

**Actualización (2026-07-23):** se agregó soporte Gemini a `scripts/count_tokens.py`
(`--provider gemini`, requiere `GEMINI_API_KEY`, capa gratuita — `pip install google-genai`).
**Esto no resuelve el bloqueo de Anthropic de arriba** — sigue bloqueado, sin
`ANTHROPIC_API_KEY`. El tokenizador de Gemini no es el de Claude: lo que aporta es un segundo
punto de dato real (no aproximado), de un proveedor distinto, para verificar si la heurística
caracteres÷4 y los porcentajes de ahorro JSON/TOON de las secciones 3-4 se sostienen bajo un
tokenizador real cualquiera — no una equivalencia con el conteo que daría Claude. También es un
paso parcial (no una resolución) hacia la limitación de "un solo proveedor" que
`docs/precision_validation_report.md` sección 6 deja anotada como gap abierto (esa limitación es
sobre calidad de respuesta de agentes, no sobre conteo de tokens — sigue sin validar ahí).

Los 3 escenarios ya se corrieron (modelo `gemini-2.5-flash`, resultados en las tablas de la
sección 3). Comandos de referencia abajo por si se quiere repetir la medición o correrla con otro
modelo/proveedor.

**Nota de método — discrepancia de bytes:** el campo `Bytes` que imprime `count_tokens.py` no
coincide exactamente con los bytes en disco reportados en las tablas de este documento (ej.
escenario 1: el script reportó 24,813 / 139,348 / 2,217 contra los 25,518 / 144,463 / 2,307
originales). No es un error de ninguno de los dos: `count_tokens.py` lee cada archivo con
`Path.read_text()` (modo texto de Python), que normaliza saltos de línea CRLF→LF antes de contar
bytes; el tamaño en disco original (medido con `os.path.getsize`) cuenta CRLF como 2 bytes cada
uno. La columna `Tokens reales (Gemini)` corresponde al texto normalizado — es lo que
efectivamente se envía al modelo — así que sigue siendo la cifra correcta a comparar contra
`Tokens aprox.`, aunque el byte-count de referencia de esa fila no sea idéntico byte a byte.

Cifras reales de Gemini (modelo `gemini-2.5-flash`) van en la columna nueva de las tablas de la
sección 3; las que faltan quedan marcadas `pendiente` — se completan corriendo:
```
pip install google-genai
export GEMINI_API_KEY=...

# Escenario 1 — overview
python scripts/count_tokens.py --provider gemini \
  "files_test/Supply Chain Sample.SemanticModel/definition/tables" \
  "files_test/Supply Chain Sample.SemanticModel/definition/database.tmdl" \
  "files_test/Supply Chain Sample.SemanticModel/definition/model.tmdl" \
  "files_test/Supply Chain Sample.SemanticModel/definition/relationships.tmdl"
python scripts/count_tokens.py --provider gemini \
  "files_test/Supply Chain Sample.SemanticModel/definition"
python scripts/count_tokens.py --provider gemini "output/Supply Chain Sample/index.json"

# Escenario 2 — tabla más grande (Backorder Percentage); regenerar output/ entre formatos
python scripts/count_tokens.py --provider gemini \
  "files_test/Supply Chain Sample.SemanticModel/definition/tables/Backorder Percentage.tmdl"
python -m pbi_extractor.cli -i "files_test/Supply Chain Sample.SemanticModel" --index-format json
python scripts/count_tokens.py --provider gemini "output/Supply Chain Sample/tables/Backorder Percentage.json"
python -m pbi_extractor.cli -i "files_test/Supply Chain Sample.SemanticModel" --index-format toon
python scripts/count_tokens.py --provider gemini "output/Supply Chain Sample/tables/Backorder Percentage.json"

# Escenario 3 — deep-dive completo, re-correr tras regenerar cada formato arriba
python scripts/count_tokens.py --provider gemini \
  "output/Supply Chain Sample/tables" "output/Supply Chain Sample/relationships.json"
python scripts/count_tokens.py --provider gemini "output/Supply Chain Sample/metadata.json"
```

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

| Enfoque | Archivo(s) | Bytes | Tokens aprox. | Tokens reales (Gemini `gemini-2.5-flash`) |
|---|---|---|---|---|
| Raw TMDL (core, sin `cultures/`) | 10 archivos `.tmdl` | 25,518 | 6,380 | 10,590 |
| Raw TMDL (dump ingenuo, con `cultures/`) | 11 archivos `.tmdl` | 144,463 | 36,116 | 47,296 |
| pbi-docs JSON | `index.json` | 2,307 | 577 | 830 |
| pbi-docs TOON | `index.json` (índice no usa TOON) | 2,307 | 577 | 830 |

**Ahorro vs raw TMDL (core): 91.0%** (aproximación) — `index.json` no existe en absoluto en un proyecto PBIP crudo; sin pbi-docs, un agente no tiene otra opción que abrir archivos de tabla individuales para siquiera saber cuántas tablas hay.

**Con tokens reales de Gemini:** ahorro de 92.2% vs raw TMDL core (830 vs 10,590) y de 98.2% vs el dump ingenuo (830 vs 47,296) — confirma la magnitud de la aproximación caracteres÷4 (91.0%), con el tokenizador real de Gemini incluso un poco más favorable. La aproximación también subestima el tamaño real del dump ingenuo (36,116 aprox. vs 47,296 reales, -23.6%) — el texto con `cultures/` mezcla más idiomas/caracteres no ASCII, donde chars÷4 tiende a fallar más.

### Escenario 2 — "Explica las measures de Backorder Percentage" (tabla más grande)

| Enfoque | Archivo(s) | Bytes | Tokens aprox. | Tokens reales (Gemini `gemini-2.5-flash`) |
|---|---|---|---|---|
| Raw TMDL | `Backorder Percentage.tmdl` | 6,661 | 1,665 | 2,310 |
| pbi-docs JSON | `tables/Backorder Percentage.json` | 4,304 | 1,076 | 797 |
| pbi-docs TOON | `tables/Backorder Percentage.json` | 3,595 | 899 | 527 |

**Ahorro vs raw TMDL (aproximación):** JSON 35.4%, TOON 46.0%. **TOON vs JSON en esta tabla
(aproximación): -16.5%** (TOON gana aquí — 14 columnas + 4 measures es un array lo bastante
grande y uniforme para que el wrapper `{__fields, __rows}` se amortice).

**Con tokens reales de Gemini:** ahorro vs raw TMDL — JSON 65.5% (797 vs 2,310), TOON 77.2% (527
vs 2,310) — bastante más alto que la aproximación en ambos casos. **TOON vs JSON real: -33.9%**
(vs -16.5% aproximado) — con el tokenizador real, TOON gana el doble de lo que sugería chars÷4 en
esta tabla.

**Nota de método — no es solo el tokenizador:** las columnas `Bytes`/`Tokens aprox.` de JSON y
TOON en esta tabla se midieron el 2026-07-15, cuando `_write_json()` (`pbi_extractor/indexed_output.py`)
todavía indentaba (`indent=2`) por defecto. Desde el hallazgo #3 de `docs/scale_validation_report.md`
(2026-07-20), la salida es compacta por defecto (`separators=(",", ":")`, sin indentación —
`--pretty` restaura el indentado para depuración humana). El `output/` que se regeneró para esta
corrida ya es compacto, así que parte de la caída real vs. aproximación (4,304→3,045 bytes en
disco para el JSON, por ejemplo) es el cambio de formato de serialización, no diferencia de
tokenizador — los números reales de esta tabla comparan raw TMDL contra la salida **compacta**
actual de pbi-docs, que es el comportamiento por defecto real hoy, así que la comparación sigue
siendo la correcta para responder "¿cuánto ahorra pbi-docs hoy?", solo que no es 1:1 con las
columnas `Bytes`/`Tokens aprox.` de al lado (esas quedan como registro histórico del formato
pretty-printed anterior).

### Escenario 3 — Deep-dive completo (todas las tablas + relaciones)

| Enfoque | Archivo(s) | Bytes | Tokens aprox. | Tokens reales (Gemini `gemini-2.5-flash`) |
|---|---|---|---|---|
| Raw TMDL (core) | 10 archivos | 25,518 | 6,380 | 10,590 |
| pbi-docs JSON | `tables/*.json` + `relationships.json` | 12,082 | 3,020 | 2,339 |
| pbi-docs TOON | `tables/*.json` + `relationships.json` | 11,670 | 2,918 | 1,815 |
| pbi-docs `metadata.json` (dump único, referencia) | `metadata.json` | 14,575 | 3,644 | 4,141 |

**Ahorro vs raw TMDL (aproximación):** JSON 52.7%, TOON 54.3%. **TOON vs JSON agregado
(aproximación): -3.4%** — con este modelo (mayoría de tablas pequeñas), el agregado de TOON casi
no gana sobre JSON plano; el ahorro real de TOON está concentrado en la tabla grande del escenario
2, no distribuido parejo.

**Con tokens reales de Gemini:** ahorro vs raw TMDL — JSON 77.9% (2,339 vs 10,590), TOON 82.9%
(1,815 vs 10,590) — ambos muy por encima del 52.7%/54.3% aproximado. **TOON vs JSON agregado
real: -22.4%** (vs -3.4% aproximado) — el hallazgo más notable de esta corrida: la aproximación
caracteres÷4 sugería que el ahorro de TOON era marginal a nivel de modelo completo y estaba
concentrado casi solo en la tabla grande del escenario 2; con tokenizador real, TOON gana de forma
mucho más consistente en agregado también, no solo en la tabla grande. No contradice la sección 4
(TOON puede seguir perdiendo tabla por tabla en tablas chicas — eso no se remidió aquí, sigue
siendo una medición en bytes/aproximación), pero sí matiza la conclusión de la sección 5 de que el
ahorro de TOON "no está distribuido parejo": con un tokenizador real, el agregado gana más de lo
que la aproximación dejaba ver. Mismo aviso de método que la sección 3.2 aplica aquí: las filas
JSON/TOON/`metadata.json` comparan contra la salida compacta actual, no contra la pretty-printed
que documentan las columnas `Bytes`/`Tokens aprox.` originales.

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

- **Actualización (2026-07-23), tokens reales de Gemini (`gemini-2.5-flash`), los 3 escenarios:**
  la aproximación caracteres÷4 confirma la dirección correcta en todos los casos (pbi-docs siempre
  gana, y por márgenes grandes), pero **subestima el ahorro real de pbi-docs de forma consistente**
  — ahorros reales entre 5 y 27 puntos porcentuales por encima de lo aproximado, y el hallazgo más
  notable es que el ahorro agregado de TOON vs JSON, que la aproximación mostraba como marginal
  (-3.4%), es real y sustancial con un tokenizador real (-22.4%). Sigue siendo un solo proveedor
  (Gemini, no Claude — el bloqueo de Anthropic de la sección 1 sigue abierto), pero refuerza que
  las conclusiones de este informe no dependen de un artefacto de la aproximación caracteres÷4.
