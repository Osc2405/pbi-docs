# CLAUDE.md — pbi-docs: soporte PBIP/TMDL + mejoras de contexto para agentes

Este archivo es la fuente de verdad para las próximas fases de desarrollo de `pbi-docs`.
Léelo completo antes de proponer un plan. Trabajar siempre en **Plan Mode** antes de tocar código:
presentar el plan, esperar aprobación explícita, y solo entonces implementar por fases.

---

## Estado actual (actualizado 2026-07-15)

Las secciones 1 y 2 de este documento describían trabajo planeado que **ya está implementado y
probado** (161 tests, 0 dependencias externas). Se dejan las secciones originales abajo sin
reescribir — el razonamiento de diseño sigue siendo válido y útil — pero marcadas como
completadas para que una sesión futura no las re-planifique desde cero.

- **Sección 1 (soporte PBIP/TMDL): ✅ COMPLETADO.** `pbi_extractor/pbip_extractor.py`. Validado
  contra un export `.pbip` real (no solo el fixture sintético) — ver
  `docs/pbip_validation_report.md` para los 5 bugs encontrados y corregidos en el proceso.
- **Sección 2 (salida indexada + TOON): ✅ COMPLETADO.** `pbi_extractor/indexed_output.py`,
  `pbi_extractor/toon_encoder.py`. Medido empíricamente, no solo implementado — ver
  `docs/token_optimization_report.md` (TOON no es un ahorro uniforme, gana solo en tablas
  grandes/uniformes; el ahorro dominante viene de `index.json` + carga selectiva, no del formato).
- **Trabajo adicional no anticipado en este documento original**, construido sobre lo anterior:
  `pbi_extractor/resolver.py` (capa de consulta estructurada, JSON/TOON transparente), servidor
  MCP de solo lectura hecho a mano (`pbi_extractor/mcp_server.py`, sin dependencia del SDK `mcp`
  oficial para preservar cero-dependencias), Skills invocables desde Claude Code y GitHub Copilot
  (`.claude/skills/analyze-pbi-model/`, `.github/prompts/analyze-pbi-model.prompt.md`), y un
  experimento de precisión automatizado (`docs/precision_validation_report.md`) que valida que el
  contexto acotado no sacrifica exactitud de respuesta.
- **Documento de planeación estratégica activo:**
  `docs/Analisis_Posicionamiento_Comparativa_Plan_Futuro.md` — reemplaza al checklist original de
  esta sesión de Plan Mode como fuente de verdad del roadmap (secciones 3-4 de ese documento).
  Secciones 3 y 4 de este archivo (Graphify, Grafo diferido) siguen vigentes sin cambios.

### Actualización 2026-07-16 — Horizonte 1 cerrado, Resolver extendido, validación humana preparada

Todos los ítems de Horizonte 1 que quedaban pendientes se completaron esta sesión (ver
`docs/Analisis_Posicionamiento_Comparativa_Plan_Futuro.md` y `CHANGELOG.md` para el detalle
completo), 187 tests en verde:

- **`--index-format auto`**: selección de TOON/JSON por tabla (no más un flag global), umbral
  real confirmado en 7 filas (columnas+measures), no el "~10" aproximado que tenía el roadmap.
- **`index.json` documentado como spec abierta** en `README.md`.
- **Resolver extendido con dependencias/impact-analysis**: `get_measure_dependencies()` /
  `find_measure_usages()`, con soporte transitivo (BFS multi-salto, cycle-safe) además del modo de
  un salto original — expuesto en MCP y `--query` (`--dependencies`, `--usages`, `--transitive`).
  Sigue sin ser un grafo persistido; es resolución bajo demanda sobre `formatted_expression` vía
  regex, consistente con el alcance que la sección 4 de este archivo ya permite.
