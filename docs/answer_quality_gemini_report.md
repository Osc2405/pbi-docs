# Calidad de respuesta con Gemini real (function calling) — Sales Sample

**Fecha:** 2026-07-23
**Modelo de referencia:** `files_test/Sales Sample.pbip` (11 tablas, 29 measures, 5 relaciones)
**Proveedor:** Gemini (`google-genai`, modelo `gemini-flash-lite-latest`), API real — no
subagentes de Claude Code.

---

## 1. Resumen ejecutivo

| Condición | Precisión | Tokens totales (20 preguntas) | Ahorro vs A |
|---|---|---|---|
| A — TMDL crudo | 14/20 (70%) | 376,159 | — |
| B — pbi-docs JSON | 18/20 (90%) | 202,674 | -46.1% |
| C — function calling (resolver.py) | 19/20 (95%) | 37,993 | -89.9% |

**Hallazgo central: la Condición C (consulta dirigida vía function calling) gana en precisión Y en
costo de tokens al mismo tiempo.** No hay trade-off entre "barato" y "correcto" en este modelo —
comprimir/acotar el contexto no le costó exactitud al modelo, se la mejoró. Esto responde
directamente la pregunta que motivó este experimento: pbi-docs no solo reduce tokens, las
respuestas resultantes son más útiles, no solo más baratas.

Este informe corre el mismo tipo de experimento que `docs/precision_validation_report.md`
(condiciones A/B/C, calificación objetiva sin juez-LLM), pero con dos diferencias deliberadas: (1)
un proveedor de IA externo real (Gemini vía API, no subagentes de Claude dentro de la misma
sesión), y (2) un modelo mediano (`Sales Sample.pbip`, 11 tablas/29 measures) en vez del modelo
chico (7 tablas) del informe original — exactamente lo que la sección 6 de ese informe pedía como
trabajo futuro. No es una comparación 1:1 con esa tabla — otro modelo, otro proveedor.

---

## 2. Metodología

### 2.1 Preguntas
20 preguntas con respuesta de referencia, reusadas de `docs/human_validation_protocol.md` sección
5 (protocolo de validación humana, bloqueado en reclutamiento — sin relación con este experimento).
Copia estructurada canónica: `scripts/fixtures/sales_sample_questions.json`. Dificultad variada
(fácil/media/difícil/trampa), incluye 2 preguntas trampa (18, 19) y una pregunta 17 diseñada para
favorecer a la Condición C (búsqueda cruzada de measures).

### 2.2 Modelo
`Sales Sample.pbip` — sample oficial de Microsoft, 11 tablas, 81 columnas, 29 measures, 5
relaciones (1 inactiva). Modelo mediano, consistente con lo que
`docs/precision_validation_report.md` sección 6 señalaba como necesario para una medición más
representativa que el modelo de 7 tablas usado ahí.

### 2.3 Condiciones
- **A — TMDL crudo:** los archivos `.tmdl` core de `files_test/Sales Sample.SemanticModel/definition/`
  (`database.tmdl`, `model.tmdl`, `relationships.tmdl`, `tables/*.tmdl` — excluye `cultures/`),
  concatenados en un único prompt junto con la pregunta. Una llamada a Gemini por pregunta, sin
  contexto compartido entre preguntas.
- **B — pbi-docs JSON:** `output/Sales Sample/{index.json, tables/*.json, relationships.json}`
  completos, mismo patrón de una llamada por pregunta.
- **C — function calling real:** Gemini recibe 8 funciones envolviendo `pbi_extractor/resolver.py`
  (`list_tables`, `get_table`, `get_measure`, `search_measures`, `search_columns`,
  `get_relationships`, `get_measure_dependencies`, `find_measure_usages`) y decide por sí mismo
  cuáles llamar (Automatic Function Calling del SDK `google-genai`, tope de 6 llamadas remotas por
  pregunta). No se le da ningún contexto precargado — tiene que consultar todo.

Implementación: `scripts/answer_quality_gemini.py`.

### 2.4 Calificación
Manual, con el mismo rubro de `docs/human_validation_protocol.md` sección 6:
`Correcta` / `Parcial` / `Incorrecta` / `NOT_FOUND` (correcto solo en la pregunta 19, la trampa de
measure inexistente). Sin juez-LLM, mismo principio que `docs/precision_validation_report.md`
sección 2.3. **Nota de honestidad:** la calificación de este informe no es ciega — la misma
persona armó el fixture de preguntas, corrió el script y calificó las respuestas, a diferencia del
"calificador ciego" que pide el protocolo humano. Resultados en
`scripts/fixtures/sales_sample_gemini_results_validados.csv`.

---

## 3. Resultados de precisión

12 de las 20 preguntas fueron correctas en las 3 condiciones sin nada que destacar. Las 8
preguntas restantes muestran el patrón real de dónde cada condición gana o pierde:

