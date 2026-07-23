# Informe de Validación de Escala (Fase 0)

**Fecha:** 2026-07-18
**Modelo de referencia:** proyecto PBIP sintético generado por `scripts/generate_synthetic_pbip.py` — 60 tablas (20 dimensión + 40 hecho), 288 measures, 120 relaciones.

---

## 1. Metodología

**Por qué sintético, no un modelo público real.** Se buscó explícitamente un modelo PBIP público y libre a escala enterprise antes de generar nada. Se revisaron 8 repositorios: `microsoft/powerbi-desktop-samples` (solo `.pbix`/`.pbit`, sin PBIP), `lczanna/semantic-model-explorer` (el mismo modelo `Sales Sample` de 11 tablas que ya está en `files_test/`, más una referencia a `AdventureWorks.bim` — formato Tabular Editor, no TMDL), `RuiRomano/pbip-demo` (3 proyectos, todos ≤8 tablas), `microsoft/fabric-samples` (un solo `.SemanticModel` de 1 tabla), `microsoft/Analysis-Services` (el mismo `Sales.SemanticModel` de 11 tablas), `JonathanJihwanKim/pbip-documenter` (4 tablas), `richhuwtaylor/adventure-works` (sin TMDL/PBIP, solo reporte). Conclusión: en julio 2026 no existe un modelo PBIP público a escala enterprise — el formato es reciente y las bases de datos de ejemplo clásicas (Contoso, AdventureWorksDW) solo circulan como `.bak`/`.bim`/`.pbix`, no como carpeta TMDL.

**Qué mide esto y qué no.** El generador produce una estructura TMDL sintética válida (esquema estrella: tablas dimensión con 8-14 columnas, tablas hecho con FKs + columnas numéricas + 5-10 measures con DAX variado — `SUM`, `CALCULATE`, `FILTER`, patrones `VAR`/`RETURN`). Sirve para medir el comportamiento propio de `pbi-docs` a escala (tiempos, tamaño de `index.json`, umbral TOON, rendimiento del resolver) — **no** dice nada sobre cómo se comporta el parser frente a las particularidades de autoría DAX de un modelo de producción real (nombres inconsistentes, expresiones muy anidadas de forma no uniforme, `calculation groups`, RLS, perspectives — explícitamente fuera de esta medición, ver sección 5).

**Reproducibilidad:**
```
python scripts/generate_synthetic_pbip.py <output_dir> --dims 20 --facts 40
pbi-docs -i <output_dir> -o <out> --index-format auto
```

**Límite del método de timing.** Los tiempos son de una sola corrida en una máquina de desarrollo (Windows, sin aislar CPU/IO), no un benchmark estadístico con múltiples repeticiones — sirven como señal de orden de magnitud, no como cifra de rendimiento garantizada.

---

## 2. Tiempos de extracción/procesamiento

`process_file()` completo (extracción TMDL → processor → los 4 archivos legacy → salida indexada) sobre las 60 tablas / 288 measures:

| `--index-format` | Tiempo (wall-clock, 1 corrida) |
|---|---|
| `json` | 0.603 s |
| `toon` | 0.828 s |
| `auto` | 0.864 s |

TOON/auto son más lentos que JSON puro (esperado: hacen el trabajo de JSON más la codificación columnar), pero la diferencia absoluta (~0.25s en 60 tablas) es intrascendente frente al tiempo de I/O de extracción TMDL. No hay una señal de que el pipeline se vuelva impráctico a este orden de magnitud de tablas.

---

## 3. Umbral TOON en modo `auto` a escala

Con `--index-format auto`, **60/60 tablas (100%) eligieron TOON**, ninguna JSON plano. Confirmado en `index.json`: cada entrada de tabla trae `"format": "toon"`.

