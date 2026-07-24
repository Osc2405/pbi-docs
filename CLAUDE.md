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