| # | Pregunta (resumen) | A | B | C | Nota |
|---|---|---|---|---|---|
| 1 | ¿Cuántas tablas tiene el modelo? | NOT_FOUND | Correcta | Correcta | A no logró contar de forma confiable enumerando ~11 archivos TMDL en un solo dump |
| 2 | ¿Cuántas measures en total? | NOT_FOUND | Correcta | Correcta | mismo patrón que la pregunta 1 |
| 9 | Categoría de negocio de "Cost" | NOT_FOUND | Correcta | Correcta | campo exclusivo de `categorizer.py`, no existe en TMDL crudo — el mismo patrón que ya documentaba `docs/precision_validation_report.md` |
| 14 | Measures categoría "margin" | NOT_FOUND | Correcta | Correcta | mismo enriquecimiento que la pregunta 9 |
| 15 | Tablas con `partition_count: 0` | NOT_FOUND | NOT_FOUND | NOT_FOUND (12 tool calls) | **gap real de producto** — ver sección 3.1 |
| 17 | Measures cuyo nombre contiene "YTD" | Correcta* | Correcta* | Correcta* | *la referencia original decía 2, estaba incompleta — corregida a 3, ver sección 3.2 |
| 18 | Format string vacío (trampa) | NOT_FOUND | NOT_FOUND | Correcta | ambigüedad del propio experimento, no gap de datos — ver sección 3.3 |
| 19 | Measure inexistente (trampa) | NOT_FOUND (correcto) | NOT_FOUND (correcto) | NOT_FOUND (correcto) | las 3 condiciones identificaron correctamente que la measure no existe |

### 3.1 Hallazgo real de producto: `partition_count` no llega al índice/resolver

La pregunta 15 falló en las **3 condiciones**, incluida la C — donde Gemini hizo **12 llamadas a
herramientas** en una sola pregunta (el promedio del resto es 2.1) intentando encontrar el dato y
no lo logró. Causa raíz confirmada en el código, no es un fallo de razonamiento del modelo:
`pbi_extractor/processor.py:228` calcula `partition_count` para cada tabla, pero
`pbi_extractor/indexed_output.py` nunca lo copia a `index.json` ni a `tables/*.json` — el campo
solo sobrevive en `metadata.json` (el dump único de referencia), que ni la Condición B ni la C
usan. `resolver.get_table()` lee directamente de `tables/<name>.json`
(`pbi_extractor/resolver.py:85`), así que el dato es genuinamente invisible para el resolver y
para cualquier tool MCP construida sobre él — no es que Gemini no supo buscar, es que el dato no
está expuesto en ningún lugar que pueda consultar. Decisión de esta sesión: **documentar, no
arreglar** — el fix toca `indexed_output.py`, que afecta el formato de salida de todos los
modelos, y queda fuera del alcance de esta sesión (evaluado explícitamente, ver plan de esta
sesión).

### 3.2 Corrección: la respuesta de referencia de la pregunta 17 estaba incompleta

Las 3 condiciones encontraron independientemente una tercera measure con "YTD" en el nombre
(`Value (ytd)`, tabla `Dynamic Measure`) que la respuesta de referencia original (en
`docs/human_validation_protocol.md` y el fixture) no listaba — decía "2", debía decir "3".
Verificado en vivo contra el modelo real:

```python
resolver.search_measures(Path("output/Sales Sample"), "YTD")
# -> Dynamic Measure | Value (ytd)
#    Sales           | Sales Amount (YTD, LY)
#    Sales           | Sales Amount (YTD)
```

Las 3 condiciones tenían razón; la referencia estaba mal. Corregido en
`docs/human_validation_protocol.md` sección 5 y en `scripts/fixtures/sales_sample_questions.json`
el mismo día. Es la segunda vez en este proyecto que un experimento de validación encuentra un
error en material de referencia previamente dado por bueno (la primera fue el bug de
`resolver._extract_references()` encontrado el 2026-07-20 validando contra PBIP reales) — mismo
patrón: los datos reales encuentran cosas que los materiales curados a mano no.

### 3.3 La pregunta 18 (trampa) expone una ambigüedad del experimento, no un gap de datos

A y B contestaron `NOT_FOUND` para el format string vacío de la measure "Value"; C acertó
("está vacío"). La measure existe y ambas condiciones A y B la encontraron sin problema en la
pregunta 16 — no es un problema de datos faltantes. La instrucción del experimento
(`INSTRUCTION_STATIC` en `scripts/answer_quality_gemini.py`) le pide al modelo responder
`NOT_FOUND` si "la respuesta no está en el contexto", y un campo presente-pero-vacío puede leerse
como "no está" en vez de "está, y es vacío". Se documenta como limitación del diseño del
experimento (sección 6), no como hallazgo de producto — aunque es sugerente que la Condición C,
recibiendo el valor estructurado directamente de la herramienta (`format_string: ""`), no tuvo
esta ambigüedad.