Esto es consistente con el umbral ya documentado (`token_optimization_report.md` sección 4: 7 filas de columnas+measures es el punto de quiebre) — todas las tablas dimensión de este modelo sintético tienen ≥9 columnas y todas las de hecho superan las 10 filas combinadas, así que ninguna cae del lado "JSON gana" del umbral. **Hallazgo:** a esta escala, `--index-format auto` se comporta idéntico a forzar `toon` — el modo `auto` solo aporta valor diferencial en modelos con mezcla real de tablas pequeñas y grandes (como los modelos de ~10 tablas ya validados), no en un modelo grande donde casi todo supera el umbral.

---

## 4. Tamaño de salida por escenario de uso — la suposición que se invierte a escala

`token_optimization_report.md` (modelo de 7 tablas) mostró 91% de ahorro en el escenario "overview" cargando solo `index.json`. Repetir la misma metodología a 60 tablas da un resultado distinto:

| Escenario | Raw TMDL | pbi-docs | Resultado |
|---|---|---|---|
| **Overview** (`index.json` solo) | 108,869 bytes (60 archivos `.tmdl`) | 17,600 bytes | ✅ 83.8% ahorro — se mantiene |
| **Tabla específica** (`Fact01`) | 1,935 bytes (`Fact01.tmdl`) | 21,601 bytes (`index.json` + `tables/Fact01.json`) | ❌ **10.2x más grande**, no más chico |
| **Deep-dive completo** | 108,869 bytes | 236,123 bytes (`index.json` + `tables/*.json` + `relationships.json`) | ❌ **2.2x más grande** |

**Causa raíz:** `index.json` tiene un costo fijo que crece linealmente con el número de tablas (293 bytes/tabla en este modelo: nombre, conteos, categorías, path). En un modelo de 7 tablas ese costo fijo es trivial (2.3 KB) y se diluye. En uno de 60 tablas, `index.json` por sí solo (17.6 KB) ya pesa casi 10x lo que pesa una tabla individual cruda (`Fact01.tmdl`, 1.9 KB) — cargarlo como paso previo obligatorio a "una tabla específica" cuesta más que ir directo al `.tmdl` sin índice.

Esto no invalida el diseño — el escenario overview sigue ganando fuerte — pero sí invalida la generalización implícita de que "index.json + carga selectiva siempre gana": a partir de cierto número de tablas, el costo fijo del índice empieza a competir con (y superar a) el ahorro que da evitar cargar tablas irrelevantes. No se investigó en esta sesión dónde está el punto de cruce exacto (quedaría para una Fase 0.1 si se necesita precisión); con 2 puntos de datos (7 tablas gana, 60 tablas pierde en consulta puntual) alcanza para documentar que el punto de cruce existe y está en algún punto entre esos dos.

---

## 5. Rendimiento del resolver a escala — hallazgo, corrección y fix

Prueba rápida de sanidad sobre la salida `auto` (60 tablas, 288 measures):

| Función | Tiempo (medición original) |
|---|---|
| `list_tables()` | 0.0017 s |
| `get_table('Fact01')` | 0.0027 s |
| `find_measure_usages(..., transitive=True)` | **1.619 s** |

`list_tables`/`get_table` escalan bien (leen `index.json` o un solo archivo de tabla). El causante
real: cada salto del BFS interno de `find_measure_usages(transitive=True)` llamaba a
`_all_measures(model_dir)`, que relee y reparsea **las 60 tablas desde disco** — sin cachear nada
entre saltos. Esto sí se corrigió en esta sesión (no quedó solo documentado):
`_all_measures(model_dir)` ahora se llama **una sola vez** por invocación de
`find_measure_usages(transitive=True)`, cacheado y reutilizado en cada salto del BFS
(`pbi_extractor/resolver.py`). Verificado con un test determinista
(`tests/test_resolver.py::test_find_measure_usages_transitive_reads_model_once_not_per_hop`) que
mockea `_all_measures` y afirma que se llama exactamente 1 vez, sin importar cuántos saltos recorra
el BFS — más robusto que medir wall-clock, que resultó ruidoso entre corridas (ver nota abajo).

