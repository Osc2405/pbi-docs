# Protocolo de validación con usuarios humanos reales — Horizonte 3

**Motivación:** `docs/Analisis_Posicionamiento_Comparativa_Plan_Futuro.md`, sección 6, identifica
este experimento como el "próximo paso crítico" del roadmap. El proxy automatizado con 3 agentes
de IA aislados (`docs/precision_validation_report.md`) ya corrió y dio señal positiva, pero el
propio informe aclara que no reemplaza la validación con desarrolladores/analistas humanos reales.
Este documento es el protocolo ejecutable para correr ese experimento.

**Hipótesis a probar (sección 6.2 del análisis):**
> Con el Context Resolver/MCP de pbi-context, los agentes de IA (asistidos por un humano) responden
> preguntas sobre modelos Power BI con la misma precisión que usando el contexto completo, pero
> con al menos 70% menos tokens y 40% menos tiempo.

---

## 1. Modelo de prueba

**`files_test/Sales Sample.pbip`** — sample oficial de Microsoft (`microsoft/Analysis-Services`,
carpeta `pbidevmode/fabricps-pbip/SamplePBIP`, licencia MIT), descargado byte-exacto (no
convertido desde `.pbix`, evitando cualquier alteración de formato).

| Métrica | Valor |
| :--- | ---: |
| Tablas | 11 |
| Columnas | 81 |
| Measures | 29 |
| Relaciones | 5 (1 inactiva) |

Cumple el rango pedido por el diseño original (10-15 tablas, 30-50 measures) y, a diferencia de un
fixture sintético, incluye patrones reales de exportación (calculation-group-like tables sin
partición, DAX con variables, una relación inactiva, formato `$#,##0` con distintos separadores).