- **`files_test/Sales Sample.pbip`**: sample oficial de Microsoft (MIT) agregado como segundo
  modelo de prueba (11 tablas/29 measures/5 relaciones) — reveló y permitió corregir un bug real
  del parser TMDL (expresiones DAX delimitadas por backtick-fence se leían como el literal
  `` ``` ``, ver `CHANGELOG.md`).
- **`docs/human_validation_protocol.md`**: protocolo ejecutable para el experimento de la sección
  6 del análisis de posicionamiento (el "próximo paso crítico"). Está en curso — logística de
  reclutamiento de participantes, fuera del control de este repo.
- **`scripts/count_tokens.py`**: conteo real de tokens vía API de Anthropic, dev-only (mismo
  tratamiento que Graphify, sección 3). No corrido en este entorno por falta de
  `ANTHROPIC_API_KEY` — documentado como bloqueado en `docs/token_optimization_report.md`, no
  simulado.

**Decisión reafirmada, no nueva — capa de escritura/modificación de PBIP sigue diferida
(Horizonte 4 sin cambios).** Se evaluó explícitamente en esta sesión si convenía empezarla ahora
y la respuesta fue no, por las mismas razones que ya constaban en la sección 4: escribir TMDL de
vuelta con seguridad (preservar formato/comentarios/lineage tags, resolver merges/conflictos) es
sustancialmente más riesgoso que leer, es redundante con el Modeling MCP oficial de Microsoft, y
distrae del posicionamiento de "compilador de contexto" antes de tener resultados de la
validación humana en curso. Si se reconsidera, que sea por un caso de uso puntual y acotado
(ej. agregar una sola measure), no una capa de escritura general.

### Actualización 2026-07-18 — Fase 0 (validación de escala) del plan contexto/auditoría

Nuevo plan activo, orientado a posicionar `pbi-docs` como capa read-only de contexto pre-edición
y auditoría post-edición alrededor de flujos donde una IA modifica PBIP (nunca escribiendo TMDL).
Fase 0 (bloqueante, medir escala primero) completada esta sesión — ver
`docs/scale_validation_report.md` para el detalle completo:

- **No existe modelo PBIP público a escala enterprise** (8 repos revisados, todos convergen al
  mismo modelo de ~10-11 tablas que ya está en `files_test/`) — se generó un modelo sintético
  (`scripts/generate_synthetic_pbip.py`, dev-only, 60 tablas/288 measures/120 relaciones)
  explícitamente etiquetado como tal, no como sustituto de validación con datos reales.
- **`--index-format auto` pierde su valor diferencial a esta escala**: 60/60 tablas eligen TOON
  (todas superan el umbral de 7 filas ya documentado) — el modo `auto` solo importa en modelos
  con tablas de tamaño mixto.
- **El ahorro de tokens de `token_optimization_report.md` (validado en 7 tablas) se invierte a
  60 tablas** en los escenarios "tabla específica" y "deep-dive": el costo fijo de `index.json`
  crece con el número de tablas y termina pesando más que la tabla cruda que reemplaza. El
  escenario overview sigue ganando fuerte (ver reporte para las cifras exactas).
- **Hallazgo (ya corregido, sesión siguiente)**: `resolver.find_measure_usages(transitive=True)`
  releía el modelo completo desde disco en cada salto BFS. Fix aplicado en
  `pbi_extractor/resolver.py` (una sola lectura cacheada por invocación), verificado
  deterministamente por call-count, no por wall-clock. **Corrección importante**: al re-medir se
  encontró que `scripts/generate_synthetic_pbip.py` generaba nombres de measure duplicados entre
  tablas (imposible en un modelo Tabular real) que inflaban artificialmente el BFS — la cifra
  original de 1.6s mezclaba el bug del generador con el costo real de re-lectura. Generador
  corregido también. Ver `docs/scale_validation_report.md` sección 5 para el detalle completo de
  la corrección.
- Decisión de scope explícita: el modelo sintético **no** incluye RLS/perspectives/calculation
  groups (fuera de scope v1, sección 1 de este archivo) — no se amplió el parser en esta sesión.

**Actualización, misma sesión — Fase 1 completada + hallazgo de resolver resuelto.** `--diff`
ahora es content-aware (`pbi_extractor/diff.py` reescrito: `measures_modified`,
`columns_added/removed/modified`, `relationships_modified`, heurística semántico/cosmético en DAX
vía whitespace; identidad de relaciones cambiada a solo columnas conectadas). 11 tests nuevos en
`tests/test_diff.py`. Encima, se decidió resolver el hallazgo de rendimiento del resolver
(arriba) en vez de dejarlo como deuda — ver el bullet corregido arriba y
`docs/scale_validation_report.md` sección 5. Suite completa: 200 tests, todos en verde. Fases 2-3
(MCP como pre-check documentado, hook de CI/pre-commit) y el hallazgo #2 (inversión de costo fijo
de `index.json` a escala) quedan para una sesión futura.

---

### Actualización 2026-07-20 — Validación contra PBIP reales, bug del resolver, hallazgos de escala revisados

Dos hilos de trabajo en la misma sesión: (1) validación ad hoc del estado actual contra modelos
PBIP reales descargados por el usuario, y (2) cerrar los 2 hallazgos de escala que quedaron
pendientes el 2026-07-18.

**Validación contra PBIP reales (`file_test_2/`, gitignored — no son fixtures del repo).** Dos
modelos reales: "Corporate Spend" (11 tablas/15 measures) y "Adventure_Works" (11 tablas/0
measures — confirmado real en el TMDL fuente, no un bug). Pipeline completo, `--diff`,
`--index-format auto`, resolver/`--query` y la suite completa corrieron limpio, con una excepción:
se encontró y corrigió un bug real en `resolver._extract_references()` — clasificaba un `[Column]`
sin calificar (ej. `SUM([Value])` dentro de una measure de `Fact`, refiriéndose a `Fact[Value]`)
como si fuera una measure, en vez de una columna de la propia tabla. Ni `tests/fixtures/minimal_pbip/`
ni `files_test/Sales Sample.pbip` habían expuesto este caso — otra confirmación de que validar
contra datos reales encuentra cosas que los fixtures curados no (mismo patrón que el bug del
generador sintético del 2026-07-18). Corregido, con 2 tests unitarios nuevos contra
`_extract_references()` en `tests/test_resolver.py` (sin tocar el fixture compartido `minimal_pbip`,
que usan otros 3 archivos de test). Documentado en `CHANGELOG.md`. Commit `7b6073f`.

**Hallazgos de escala del 2026-07-18, revisados uno por uno** (`docs/scale_validation_report.md`
sección 5.1 tiene el detalle completo):

- **`--index-format auto` "pierde valor a escala" — cerrado, no era un defecto.** `_should_use_toon()`
  decide por tabla, no por modelo; que 60/60 tablas elijan TOON en un modelo donde todas superan
  el umbral es el resultado *correcto*, no un bug. Sin cambio de código — solo faltaba dejarlo
  documentado como cerrado en vez de "pendiente".
- **Inversión de costo fijo de `index.json` — causa raíz identificada y corregida parcialmente.**
  `resolver.get_table()` cargaba `index.json` completo antes de leer la tabla pedida, aunque el
  nombre de archivo es 100% determinístico (`_safe_filename(table_name)`). Fix: lectura directa de
  `tables/<name>.json` primero, `index.json` solo como fallback para el mensaje de error. Resultado
  medido en el mismo modelo sintético de 60 tablas: "tabla específica" pasa de 10.34x a 2.00x más
  grande que TMDL crudo — mejora real, pero no revierte a una victoria neta en este modelo sintético
  en particular (que no tiene `lineageTag`/`annotations` que limpiar, a diferencia de un export real).
  "Deep-dive completo" no se mueve con este fix (necesita genuinamente la lista completa de tablas,
  correcto que siga usando `index.json`) y queda como **hallazgo #3 nuevo, diagnosticado con datos
  reales, no implementado**: remover `indent=2` de `json.dump()` reduciría el total en 44.3%
  (2.48x → 1.38x sobre TMDL crudo) pero no cierra la brecha completa — decisión de diseño que afecta
  legibilidad humana de la salida en todos los modos, no solo a escala, así que queda fuera del
  alcance de esta sesión a propósito.

Suite completa: 203 tests, todos en verde.

---

### Actualización 2026-07-21 — Hallazgo #3 de escala (indent=2) implementado, cifra real medida

Cierra el hallazgo #3 que las actualizaciones de 2026-07-18/2026-07-20 dejaban documentado pero
sin implementar (`docs/scale_validation_report.md` sección 5.1: quitar `indent=2` de `json.dump()`
reduciría el tamaño de la salida indexada pero afecta legibilidad humana). Decisión tomada esta
sesión: la salida indexada (`index.json`, `tables/*.json`, `relationships.json`) pasa a ser
**compacta por defecto** (`_write_json()` en `pbi_extractor/indexed_output.py`, sin `indent`),
con un flag nuevo `--pretty` en `cli.py` que restaura `indent=2` para debug humano. Justificación:
el consumidor primario de estos archivos es `resolver.py`/`mcp_server.py`/un LLM, no un humano
leyendo JSON crudo — el artefacto legible para humanos (`model_documentation.md`) no se tocó.

Re-corrida completa de la metodología de la sección 5.1 sobre el mismo modelo sintético de 60
tablas/288 measures (`docs/scale_validation_report.md` sección 5.2, cifras reales, no proyectadas):
"tabla específica" (`Fact01` vía `get_table()`) pasa de 2.00x a **1.13x** el tamaño de TMDL crudo
(-43.5%); "deep-dive completo" pasa de 2.12x a **1.18x** (-44.3%, coincide casi exactamente con la
proyección de la sección 5.1). Combinado con el fix de `resolver.get_table()` del 2026-07-20,
"tabla específica" queda en paridad práctica con el TMDL crudo. "Deep-dive completo" mejora fuerte
pero sigue sin ser una victoria neta en este modelo sintético en particular — el generador produce
TMDL limpio, sin `lineageTag`/`annotations` que un export real de Power BI Desktop sí tiene y que
`pbi-docs` descarta; no generalizar a "siempre gana" sin medir contra un modelo real grande, que
sigue sin existir públicamente (ver sección 1 del mismo informe).

El conteo real de tokens vía API de Anthropic sigue bloqueado por falta de `ANTHROPIC_API_KEY` —
las cifras de esta sección son bytes medidos directamente, no tokens reales.

---

### Actualización 2026-07-23 — Conteo real de tokens vía Gemini (segundo proveedor, no resuelve bloqueo Anthropic)

`scripts/count_tokens.py` (dev-only, mismo tratamiento que Graphify — no es dependencia del
paquete) ahora soporta `--provider anthropic|gemini` (antes solo Anthropic, sin flag). Se agregó
porque el usuario consiguió una API key de Gemini (capa gratuita) pero sigue sin una de Anthropic.
`_iter_files()` y la lógica de combinar archivos no cambiaron — solo se agregó despacho por
proveedor (`PROVIDERS` dict, funciones `_count_anthropic`/`_count_gemini` con lazy import cada
una). Requiere `pip install google-genai` y `GEMINI_API_KEY`; usa el SDK unificado `google-genai`
(no el `google-generativeai` antiguo), método `client.models.count_tokens()` — mismo tipo de
endpoint gratuito (sin costo de generación) que `count_tokens` de Anthropic.

Se actualizó `docs/token_optimization_report.md` (modelo Supply Chain Sample, 7 tablas) con una
columna nueva para tokens reales de Gemini en las 3 tablas de escenario — los 3 escenarios
completos, con el usuario corriendo los comandos con su key:
- **Escenario 1** (overview): 10,590 / 47,296 / 830 tokens — ahorro real 92.2% (vs 91.0% aprox.).
- **Escenario 2** (tabla `Backorder Percentage`, la más grande): 2,310 raw / 797 JSON / 527 TOON —
  ahorro real JSON 65.5%, TOON 77.2% (vs 35.4%/46.0% aprox.); **TOON vs JSON real: -33.9%** (vs
  -16.5% aprox.) — con tokenizador real, TOON gana el doble de lo que sugería chars÷4 en esta tabla.
- **Escenario 3** (deep-dive completo): 10,590 raw / 2,339 JSON / 1,815 TOON / 4,141
  `metadata.json` — ahorro real JSON 77.9%, TOON 82.9% (vs 52.7%/54.3% aprox.). **Hallazgo
  principal de la sesión: TOON vs JSON agregado real es -22.4% (vs -3.4% aprox.)** — la
  aproximación caracteres÷4 hacía ver el ahorro agregado de TOON como marginal y concentrado solo
  en la tabla grande; con tokenizador real, TOON gana de forma consistente también en agregado.
  Sección 5 del informe actualizada con este matiz (no contradice la sección 4 — TOON tabla por
  tabla en tablas chicas sigue midiéndose en aproximación, no se remidió).

**Hallazgo de método, no solo tokenizador:** las columnas `Bytes`/`Tokens aprox.` de JSON/TOON en
este informe se midieron el 2026-07-15, antes de que `_write_json()` pasara a compacto por
defecto (hallazgo #3 de `docs/scale_validation_report.md`, resuelto 2026-07-20). El `output/`
regenerado para esta corrida ya es compacto (`separators=(",",":")`, sin `indent=2`), así que
parte de la caída real-vs-aproximación en las filas JSON/TOON es el cambio de formato, no solo
diferencia de tokenizador — documentado explícitamente en el informe para no confundir ambos
efectos. Aparte, el `Bytes` que imprime el script también normaliza CRLF→LF al leer en modo
texto, por lo que tampoco coincide byte a byte con `os.path.getsize` del disco — otra diferencia
de método, no un bug.

**No se tocó** `docs/scale_validation_report.md` (modelo sintético de 60 tablas) — queda fuera de
alcance de esta sesión.

**Esto no resuelve el bloqueo de Anthropic** documentado desde 2026-07-16 — sigue bloqueado, sin
`ANTHROPIC_API_KEY`. El tokenizador de Gemini no es el de Claude; esto es un segundo punto de dato
real de un proveedor distinto, útil para verificar la heurística caracteres÷4 en general, y un
paso parcial hacia cerrar la limitación de "un solo proveedor" de
`docs/precision_validation_report.md` sección 6 (que es sobre calidad de respuesta, no sobre
conteo de tokens — sigue sin validar ahí).

---

### Actualización 2026-07-23 — Calidad de respuesta con Gemini real (function calling, Sales Sample)

Cierra la parte de "calidad de respuesta" de la limitación de "un solo proveedor" que dejaba
abierta el bullet anterior. Nuevo experimento: `scripts/answer_quality_gemini.py` (dev-only,
mismo tratamiento Graphify) corre 20 preguntas de negocio contra `Sales Sample.pbip` (11
tablas/29 measures) bajo 3 condiciones — A: TMDL crudo, B: JSON de pbi-docs completo, C: Gemini
elige por su cuenta qué funciones de `resolver.py` llamar (Automatic Function Calling del SDK
`google-genai`, no un `--query` fijo preseleccionado). Preguntas reusadas de
`docs/human_validation_protocol.md` sección 5, copia estructurada en
`scripts/fixtures/sales_sample_questions.json`.

**Resultado real, calificado a mano** (`scripts/fixtures/sales_sample_gemini_results_validados.csv`,
detalle en `docs/answer_quality_gemini_report.md`): precisión A 70% / B 90% / C 95%; tokens
totales A 376,159 / B 202,674 / C 37,993 (ahorro C vs A: 89.9%). **Condición C gana en precisión Y
en costo a la vez** — no hay trade-off entre barato y correcto en este modelo, que es la respuesta
directa a por qué vale la pena la capa de consulta dirigida (MCP/resolver) sobre un dump completo.

Dos hallazgos de datos en el camino, ambos verificados contra el código/modelo real, no solo
inferidos de las respuestas:
- **Gap real de producto, documentado no arreglado por decisión explícita:** `partition_count` se
  calcula en `processor.py:228` pero `indexed_output.py` nunca lo copia a
  `index.json`/`tables/*.json` — invisible para `resolver.py` y cualquier tool MCP. Falló en las
  3 condiciones (en C, Gemini hizo 12 tool calls sin éxito buscándolo). Fix queda para sesión
  aparte — toca el formato de salida de todos los modelos.
- **Corrección de referencia:** la pregunta 17 (`docs/human_validation_protocol.md` sección 5)
  tenía como respuesta "2" measures con "YTD" en el nombre; las 3 condiciones encontraron
  independientemente una tercera (`Value (ytd)`), confirmada en vivo con
  `resolver.search_measures()`. Corregido a "3" en el fixture y en la tabla original — la
  referencia estaba incompleta, no los agentes.

**Notas de implementación** (por si se reusa el patrón en otro script con Gemini): el modelo por
defecto tuvo que cambiar 3 veces durante la sesión por errores reales de la API —
`gemini-2.5-flash` (404 para cuentas nuevas en `generateContent`, aunque sigue funcionando para
`count_tokens`) → `gemini-flash-latest` (resuelve a `gemini-3.6-flash`, cuota gratis de solo 20
req/día) → `gemini-2.5-flash-lite` (mismo 404) → `gemini-flash-lite-latest` (funcionó). El límite
real de RPM en la capa gratuita resultó ser 5, no una suposición de diseño — pacing y backoff
exponencial ajustados con ese dato real, parseando el `retryDelay` que la propia API devuelve en
el 429 en vez de adivinar el tiempo de espera.

---

### Actualización 2026-07-23 — Fix: `partition_count` ahora expuesto en `index.json`/`tables/*.json`

Cierra el gap documentado en la sección anterior (`docs/answer_quality_gemini_report.md` sección
3.1, pregunta 15 fallida en las 3 condiciones). `pbi_extractor/indexed_output.py`
(`_table_entry_json`, `_table_entry_toon`, `build_index`) y `pbi_extractor/resolver.py`
(`get_table`) ahora propagan `partition_count` desde `cleaned_metadata` hasta
`index.json`/`tables/*.json`, vía `.get("partition_count", 0)` para no romper fixtures/dicts
construidos a mano sin el campo. `resolver.list_tables()` no necesitó cambios — no filtra campos,
solo filas. Descripción del tool MCP `list_tables` actualizada para mencionarlo. Campo aditivo, no
requiere bump de `index.json`'s `"version"` (`docs/index-json-spec.md`). 4 tests nuevos en
`tests/test_indexed_output.py`/`tests/test_resolver.py`, incluida paridad JSON/TOON específica del
campo — 226 tests, todos en verde.

**Verificado end-to-end contra el modelo real del experimento**, no solo con tests unitarios:
regenerando `output/Sales Sample/` y corriendo `pbi-docs --query ... --list-tables`, las tablas
`Smart Calcs` y `Time Intelligence` aparecen con `partition_count: 0` — exactamente la respuesta
de referencia de la pregunta 15 que fallaba antes del fix.

---

### Actualización 2026-07-24 — Hook de pre-commit (referencia) + 4 hallazgos P1 de auditoría general

Sesión originada en una auditoría general de arquitectura/deuda técnica/cobertura de tests
(`Pruebas/auditoria_general_2026-07-24.md`, nota local gitignoreada — no versionada, igual
tratamiento que otras notas de auditoría previas). De ahí salieron una feature nueva y varios
fixes, todos con 283 tests en verde al cierre:

- **Hook de pre-commit de referencia** (`githooks/`, no es parte del paquete instalable — plantilla
  para repos que versionan modelos `.pbip`/`.pbit`, ver `docs/pre_commit_hook.md`). Bloquea un
  commit que borra o modifica una measure de la que otra measure todavía depende, usando
  `pbi-docs --diff --diff-impact --transitive`. Compara el contenido *staged* contra `HEAD` (no el
  working tree — respeta un `git add` parcial) materializando ambas versiones vía `git
  archive`/`git write-tree` en directorios temporales, porque `--diff` toma paths de filesystem,
  no refs de git. Falla abierto (advierte, deja pasar el commit) si `pbi-docs` no está instalado o
  falla inesperadamente. Instalación: `git config core.hooksPath githooks`. 17 tests en
  `tests/test_githooks_pbip_diff.py`, incluyendo casos end-to-end reales (repo git temporal,
  subprocess real de `pbi-docs`).
- **Bug real encontrado construyendo el hook**: `--diff --diff-impact` corrompía silenciosamente
  su propio campo `used_by` cuando `a_path` y `b_path` compartían el mismo nombre de modelo —
  exactamente el caso "mismo proyecto, dos checkouts" que el hook ejercita. La segunda llamada a
  `process_file()` sobreescribía el output de la primera antes de que `diff_impact()` la leyera de
  vuelta, dando `used_by` vacío sin importar dependencias reales — una respuesta silenciosamente
  incorrecta, no un crash, así que la suite existente no lo detectaba. Corregido en `cli.py`:
  el output de `b` va a un subdirectorio `_diff_b` cuando los nombres colisionan.
- **4 hallazgos P1 de la misma auditoría**, todos corregidos: (1) un archivo de tabla `.tmdl`
  corrupto en `.pbip` abortaba todo el modelo en vez de solo advertir y saltarlo, como ya hacía
  `.pbit` — alineado; (2) la forma "flat" de una measure estaba duplicada en 3 lugares (mismo
  patrón que causó el bug de `partition_count` de la sección anterior) — centralizada en
  `flatten_measure()`, usada ahora también por `resolver.get_table()`; (3) `resolver._load_json()`
  ahora cachea por (path resuelto, mtime), ya que `mcp_server.py` ata un proceso de larga vida a un
  directorio de modelo y releía los mismos JSON en cada llamada a tool, sin reuso entre llamadas
  (el fix de rendimiento del 2026-07-18 solo deduplicaba lecturas *dentro* de un mismo BFS); (4)
  4 tests nuevos de hardening del parser TMDL (indentación mixta tabs/espacios, DAX anidado
  profundo) — pasaron sin cambios de código, cerrando un gap de cobertura sin bug real detrás.
- **Cobertura de tests que no existía**: `extractor.py` (ruta `.pbit`) tenía cero tests y
  `cli.py --batch` no tenía ninguno — hallazgos P0 de la misma auditoría. Se agregaron
  `tests/test_extractor.py` (29 tests, fixtures de zip en memoria) y `tests/test_cli_batch.py`
  (3 tests). Escribir los tests de extractor expuso un bug real: `clean_json_text()` usaba
  `r"\\1"` (backslash literal + "1") en vez de `r"\1"` (backreference) en sus regex de
  comentarios/comas colgantes — corrompía en vez de limpiar el JSON cuando el `DataModelSchema`
  traía comentarios o trailing commas. Corregido.

---

### Actualización 2026-07-28 — Primer release publicado en PyPI (`v1.0.0`), validado en venv limpio

Cierra el ciclo de publicación que quedaba a medias desde antes de la sesión 2026-07-16 (ver
`Pruebas/PENDIENTES_PUBLICACION_SEGURA.md`, nota local gitignoreada, para el detalle completo del
checklist previo — branch protection, trusted publisher OIDC en pypi.org/test.pypi.org y la
validación en TestPyPI con `1.0.0rc1`/`rc2` ya se habían hecho en sesiones anteriores).

- **`CHANGELOG.md`**: contenido de `[Unreleased]` (Gemini scripts, hook de pre-commit, 4 fixes
  reales de la auditoría P1, `partition_count`) fusionado dentro de `[1.0.0]`, fecha del header
  actualizada a 2026-07-28 (fecha real de publicación) — decisión explícita del usuario de no
  bumpear versión, ya que a ojos de PyPI es la primera publicación de todos modos.
- **`main` está protegida** (requiere PR + 6 checks) — descubierto al intentar `git push` directo.
  Los 11 commits pendientes (incluida la fusión del CHANGELOG y esta misma entrada) se subieron
  vía rama `release/v1.0.0-prep` + PR, no push directo. El PR también absorbió un commit que ya
  estaba en `origin/main` y no en local (`fix: skip Sales Sample resolver tests when fixture
  absent`, mergeado sin conflictos).
- **`v1.0.0` publicado en PyPI real** (`https://pypi.org/project/pbi-docs/`) vía el GitHub Release
  + `publish.yml` (trusted publisher OIDC, ya configurado por el usuario en sesiones previas).
- **Validación funcional en venv limpio** (no solo `pip install`, sino uso real): `pip install
  pbi-docs` sin arrastrar dependencias, entry point `pbi-docs --help` correcto, extracción sobre
  `tests/fixtures/minimal_pbip` genera los 7 archivos esperados, `--query` (`--list-tables`,
  `--table`, `--search-measures`) responde bien, `--mcp-serve` responde protocolo JSON-RPC 2.0
  completo (`initialize` + `tools/call`) y cierra limpio en EOF. Único hallazgo, cosmético y no
  bloqueante: `--search-measures ""` (string vacío) cae en el error de "requiere uno de..." por un
  check truthy (`if args.search_measures:`) en vez de `is not None` — nadie busca con query vacío
  en la práctica, no se corrigió.
- **Documentación sincronizada al estado publicado**: `README.md` (badge de PyPI, `pip install
  pbi-docs` como instalación primaria, `git clone`/`pip install -e .` relegado a desarrollo),
  `docs/pre_commit_hook.md` y `githooks/check_pbip_diff_impact.py` (ya no dicen "no publicado
  todavía"), `docs/Analisis_Posicionamiento_Comparativa_Plan_Futuro.md` (instalación actualizada).
  Notas locales gitignoreadas (`Pruebas/PENDIENTES_PUBLICACION_SEGURA.md`,
  `Pruebas/powerbi_devops_integracion_pbi-docs.md`) también actualizadas — tenían veredictos
  desactualizados sobre PyPI y el hook de pre-commit que ya no aplicaban.

Suite completa: 283 tests, todos en verde (sin cambios de código en esta sesión, solo
documentación/release).

---

### Actualización 2026-07-31 — `--diff-impact` extendido a columnas (Fase 2 del roadmap)

Cierra la Fase 2 que quedó documentada (no ejecutada) en la sesión de reconciliación
brainstorm/`NEXT_STEPS.md` del 2026-07-30: `--diff-impact` cubría roturas measure→measure pero no
detectaba que un commit borrara o modificara una **columna** que una measure sigue referenciando
en su DAX — ni `diff_impact()` ni el pre-commit hook lo reportaban.

- **`resolver.find_column_usages(model_dir, table_name, column_name, *, transitive=False)`**
  nueva — mirror de `find_measure_usages()`, reusando `_extract_references()` (ya distinguía
  columnas de measures) y `_all_measures()` (una sola lectura cacheada). El caso `transitive=True`
  reusa `find_measure_usages(transitive=True)` sobre cada referenciador directo en vez de
  reimplementar el BFS — un referenciador directo de la columna puede a su vez tener sus propios
  callers measure→measure, y ese camino ya estaba resuelto. Sin `find_column_dependencies()`
  simétrico: una columna no tiene expresión DAX propia en este modelo (calculated columns no se
  capturan con `expression`), así que "de qué depende una columna" no aplica — decisión explícita,
  no un gap olvidado.
- **`diff.diff_impact()`** ahora también devuelve `columns_removed_impact`/
  `columns_modified_impact`, mismo criterio old-model/new-model que measures (removed → modelo
  viejo, modified → modelo nuevo). `cli.py` (`--diff --diff-impact`) y `diff.diff_with_impact()`
  no necesitaron cambios — ambos ya eran genéricos sobre las claves que devuelve `diff_impact()`.
- **Tool MCP nuevo `find_column_usages`** (wrapper delgado, mismo patrón que cada tool existente
  sobre una función de `resolver.py`); descripción de `diff_impact` actualizada para mencionar
  impacto de columnas.
- **`githooks/check_pbip_diff_impact.py`** extendido: `_has_breaking_impact()`/
  `_format_impact_report()` ahora también miran `columns_removed_impact`/
  `columns_modified_impact` — antes de este fix, el hook dejaba pasar sin advertencia un commit
  que borraba una columna todavía referenciada por una measure (bug de cobertura, no de lógica:
  `diff_impact()` ya reportaba el impacto, el hook simplemente no lo miraba).
- Documentación sincronizada: `README.md` (`--diff-impact`), `docs/use-cases.md` (10 tools MCP,
  no 9), `docs/pre_commit_hook.md` (alcance del hook menciona columnas).
- 16 tests nuevos (`tests/test_resolver.py`, `tests/test_diff.py`, `tests/test_mcp_server.py`,
  `tests/test_githooks_pbip_diff.py`, incluido un caso end-to-end real: commit que borra
  `Sales[SalesAmount]` sin tocar la measure `Total Sales` que la sigue referenciando, bloqueado).

Suite completa: 299 tests, todos en verde.

---

### Actualización 2026-07-31 — Fabric (documentado) + diagrama Mermaid en `model_documentation.md`

Cierra la Fase 3 del roadmap ("Fabric + Mermaid", `Pruebas/brainstorm_features_2026-07-29.md` §5
punto 3). Dos fichas de naturaleza distinta, no confundir su estado:

- **Fabric — documentación de compatibilidad esperada, NO validación empírica.** Se preguntó
  explícitamente al usuario (AskUserQuestion) si había acceso a un export real de un modelo
  semántico de Microsoft Fabric en este entorno — respuesta: no. La ficha del brainstorm ya la
  describía como "validación, no código nuevo", así que sin export real el alcance se redujo a
  `docs/fabric_compatibility.md`: documenta, citando fuentes públicas de Microsoft Learn
  verificadas por WebSearch esta sesión (no de memoria), que TMDL es el formato compartido entre
  PBIP y los semantic models de Fabric, y que `pbip_extractor.py` parsea la gramática TMDL general
  sin depender de artefactos específicos de Power BI Desktop — pero el documento queda marcado
  explícitamente en estado 🟡 ("compatibilidad esperada, no validada"), nunca ✅, mismo tratamiento
  que ya reciben `docs/human_validation_protocol.md` y el conteo real de tokens vía Anthropic. Si
  aparece un export real de Fabric en una sesión futura, re-correr esto empíricamente (mismo
  formato que `docs/pbip_validation_report.md`) y recién ahí subir el estado.
- **Diagrama Mermaid — código real, con tests.** `pbi_extractor/documentation.py`:
  `generate_mermaid_er(cleaned_metadata)` (+ `_sanitize_mermaid_id()`) genera un bloque
  ```` ```mermaid ```` `erDiagram` (tablas + relaciones + cardinalidad crow's-foot, línea sólida/
  punteada para relación activa/inactiva) reusando `relationships.json`/`cleaned_metadata` sin
  nueva extracción — tablas aisladas (sin relaciones) se omiten a propósito. Insertado en
  `generate_markdown()` dentro de la sección `## Relationships`/`## Relaciones`, antes de la tabla
  existente. Nueva clave i18n `diagram_isolated_note` (en/es). Verificado no solo con tests sino
  generando `model_documentation.md` real sobre `tests/fixtures/minimal_pbip` y confirmando que el
  bloque Mermaid resultante es sintácticamente válido (crow's-foot correcto, IDs saneados sin
  espacios, línea punteada en la relación inactiva del fixture).
- 9 tests nuevos en `tests/test_processor_and_context.py` (no existe `test_documentation.py` — los
  tests de `generate_markdown()` ya vivían en ese archivo, se mantuvo el patrón).

Suite completa: 308 tests, todos en verde.

---

### Actualización 2026-07-31 — Cerrado `.mcp.json` → `Sales Sample` (Fase 4), ledger de deuda técnica

Cierra la Fase 4 del roadmap: `.mcp.json` (raíz del repo) apuntaba a `output/Supply Chain Sample`
desde antes de decidir (sesión 2026-07-18) que debía apuntar a `Sales Sample` — pendiente de
ejecución hasta ahora.

- `output/Sales Sample` regenerado con el pipeline actual (antes era del 2026-07-23, previo a
  `--diff-impact` a columnas y al diagrama Mermaid) — confirmado que `model_documentation.md`
  incluye el bloque ` ```mermaid ` nuevo.
- `.mcp.json` actualizado a `output/Sales Sample`.
- **Smoke test real** (no solo el harness sintético de `tests/test_mcp_server.py`): handshake
  JSON-RPC manual (`initialize` → `tools/list` → `tools/call list_tables`) contra el directorio
  real que `.mcp.json` ahora usa — confirmó 10 tools (incluye `find_column_usages`) y las 11
  tablas esperadas de `Sales Sample`.
- **Hallazgo de la misma pasada, corregido**: `docs/use-cases.md` (sección MCP server) tenía dos
  referencias desactualizadas — `Supply Chain Sample` como fixture de demo, y "9 tools" (quedó
  desactualizado cuando se agregó `find_column_usages` en la Fase 2, un miss de esa sesión).
  Ambas corregidas.
- **Nuevo, a partir de esta sesión**: `Pruebas/deuda_tecnica_por_etapa.md` — ledger acumulativo
  (gitignored) con la deuda técnica pendiente/diferida de cada etapa del roadmap, retroactivo a
  las Fases 1-3 más esta. Instrucción explícita del usuario: cada etapa futura agrega su propia
  sección ahí, sin reescribir las anteriores.

Suite completa: 308 tests, todos en verde (sin cambios de código de producción en esta sesión —
solo `.mcp.json`, documentación, y regeneración de `output/`).

---

### Actualización 2026-07-31 — `--export-graph` (JSON/GraphML) + JSON Schema formal para `index.json` (Fase 5)

Cierra la Fase 5 del roadmap, la última de las fichas "casi gratis" agrupadas en el brainstorm.

- **`pbi_extractor/graph_export.py`** (nuevo módulo): `build_graph(model_dir)` proyecta
  `resolver.list_tables()`/`get_relationships()` a `{"nodes": [...], "edges": [...]}` — todas las
  tablas son nodos, incluidas las aisladas (a diferencia del diagrama Mermaid, que las omite por
  legibilidad; acá el consumidor es una herramienta externa). `to_graphml(graph)` serializa a XML
  GraphML con solo la librería estándar (`xml.sax.saxutils.escape`/`quoteattr`, sin lxml) —
  `categories` (lista en JSON) se aplana a string separado por comas en GraphML, único formato sin
  tipo escalar de lista; diferencia documentada, no un bug.
- **CLI**: `--export-graph [json|graphml]` como flag de modo `--query` (mismo patrón que
  `--dependencies`/`--usages`), default `json`. El caso `graphml` retorna temprano imprimiendo XML
  crudo en vez de pasar por el `print(json.dumps(...))` genérico — único caso especial en
  `_run_query()`.
- **Fuera de alcance, decisión explícita:** no se expone como tool MCP — un agente que ya tiene
  `list_tables`/`get_relationships` puede reconstruir la misma información sin un blob GraphML/XML
  en el contexto (mismo razonamiento de `CLAUDE.md` sección 4 sobre el grafo liviano).
- **`docs/index.schema.json`** (nuevo): JSON Schema formal (draft 2020-12) para `index.json`,
  formalizando la prosa de `docs/index-json-spec.md` (que gana un puntero al schema, sin
  reescribirse). Cubre solo `index.json` — `tables/*.json`/`relationships.json` varían de forma
  según TOON/JSON y quedan fuera de este schema.
- **`jsonschema` agregado como dependencia dev-only** (`pyproject.toml` extras `dev`, decisión
  confirmada con el usuario vía AskUserQuestion) — el paquete publicado sigue con cero
  dependencias; solo se importa dentro de tests nuevos en `tests/test_indexed_output.py`, que
  validan `build_index()` real (json/toon/auto) contra el schema formal.
- **Verificación manual real** (no solo tests): `pbi-docs --query "output/Sales Sample"
  --export-graph`/`--export-graph graphml` confirmó 11 nodos/5 aristas en ambos formatos, y que el
  XML GraphML parsea sin error (`xml.etree.ElementTree`).
- 13 tests nuevos (`tests/test_graph_export.py`, 3 tests de schema en `test_indexed_output.py`).

Suite completa: 321 tests, todos en verde.

---

## 0. Contexto del proyecto (no re-investigar, ya validado)

`pbi-docs` es un extractor y documentador de modelos de Power BI, 100% Python, cero dependencias
externas. Hoy solo soporta `.pbit` (ZIP con un JSON `DataModelSchema` en formato TMSL). Pipeline actual:

```
extractor.py       → abre el .pbit (zipfile), localiza y parsea DataModelSchema (JSON/TMSL)
processor.py        → normaliza a `cleaned_metadata` (tablas, columnas, measures, relaciones)
categorizer.py       → clasifica tablas/columnas/measures (revenue, cost, margin, temporal...)
formatters.py        → limpia y formatea DAX con indentación jerárquica (simple/medium/complex)
documentation.py     → genera model_documentation.md y agent_context.json (top-20 measures)
jsonl_generator.py   → genera model_context.jsonl (una entrada por tabla/measure/relación)
diff.py               → compara dos modelos procesados
i18n.py                → traducciones en/es
cli.py                  → argparse: --input/-i, --output/-o, --batch, --diff, --lang, --verbose
```

`process_file()` en `cli.py` es el orquestador único: extrae → procesa → escribe 4 archivos
(`metadata.json`, `model_documentation.md`, `agent_context.json`, `model_context.jsonl`) en
`output/<nombre>.pbit/`.

**Decisión de arquitectura ya tomada** (no reabrir el debate, solo ejecutar): el modelo interno
`cleaned_metadata` (dict con `tables`, `relationships`, `summary`) se **mantiene como contrato
estable**. Los cambios de esta fase son (a) un nuevo origen de entrada (PBIP/TMDL en vez de
PBIT/TMSL) que produce el mismo `cleaned_metadata`, y (b) cambios en cómo se serializa la salida.
No se reescribe `processor.py`, `formatters.py`, `categorizer.py`, `i18n.py` salvo que el diseño
de TMDL fuerce un cambio puntual y justificado.

---

## 1. Feature obligatoria: soporte `.pbip` / TMDL

### Por qué es obligatoria (contexto de mercado, no opinable)
Power BI Service usa PBIR por defecto desde enero–febrero 2026; Desktop desde mayo 2026; GA de
PBIR (retiro de legacy) esperada Q3 2026. Cualquier proyecto Power BI nuevo en 2026 se guarda como
PBIP. `.pbit`/`.pbix` siguen soportados indefinidamente pero dejan de ser el estándar de facto.

### Estructura de entrada a soportar
```
MyProject/
├── MyProject.pbip                        # JSON pointer, apunta a .Report/
├── MyProject.Report/
│   ├── definition.pbir
│   └── definition/
│       ├── report.json
│       └── pages/...                     # NO es el foco de esta fase (ver alcance)
└── MyProject.SemanticModel/
    ├── definition.pbism                  # entry point del modelo (JSON, NO .tmdl)
    └── definition/
        ├── database.tmdl
        ├── model.tmdl
        ├── relationships.tmdl            # puede variar de nombre/ubicación según versión
        └── tables/
            ├── TableA.tmdl
            ├── TableB.tmdl
            └── ...
```

Puntos de diseño que el plan debe resolver explícitamente:
- **Punto de entrada del CLI**: el usuario debe poder pasar la carpeta raíz del proyecto, el
  archivo `.pbip`, o directamente la carpeta `.SemanticModel/`. Definir prioridad y validación
  para cada caso (con mensajes de error claros, siguiendo el estilo actual de `extractor.py`).
- **Parser TMDL**: es indentación por **tabs** (no espacios — documentado como error común),
  sintaxis tipo YAML pero con reglas propias (definición de tabla, columnas, measures con
  `expression`, jerarquía por indentación, lineage tags/GUIDs que deben preservarse o ignorarse
  con seguridad). Diseñar como parser dedicado, no reutilizar regex de JSON.
- **Mapeo TMDL → `cleaned_metadata`**: cada archivo `.tmdl` de tabla debe producir la misma forma
  de `table_data` que hoy produce `processor.py` desde TMSL (columns, measures, is_hidden,
  partition_count, etc.). Confirmar campo por campo qué existe en TMDL y qué no, y documentar
  gaps con un warning (mismo patrón que los `try/except` + `print(Warning: ...)` que ya usa
  `processor.py`).
- **Relaciones**: en TMDL suelen vivir en `model.tmdl` o archivo separado, no por tabla — resolver
  bien el fan-out a la estructura plana de `relationships` que espera `processor.py`.
- **Coexistencia con `.pbit`**: `extractor.py` actual no se toca. Se agrega un módulo nuevo
  (nombre sugerido: `pbip_extractor.py` o `tmdl_extractor.py`) con su propia jerarquía de
  excepciones espejo (`PBIPExtractionError`, etc., heredando o siguiendo el mismo patrón que
  `PBITExtractionError`). `cli.py` debe detectar automáticamente el tipo de entrada (extensión
  `.pbit` vs. `.pbip` vs. carpeta) y despachar al extractor correcto.
- **`--batch` y `--diff`**: deben seguir funcionando mezclando o no tipos de entrada. Validar
  explícitamente en el plan cómo se comporta `--diff modelo.pbit modelo.pbip` (¿se permite
  comparar formatos distintos? probablemente sí, dado que ambos convergen a `cleaned_metadata`).

### Alcance explícito de esta fase (para no expandir sin control)
- **Dentro de alcance**: parseo completo del `.SemanticModel` (TMDL) hacia `cleaned_metadata`.
- **Fuera de alcance por ahora**: parsear el `.Report/` (PBIR) — visuales, páginas, bookmarks.
  Es un problema distinto (documentar el modelo de datos vs. documentar el reporte visual). Si
  surge como necesidad futura, es una fase separada. Dejarlo anotado en el plan como "no
  implementado en esta fase" para que quede explícito y no se asuma cobertura que no existe.

### Tests requeridos
- Fixtures TMDL de ejemplo (mínimo: un modelo simple con 2-3 tablas, measures con DAX anidado,
  relaciones activas/inactivas, alguna tabla oculta) — generarlos a mano si no hay archivos reales
  de muestra disponibles en el entorno de desarrollo.
- Test de paridad: mismo modelo exportado como `.pbit` y como `.pbip` debe producir
  `cleaned_metadata` equivalente (mismas tablas, measures, categorías, conteos en `summary`).
- Tests de error: carpeta TMDL corrupta/incompleta, `.tmdl` con indentación mixta (tabs+espacios),
  archivo `.pbip` que apunta a una carpeta inexistente.

---

## 2. Salida en múltiples archivos indexados (prioridad sobre TOON)

Objetivo: que un agente pueda consultar un modelo grande sin cargar `agent_context.json`/
`model_context.jsonl` completos.

### Diseño propuesto (a validar/ajustar en el plan)
```
output/<modelo>/
├── index.json                 # NUEVO: resumen liviano + puntero a cada archivo de detalle
├── metadata.json               # se mantiene igual (compatibilidad)
├── model_documentation.md      # se mantiene igual
├── tables/
│   ├── <TableA>.json           # detalle completo de una tabla (columnas + measures + DAX)
│   ├── <TableB>.json
│   └── ...
├── relationships.json          # todas las relaciones en un solo archivo (suele ser pequeño)
└── model_context.jsonl         # se mantiene, es el formato de compatibilidad con RAG existente
```

`index.json` debe contener, por tabla: nombre, conteo de columnas/measures, categorías presentes,
y la ruta relativa a su archivo de detalle — lo mínimo para que un agente decida qué cargar sin
leer nada más pesado primero.

Este cambio es **aditivo**: no romper `agent_context.json` actual (algún consumidor externo puede
depender de él). Se agrega como salida nueva, no como reemplazo, salvo decisión explícita en
Plan Mode de deprecar algo.

### Formato de serialización (TOON) — alcance acotado, no total
No convertir todo el output a TOON. Evidencia: TOON solo gana tokens en arrays uniformes; en
estructuras anidadas/no uniformes (como una expresión DAX formateada jerárquicamente) puede
empatar o perder contra JSON compacto.

Aplicar TOON (o CSV si el caso es puramente tabular) **únicamente** a:
- Listado de columnas por tabla (`name`, `data_type`, `category`, `is_hidden`) — alto grado de
  uniformidad.
- Listado de relaciones (`from_table`, `from_column`, `to_table`, `to_column`, `cardinality`,
  `cross_filtering`, `is_active`) — alto grado de uniformidad.
- Listado plano de measures **sin** el cuerpo DAX (name, table, category, complexity,
  format_string) — para vistas de "qué measures existen" sin pagar el costo de cargar todas las
  expresiones.

No aplicar TOON a: expresiones DAX formateadas (`formatted_expression`), `sample_prompts`,
cualquier campo de texto libre o de profundidad variable.

Esto debe ser una **opción**, no el comportamiento por defecto que rompa lo existente — evaluar
flag de CLI (p.ej. `--index-format json|toon`) o generar ambos y que el índice declare cuál usa
cada archivo.

### Tests requeridos
- Verificar que `index.json` referencia correctamente cada archivo de detalle generado.
- Test de "no ruptura": `agent_context.json` y `model_context.jsonl` siguen generándose igual
  que antes de este cambio (snapshot test o comparación campo a campo).
- Si se implementa TOON: test de round-trip (TOON → parseado de vuelta → mismo dict) para las
  secciones donde se aplique.

---

## 3. Graphify — herramienta de apoyo al desarrollo (NO es una dependencia del paquete)

No forma parte del código de `pbi-docs`. Es una herramienta externa (`safishamsi/graphify`) que
se puede correr localmente durante el desarrollo para navegar cómo se conectan los módulos del
repo mientras se implementan las fases 1 y 2, especialmente útil para no romper dependencias
entre `processor.py` y los nuevos extractores.

**No incluir en `pyproject.toml`, `requirements-dev.txt` ni en ningún flujo de CI.** Es opcional
y de uso personal del desarrollador, no un requisito del proyecto. Mencionarlo aquí solo para que
quede registrado que fue evaluado y descartado como dependencia — si en el futuro se reconsidera,
debe ser una decisión explícita y nueva, no heredada de esta nota.

---

## 4. Grafo para el resultado final — diferido, alcance redefinido

GraphRAG completo (extracción de entidades vía LLM, comunidades, resúmenes jerárquicos) **no se
implementa**: el costo de indexación es 100-1000x mayor que una indexación vectorial simple, y en
varias implementaciones el prompt de recuperación resulta *más largo*, no más corto — contrario
al objetivo de optimización de tokens de este proyecto. Además, un modelo de Power BI ya es un
grafo pequeño y explícito (tablas/relaciones con cardinalidad ya extraída), así que pagar el costo
de extracción semántica por LLM no tiene sentido cuando el dato ya viene estructurado.

Si en una fase futura se retoma, el alcance viable sería: un grafo **liviano** de navegación
(nodos = tablas, aristas = relaciones, sin resúmenes generados por LLM), construido directo desde
`cleaned_metadata` — básicamente una proyección de `relationships.json` a formato grafo (JSON de
nodos/aristas, o GraphML si se quiere compatibilidad con herramientas de visualización). Esto es
casi gratis de construir porque los datos ya existen; no requiere LLM ni librerías nuevas.

**No planificar esto en el plan de la fase actual.** Queda anotado como posible fase 3 futura,
condicionada a que se confirme un caso de uso real que lo justifique (por ejemplo, si el
`index.json` de la sección 2 resulta insuficiente para navegación en modelos muy grandes con
decenas de tablas).

---

## Checklist de arranque para Plan Mode (histórico — completado)

Este checklist cubrió la sesión original de Plan Mode para las secciones 1 y 2. Todos los ítems
se completaron (parser TMDL, interfaz común pbit/pbip, detección automática, fixtures, índice +
TOON, README/CHANGELOG, tests) — se deja como registro de lo que se cubrió, no como pendiente:

- [x] Confirmar lectura de este archivo y del código actual (`extractor.py`, `processor.py`,
      `cli.py`) antes de proponer diseño — no asumir estructura sin verificarla en el repo real.
- [x] Diseño del parser TMDL: qué librería/approach (parser manual por indentación vs. alguna
      gramática), y qué subconjunto de TMDL se soporta en v1 (tablas, columnas, measures,
      relaciones — explícitamente NO roles, perspectivas, culturas salvo que se decida ampliar).
- [x] Definir la interfaz común que deben cumplir `extractor.py` (pbit) y el nuevo extractor
      (pbip) para que `processor.py` no necesite saber cuál se usó.
- [x] Detección automática de tipo de entrada en `cli.py` (extensión/estructura de carpeta) y
      mensajes de error consistentes con el estilo actual.
- [x] Fixtures de prueba TMDL (creadas desde cero, `tests/fixtures/minimal_pbip/`).
- [x] Diseño de `index.json` y estructura `tables/*.json` (sección 2), como cambio aditivo.
- [x] Alcance acotado de TOON (solo columnas/relaciones/listado plano de measures) —
      implementado en la misma fase, validado empíricamente en `docs/token_optimization_report.md`.
- [x] `README.md` y `CHANGELOG.md` actualizados.
- [x] Tests para cada punto anterior (161 tests totales al momento de esta nota).

Para el trabajo posterior (resolver, MCP server, Skills, validación de precisión), ver "Estado
actual" al principio de este archivo y `docs/Analisis_Posicionamiento_Comparativa_Plan_Futuro.md`.