**Corrección post-fix, importante para la integridad de esta cifra:** al intentar re-medir el
"antes vs. después" en el mismo modelo para reportar un número limpio, se encontró que
`scripts/generate_synthetic_pbip.py` tenía un bug — los nombres de measure (`"Total Amount1"`, por
ejemplo) se repetían **entre las 40 tablas de hecho**, algo que un modelo Tabular real nunca
permite (los nombres de measure son únicos en todo el modelo, no solo por tabla). Esto contaminaba
el grafo de dependencias con falsos cruces entre tablas no relacionadas, e infló el BFS de forma
artificial — la cifra de 1.619s de la tabla de arriba mezclaba el costo real de "releer 60 tablas
por salto" con este artefacto del generador. **Se corrigió el generador** (los nombres de columna
numérica ahora llevan el nombre de tabla como prefijo, ej. `Fact01Amount1`, garantizando unicidad
real). Con el generador corregido, la mayoría de los measures de este modelo sintético no tienen
cadenas de uso profundas (las referencias entre measures del generador son en gran parte
aleatorias/no correlacionadas, así que muchos targets terminan en 0 usos en 1 solo salto) — no se
encontró un caso natural con suficiente profundidad de BFS en este modelo para re-medir un número
de wall-clock limpio y representativo del "antes" sin la contaminación del bug. Se optó por no
forzar un escenario artificial solo para conseguir una cifra bonita: la prueba de call-count
(arriba) es la verificación válida del fix, no un tiempo re-medido.

**Conclusión honesta:** el fix está aplicado y verificado correctamente (algorítmicamente
correcto: O(1) lecturas completas del modelo en vez de O(saltos)). La cifra original de 1.6s
sigue siendo evidencia válida de que *algo* escalaba mal a 60 tablas, pero no debe citarse como
"el costo exacto de releer por salto" sin la salvedad de que una parte de ese número venía del bug
del generador, ya corregido.

---

## 5.1. Seguimiento (2026-07-20) — hallazgos 2 y 3 de la sección 4, revisados

Los dos hallazgos que quedaban abiertos de la sección 4 se revisaron por separado, porque no son
el mismo tipo de problema.

**"`--index-format auto` pierde valor diferencial a escala" (sección 3) — cerrado, no era un
defecto.** `_should_use_toon()` (`pbi_extractor/indexed_output.py`) decide por tabla, sobre el
tamaño de esa tabla — no tiene ni necesita noción de cuántas tablas tiene el modelo. Que 60/60
tablas elijan TOON en este modelo sintético es el resultado *correcto* dado que todas superan el
umbral de 7 filas, no un bug de la heurística. El modo `auto` simplemente no tiene margen para
diferenciarse de forzar `toon` cuando el modelo no mezcla tablas grandes y chicas — eso ya estaba
dicho en la sección 3, solo faltaba dejarlo explícito como "cerrado", no "pendiente".

**Inversión de costo fijo de `index.json` (sección 4) — causa raíz identificada y corregida
parcialmente.** `resolver.get_table()` cargaba `index.json` completo antes de leer la tabla
pedida, solo para confirmar que el nombre existía — redundante, porque el nombre de archivo es
100% determinístico (`_safe_filename(table_name)`). Se corrigió (`pbi_extractor/resolver.py`):
lectura directa de `tables/<name>.json` primero, `index.json` solo como fallback para el mensaje
de error cuando la tabla no existe. Re-midiendo el mismo modelo sintético (60 tablas/288 measures,
regenerado, por lo que los bytes exactos varían levemente por aleatoriedad del generador frente a
la sección 4 — mismo orden de magnitud):

| Escenario | Raw TMDL | Antes del fix | Después del fix |
|---|---|---|---|
| **Tabla específica** (`Fact01`) | 2,109 bytes | 21,807 bytes (`index.json` 17,596 + `tables/Fact01.json` 4,211) → **10.34x** más grande | 4,211 bytes (solo `tables/Fact01.json`, sin `index.json`) → **2.00x** más grande |
| **Deep-dive completo** | 98,675 bytes | 244,369 bytes → **2.48x** más grande | Sin cambio — el fix no aplica acá (ver abajo) |