### 3.4 Patrón general de los fallos de Condición A

Los 4 fallos propios de Condición A que no comparte con B (preguntas 1, 2, 9, 14) caen todos en
información que pbi-docs calcula o agrega y que TMDL crudo no tiene explícita: categoría de
negocio (enriquecimiento de `categorizer.py`) o conteos que requieren enumerar manualmente ~11
archivos dentro de un dump de ~50KB en un solo prompt. Mismo patrón cualitativo que ya documentaba
`docs/precision_validation_report.md` con el modelo chico — se sostiene a esta escala mediana.

---

## 4. Resultados de tokens (reales, no aproximación)

| Condición | Tokens prompt (prom./pregunta) | Tokens completion (prom.) | Tokens totales (20 preguntas) |
|---|---|---|---|
| A — TMDL crudo | 18,792 | 16 | 376,159 |
| B — pbi-docs JSON | 10,117 | 16 | 202,674 |
| C — function calling | 1,875 | 25 | 37,993 |

Ahorro: B vs A -46.1%, C vs A -89.9%, C vs B -81.3%. Consistente en dirección con
`docs/token_optimization_report.md` (que ya había mostrado que el tokenizador real de Gemini
favorece más a pbi-docs que la aproximación caracteres÷4) — acá se ve el mismo efecto a nivel de
un experimento de preguntas de negocio completo, no solo de tamaño de archivo.

---

## 5. Matiz honesto: llamadas a herramientas (Condición C)

Promedio de 2.1 llamadas por pregunta, pero la distribución no es pareja: la mayoría de las
preguntas se resuelven en 1-2 llamadas, y la pregunta 15 es un outlier extremo con 12 llamadas
—Gemini insistió probando distintas tablas/tools buscando `partition_count` antes de rendirse,
exactamente porque el dato no está expuesto en ningún lugar que pueda consultar (sección 3.1). Sin
ese outlier, el promedio del resto de las preguntas ronda 1.6 llamadas — la fricción real de la
Condición C en la práctica es baja, salvo cuando el dato que se pide genuinamente no está en la
superficie de consulta.

---

## 6. Limitaciones

- **Un solo proveedor externo todavía** — Gemini, no GPT ni otros. `docs/precision_validation_report.md`
  sección 6 ya tenía a Claude (vía subagentes); este informe agrega Gemini (vía API real); GPT y
  el resto siguen sin validar.
- **Calificación no ciega** (sección 2.4) — la misma persona armó preguntas, corrió el
  experimento y calificó. El rubro es objetivo (comparación contra referencia, no juicio
  subjetivo), pero no tiene el filtro adicional de un calificador independiente.
- **No reemplaza la validación humana** de `docs/human_validation_protocol.md`, que sigue
  bloqueada en logística de reclutamiento — sin relación con este experimento. Mide si un LLM
  puede responder correctamente, no si un desarrollador humano real llega más rápido o con más
  confianza a la respuesta correcta.
- **No comparable 1:1 con `docs/precision_validation_report.md`** — otro modelo (11 tablas vs 7),
  otro proveedor (Gemini real vs subagentes de Claude), preguntas distintas. Ambos informes son
  medidas independientes que apuntan en la misma dirección, no una réplica exacta.
- **El gap de `partition_count` (sección 3.1) queda documentado, no arreglado** — decisión
  explícita de esta sesión, para no expandir el alcance a un cambio en `indexed_output.py` que
  afecta el formato de salida de todos los modelos.
- **Un solo modelo mediano** — 11 tablas es un paso adelante respecto a las 7 del informe
  original, pero sigue siendo chico comparado con un modelo enterprise real (decenas de tablas) —
  ver `docs/scale_validation_report.md` para las regresiones de ahorro de tokens ya documentadas a
  60 tablas sintéticas, que no se remidieron aquí con calidad de respuesta.

---

## 7. Conclusión

Este informe cierra, para el eje de calidad de respuesta, la limitación de "un solo proveedor" que
`docs/precision_validation_report.md` sección 6 dejaba abierta (el eje de conteo de tokens ya se
había cerrado parcialmente el mismo día con `scripts/count_tokens.py --provider gemini`, ver
`docs/token_optimization_report.md`). El resultado central — Condición C gana en precisión y en
costo simultáneamente — es la respuesta directa a la pregunta que motivó este experimento: la
compresión de pbi-docs no sacrifica utilidad, y en este modelo la consulta dirigida (function
calling) resultó ser más precisa que ambos dumps completos (TMDL crudo y JSON de pbi-docs), no
solo más barata. Los dos hallazgos de datos encontrados en el camino (`partition_count` no
propagado, referencia de la pregunta 17 incompleta) son ejemplos concretos de por qué vale la pena
seguir corriendo este tipo de validación contra datos y proveedores reales en vez de confiar solo
en aproximaciones o en un único proveedor.