Al descargarlo y correr `pbi-context` contra él se encontró y corrigió un bug real en
`pbip_extractor.py`: las medidas con expresión DAX delimitada por triple backtick
(`` measure X = ``` ... ``` ``, sintaxis que usan Tabular Editor y varios formateadores DAX) se
extraían como el literal `` ``` `` en vez del DAX real. Corregido (7 medidas afectadas en este
modelo, ver tabla "Dynamic Measure"); test de regresión en
`tests/test_pbip_extractor.py::test_parse_measure_backtick_fenced_dax`.

Para regenerar la salida de pbi-context (Condición B/C) tras cualquier cambio:
```
python -m pbi_extractor.cli --input "files_test/Sales Sample.pbip" --output output
```

---

## 2. Condiciones

| Condición | Material que ve el participante |
| :--- | :--- |
| **A — TMDL crudo** | Los archivos en `files_test/Sales Sample.SemanticModel/definition/` (11 `.tmdl` de tablas + `model.tmdl` + `relationships.tmdl` + `database.tmdl`). Sin herramienta de IA — el participante lee los archivos directamente, como si documentara el modelo a mano. |
| **B — JSON de pbi-context** | `output/Sales Sample/` completo (`index.json`, `tables/*.json`, `relationships.json`, `metadata.json`) — carga completa, sin consulta selectiva. |
| **C — MCP/Resolver acotado** | Claude Code (u otro cliente MCP) conectado al servidor `pbi-context` vía `.mcp.json`, apuntando a `output/Sales Sample` (ajustar el path del `.mcp.json` actual, que hoy apunta a `output/Supply Chain Sample`). El participante pregunta en lenguaje natural; el agente decide qué tool llamar (`list_tables`, `get_table`, `get_measure`, `search_measures`, `search_columns`, `get_relationships`). |

**Nota sobre A:** en el proxy automatizado (agentes de IA), la condición A fue un agente leyendo
TMDL crudo. Con humanos reales hay una variante a decidir: ¿el participante lee el TMDL crudo él
mismo, o abre el `.pbip` en Power BI Desktop y navega el modelo visualmente? Este protocolo asume
**lectura directa de TMDL** (más comparable a B y C, no depende de tener Power BI Desktop
instalado) — si se corre con Power BI Desktop en su lugar, documentarlo como variante A' separada,
no mezclar los datos.

---

## 3. Diseño experimental

**Between-subjects** (cada participante ve **una sola** condición) — no counterbalanced
within-subject. Motivo: con within-subject, un participante que ya respondió una pregunta en la
condición A recuerda la respuesta al llegar a B o C, contaminando la medición de precisión y
tiempo — el riesgo de contaminación pesa más que la ganancia de potencia estadística con un N
tan chico (10-15). Trade-off aceptado explícitamente.

- **Participantes:** 12-15 desarrolladores/analistas con experiencia Power BI (reclutamiento fuera
  de alcance de este documento — logística del usuario).
- **Asignación:** aleatoria, grupos de ~4-5 por condición (A/B/C).
- **Duración estimada:** 30-45 min por sesión (20 preguntas + configuración inicial).
- **Anonimato:** si los resultados se publican (sección 6.3 del análisis de posicionamiento),
  anonimizar participantes (P1, P2, ...), no nombres.

### Procedimiento por sesión

1. Explicar la tarea: "vas a responder 20 preguntas sobre un modelo de Power BI usando únicamente
   [material de tu condición]". No revelar qué condición es "la buena" ni que hay comparación
   entre condiciones.
2. Dar acceso al material correspondiente (carpeta TMDL / carpeta `output/` / cliente con MCP
   configurado). Para C, confirmar que el servidor responde antes de empezar (`--mcp-serve` vivo).
3. Presentar las 20 preguntas de la sección 5, una por una, en orden.
4. Por cada pregunta, registrar (planilla, ver sección 4):
   - Tiempo desde que se muestra la pregunta hasta que el participante da su respuesta final.
   - La respuesta tal cual la dio (sin corregir).
   - Confianza autoreportada 1-5 ("¿qué tan seguro estás de tu respuesta?").
   - Para C: qué tools/queries usó (si el cliente lo expone) — sirve para medir tokens reales
     luego con `scripts/count_tokens.py`.
5. El participante puede responder `NOT_FOUND` / "no sé" en vez de adivinar — instruirlo
   explícitamente, igual que en el proxy automatizado (evita que una condición gane por
   inventar respuestas plausibles).

---

## 4. Planilla de recolección de datos

Una fila por (participante × pregunta). Columnas mínimas:

| participant_id | condition | question_id | answer_given | time_seconds | confidence_1_5 | grader_verdict |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |

`grader_verdict` se completa después, en la fase de calificación (sección 6), no durante la
sesión — el participante no debe saber si acertó o no mientras responde, para no sesgar su
confianza autoreportada en preguntas siguientes.

---

## 5. Las 20 preguntas (con respuesta de referencia)

Calculadas leyendo `output/Sales Sample/metadata.json` directamente — no vistas por los
participantes. Dificultad marcada para asegurar variedad (igual que pide la sección 6.1 del
análisis: "desde qué medidas hay hasta cómo se calcula el margen bruto y qué tablas involucra").

**Nota (2026-07-23):** estas mismas 20 preguntas/respuestas de referencia también existen en forma
estructurada en `scripts/fixtures/sales_sample_questions.json`, fuente canónica para el
experimento automatizado con Gemini (`docs/answer_quality_gemini_report.md`). La tabla de esta
sección se mantiene como versión legible para correr sesiones humanas.

| # | Dificultad | Pregunta | Respuesta de referencia |
| :--- | :--- | :--- | :--- |
| 1 | Fácil | ¿Cuántas tablas tiene el modelo? | 11 |
| 2 | Fácil | ¿Cuántas measures tiene el modelo en total? | 29 |
| 3 | Fácil | ¿Cuántas relaciones existen entre tablas? | 5 |
| 4 | Fácil | ¿La relación entre `Sales[Delivery Date]` y `Calendar[Date]` está activa o inactiva? | Inactiva |
| 5 | Fácil | ¿Cuál es el format string de la measure "Sales Amount"? | `$ #,##0` |
| 6 | Media | ¿A qué tabla pertenece la measure "Margin %"? | Sales |
| 7 | Media | ¿Qué expresión DAX tiene la measure "# Stores"? | `COUNTROWS('Store')` |
| 8 | Media | Listá todas las columnas ocultas (`isHidden`) de la tabla "Sales". | Quantity, CustomerKey, StoreKey, ProductKey, Net Price, Unit Cost (6 columnas) |
| 9 | Media | ¿Qué categoría de negocio (revenue/cost/margin/...) le asigna pbi-context a la measure "Cost"? | cost |
| 10 | Media | ¿Qué columna de la tabla "Customer" tiene tipo de dato `dateTime`? | Birthday |
| 11 | Difícil | En la relación donde `Sales.ProductKey` es el lado "muchos", ¿qué tabla es el lado "uno"? | Product |
| 12 | Difícil | ¿Cómo se llama la measure que calcula la diferencia entre "Sales Amount" y "Sales Amount (LY)"? | `Sales Amount  (Δ LY)` (nota: doble espacio en el nombre real) |
| 13 | Difícil | ¿Qué measure usa `USERELATIONSHIP` para activar la relación inactiva de Delivery Date? | Sales Qty by Delivery Date |
| 14 | Difícil | ¿Cuántas measures de la tabla "Sales" están categorizadas como "margin"? | 4 (Margin, Margin (ly), Margin %, Margin % Overall) |
| 15 | Difícil | ¿Qué dos tablas tienen `partition_count: 0` (sin partición de datos)? | Smart Calcs, Time Intelligence |
| 16 | Difícil | ¿Qué measure usa `SELECTEDVALUE` para construir un selector dinámico de measures? | Value (tabla "Dynamic Measure") |
| 17 | Difícil | Buscá todas las measures cuyo nombre contenga "YTD". ¿Cuántas hay y cómo se llaman? | 3: "Sales Amount (YTD)", "Sales Amount (YTD, LY)", "Value (ytd)" (tabla Dynamic Measure) |
| 18 | Trampa | ¿Cuál es el format string de la measure "Value" (tabla "Dynamic Measure")? | "" (vacío — no tiene format string definido) |
| 19 | Trampa | ¿Cuál es la expresión DAX de la measure "Total Revenue"? | NOT_FOUND — esa measure no existe en este modelo |
| 20 | Difícil | ¿Qué tabla de hechos se relaciona tanto con "Customer" como con "Store"? | Sales |

**Nota sobre la pregunta 17:** está pensada para favorecer a la Condición C — un participante con
acceso a `search_measures("YTD")` la responde en una consulta; en A/B implica escanear manualmente
todas las measures. Es intencional: mide justamente la ventaja que el Resolver/MCP dice ofrecer.

**Corrección (2026-07-23):** la respuesta de referencia original decía "2" y omitía
`Value (ytd)` (tabla `Dynamic Measure`) — encontrada independientemente por las 3 condiciones en
`docs/answer_quality_gemini_report.md` (experimento con Gemini real) y confirmada en vivo con
`resolver.search_measures(Path("output/Sales Sample"), "YTD")`. La respuesta de referencia estaba
incompleta, no las respuestas de los agentes.

---

## 6. Calificación

- **Calificador ciego:** idealmente alguien que no sabe qué condición generó cada respuesta
  (mezclar las filas de la planilla antes de calificar, ocultando la columna `condition`).
- **Veredictos:** `Correcto` (exacto o equivalente semántico — ver criterio del proxy
  automatizado en `docs/precision_validation_report.md` sección 2.3), `Parcial` (identificó el
  objeto correcto pero el valor está incompleto o impreciso), `Incorrecto`, `NOT_FOUND` (solo
  correcto en la pregunta 19).
- Completar `grader_verdict` en la planilla de la sección 4 después de recolectar todas las
  sesiones, no en vivo.

---

## 7. Métricas y análisis

| Métrica | Cómo se calcula |
| :--- | :--- |
| % de precisión por condición | `Correcto` / 20, promediado entre participantes de esa condición |
| Tiempo mediano hasta respuesta por condición | Mediana de `time_seconds`, por pregunta y agregado |
| Confianza autoreportada vs. precisión real | Correlación simple — ¿los participantes de A están tan seguros como los de B/C aun cuando se equivocan más? |
| Tokens reales de contexto por condición | `scripts/count_tokens.py` sobre los archivos que cada condición carga (A: `.tmdl`, B: `output/Sales Sample/`, C: acumulado de las respuestas de `--query`/tool calls si el cliente las expone) — reemplaza la aproximación bytes÷4 de informes previos |

Contrastar contra la hipótesis de la sección 6.2: ¿≥70% menos tokens y ≥40% menos tiempo en C
vs. A, sin pérdida de precisión? Reportar el resultado tal cual salga, incluyendo si no se cumple
— mismo estándar de honestidad que `docs/precision_validation_report.md` sección 5 (matizar, no
solo citar la cifra más favorable).

---

## 8. Fuera de alcance de este protocolo

- Reclutamiento de participantes (logística externa).
- Publicación de resultados como estudio de caso — posterior a correr el experimento (sección 6.3
  del análisis de posicionamiento).
- Validación con LLMs de otros proveedores (GPT, Gemini) — este protocolo mide participantes
  humanos, no la generalización de pbi-context a otros modelos de IA.

**Actualización (2026-07-23):** `docs/answer_quality_gemini_report.md` corrió calidad de
respuesta con Gemini real (function calling) sobre este mismo set de 20 preguntas — 70/90/95% de
precisión en A/B/C. No reemplaza esta validación humana, que sigue bloqueada en reclutamiento sin
relación con esto; sí cierra el hueco de "un solo proveedor" que el bullet de arriba señala, para
el eje de calidad de respuesta (con Gemini, todavía no con GPT).