El fix resuelve la mayor parte del escenario "tabla específica" (de 10.3x a 2.0x), pero **no lo
revierte a una victoria neta en este modelo sintético en particular**: la razón es que el
generador (`scripts/generate_synthetic_pbip.py`) produce TMDL deliberadamente limpio (sin
`lineageTag`/`annotations`, a diferencia de un export real de Power BI Desktop), así que no hay
"ruido estructural" que el JSON de `pbi-docs` esté eliminando — el 91%/35.4% de ahorro original
(`token_optimization_report.md`) vino en parte de descartar ese ruido en un modelo *real*
(`Supply Chain Sample.pbip`, con 222 líneas de `lineageTag`/`annotations`). Confirmar si el fix por
sí solo ya gana en un modelo real grande requeriría uno — que sigue sin existir públicamente (ver
sección 1).

**Deep-dive completo no se mueve con este fix, por diseño** (así estaba previsto en el plan): ese
escenario necesita genuinamente la lista completa de tablas, así que `list_tables()` sigue leyendo
`index.json` — correcto, no hay nada que evitar ahí. Diagnóstico adicional (medido, no
implementado en esta pasada): remover el `indent=2` de `json.dump()` en
`pbi_extractor/indexed_output.py` (JSON compacto, pensado para consumo por LLM en vez de lectura
humana) reduciría el total de 244,369 a 136,070 bytes (**-44.3%**), bajando la razón de 2.48x a
1.38x frente a TMDL crudo — indent=2 explica una porción real y significativa del exceso, pero no
todo: incluso compacto, sigue siendo 1.38x más grande que el TMDL crudo de este modelo
particularmente limpio. No se implementó este cambio en esta sesión porque (a) no estaba en el
alcance aprobado y (b) cambiaría la legibilidad humana de la salida para todos los modos, no solo
`auto`/escala — amerita su propia decisión de diseño, no un ajuste incidental. **Queda documentado
como hallazgo abierto #3**, con causa parcial ya medida (no supuesta): `indent=2` + la ausencia de
ruido estructural que remover en TMDL sintético limpio.

---

## 5.2. Seguimiento (2026-07-21) — hallazgo #3 implementado, cifra real medida

El hallazgo #3 (sección 5.1) se implementó esta sesión: la salida indexada (`index.json`,
`tables/*.json`, `relationships.json`) ahora es **compacta por defecto**
(`json.dump(..., separators=(",", ":"))`, sin `indent`), con un flag `--pretty` opcional que
restaura `indent=2` para debug humano. Justificación: el consumidor primario de estos archivos es
`resolver.py`/`mcp_server.py`/un LLM, no un humano leyendo JSON crudo — el artefacto legible para
humanos sigue siendo `model_documentation.md`, que no se tocó.

Re-corrida completa de la metodología de la sección 5.1 (`scripts/generate_synthetic_pbip.py`,
`num_dims=20, num_facts=40` — mismos parámetros; los bytes exactos vuelven a variar levemente por
la aleatoriedad propia del generador, ya documentada, no por el cambio medido aquí):

| Escenario | Raw TMDL | Antes (`indent=2`, ahora `--pretty`) | Después (compacto, default) | Reducción |
|---|---|---|---|---|
| **Tabla específica** (`Fact01`, vía `get_table()`, sin `index.json`) | 2,109 bytes | 4,211 bytes → 2.00x | **2,381 bytes → 1.13x** | -43.5% |
| **Deep-dive completo** (`index.json` + `tables/*.json` + `relationships.json`) | 115,195 bytes | 244,361 bytes → 2.12x | **136,062 bytes → 1.18x** | -44.3% |

La reducción medida (-44.3% en deep-dive) coincide casi exactamente con la proyección de la
sección 5.1 (-44.3% proyectado sobre una corrida distinta del generador, 2.48x→1.38x) — confirma
que la causa raíz estaba correctamente diagnosticada, no solo estimada. El resultado real termina
mejor que lo proyectado (1.18x aquí vs. 1.38x proyectado) porque esta corrida del generador dio un
modelo con relación bytes-por-tabla distinta; la comparación válida es el porcentaje de reducción
compacto-vs-pretty (-44.3%, estable entre corridas), no el ratio absoluto contra TMDL crudo (que
depende del modelo puntual generado).

**Conclusión honesta:** "tabla específica" queda prácticamente en paridad con el TMDL crudo (1.13x)
combinando este fix con el de `get_table()` de la sección 5.1 — la app de auditoría/lectura ya no
paga una penalización de tokens significativa en el caso de uso más común (una tabla puntual).
"Deep-dive completo" mejora sustancialmente (2.12x → 1.18x) pero sigue sin ser una victoria neta
contra el TMDL crudo en este modelo sintético particular — consistente con la explicación ya dada
en la sección 5.1 (el generador produce TMDL limpio, sin `lineageTag`/`annotations` que un export
real de Power BI Desktop sí tiene y que `pbi-docs` descarta). **El conteo real de tokens vía API
de Anthropic (`scripts/count_tokens.py`) sigue bloqueado** por falta de `ANTHROPIC_API_KEY`/paquete
`anthropic` en este entorno — las cifras de esta sección, como las de toda la sección 5, son bytes
medidos directamente, no tokens reales.

---

## 6. Scope gaps no ejercitados (por decisión, no por descuido)

Por decisión explícita antes de generar el modelo sintético, éste **no** incluye RLS/roles, perspectives ni calculation groups — están fuera del scope del parser v1 (ver `CLAUDE.md` sección 1) y ampliarlo no era el objetivo de esta fase. Si en el futuro se decide ampliar el parser, esa validación de escala debería repetirse con un modelo que sí los incluya.

---

## 7. Conclusiones

1. **El pipeline no se rompe a 60 tablas / 288 measures** — tiempos siguen siendo sub-segundo.
2. **`--index-format auto` pierde su valor diferencial a esta escala** (converge a `toon` puro) — no es un defecto, es el resultado correcto de una decisión por-tabla en un modelo donde todas las tablas superan el umbral. **Cerrado el 2026-07-20**, ver sección 5.1.
3. **La narrativa de "ahorro de tokens" necesita matiz por escala**: el escenario overview sigue ganando fuerte, pero "tabla específica" y "deep-dive" se invertían en un modelo de 60 tablas frente a uno de 7 — el costo fijo de `index.json` crece con el número de tablas. **Resuelto en dos pasadas**: `resolver.get_table()` ya no paga ese costo fijo en consultas puntuales (2026-07-20, sección 5.1: 10.34x → 2.00x en "tabla específica"), y la salida indexada es compacta por defecto desde 2026-07-21 (sección 5.2: 2.00x → 1.13x en "tabla específica", 2.12x → 1.18x en "deep-dive completo", -44.3% medido, no solo proyectado). "Tabla específica" queda en paridad práctica con el TMDL crudo; "deep-dive completo" mejora fuerte pero no revierte a victoria neta en este modelo sintético (ver sección 5.2 para el por qué).
4. **`find_measure_usages(transitive=True)` no escalaba bien — ya corregido.** Releer el modelo completo en cada salto BFS era aceptable a 7 tablas, notorio a 60. Fix aplicado (una sola lectura cacheada, no por salto), verificado con test determinista de call-count. Un bug del generador sintético (nombres de measure duplicados entre tablas) se descubrió en el proceso y también se corrigió — ver sección 5 para el detalle de por qué el número original de 1.6s no debe tomarse como una medición limpia del efecto aislado.

Los hallazgos 2, 3 y 4 (índice/costo fijo, `indent=2`, rendimiento del resolver) ya se resolvieron
— ver secciones 5, 5.1 y 5.2 para el detalle de cada corrección. El conteo real de tokens vía API
de Anthropic sigue bloqueado por falta de credenciales en este entorno (todas las cifras de este
reporte son bytes medidos, no tokens); queda pendiente para cuando haya `ANTHROPIC_API_KEY`
disponible.
