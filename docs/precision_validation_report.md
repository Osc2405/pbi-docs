# Informe de Validación de Precisión — Horizonte 3 (proxy automatizado)

**Fecha:** 2026-07-15
**Modelo de referencia:** `files_test/Supply Chain Sample.pbip` (7 tablas, 4 measures, 2 relaciones)
**Motivación:** `docs/Analisis_Posicionamiento_Comparativa_Plan_Futuro.md`, sección 6, identifica la
validación de precisión con usuarios reales como el "próximo paso crítico" y advierte
explícitamente: *"la evidencia de precisión y tiempo es más valiosa que las métricas de tokens"*.
Este informe no reemplaza ese experimento con humanos (10-15 desarrolladores, según el diseño
original) — es un proxy automatizado que opera la misma hipótesis usando agentes de IA aislados
en vez de testers humanos, algo que sí puedo ejecutar directamente.

---

## 1. Resumen ejecutivo

Se armó un set fijo de **18 preguntas objetivamente calificables** (respuesta exacta conocida de
antemano, extraída de `metadata.json`) y se las hizo responder a **tres agentes completamente
aislados entre sí** (sin memoria compartida, sin ver las otras condiciones), cada uno limitado a
una única fuente de contexto:

- **Condición A — TMDL crudo:** los 10 archivos `.tmdl` reales del modelo.
- **Condición B — JSON de pbi-docs:** los 7 `tables/*.json` + `relationships.json` ya procesados.
- **Condición C — MCP/resolver acotado:** sin archivos precargados, solo `pbi-docs --query` bajo
  demanda, pregunta por pregunta.

**Resultado: B y C respondieron 18/18 correctamente. A respondió 16/18** — los 2 fallos no fueron
errores, fueron `NOT_FOUND` honestos en preguntas sobre la *categoría* de una measure (revenue/
cost/percentage/ratio/...), un campo que **no existe en el TMDL crudo en absoluto** — es un
enriquecimiento que pbi-docs calcula, no algo que Power BI almacena. Es un hallazgo estructural,
no anecdótico: hay preguntas que TMDL crudo no puede responder sin importar cuánto contexto se le
dé, y pbi-docs sí puede.

En bytes de contexto realmente cargados para responder las 18 preguntas: **A 25,518 bytes → B
12,082 (-52.7%) → C 4,314 (-83.1% vs A, -64.3% vs B)**. Ver sección 5 para un matiz honesto sobre
esta comparación a nivel de tokens totales de la conversación.

Durante el experimento se encontró y corrigió un **bug real**: `resolver.py` tenía `get_measure()`
y `search_columns()` (usadas por el servidor MCP) pero nunca se habían expuesto como flags de
`--query` en `cli.py` — ver sección 4.

---

## 2. Metodología

### 2.1. Preguntas

18 preguntas de dificultad variada (fácil/media/difícil; conteos, hechos puntuales, relaciones,
búsquedas cruzadas entre tablas, y 2 preguntas trampa deliberadas: un format-string vacío y una
measure que no existe). Respuestas de referencia calculadas por mí de antemano leyendo
`metadata.json` directamente — no generadas ni vistas por los agentes evaluados.

### 2.2. Aislamiento

Cada condición corrió como un **subagente separado** (Task tool, tipo `general-purpose`, sin
historial de conversación compartido) con instrucciones explícitas de no usar ninguna fuente de
información fuera de la asignada, y de responder `NOT_FOUND` en vez de adivinar. Esto es necesario
para validez: si el mismo agente respondiera las tres condiciones en la misma conversación, ya
sabría las respuestas de la condición A al llegar a B y C, invalidando la comparación.

### 2.3. Calificación

Comparación objetiva contra la respuesta de referencia (no hay juez LLM ni calificación
subjetiva) — exacta o por contenido semántico equivalente cuando la pregunta lo permite (ej. "Yes"
vs "Yes — is_technical: true" cuentan igual).

---

## 3. Resultados de precisión

| Condición | Correctas | Incorrectas | Tasa |
| :--- | :---: | :---: | :---: |
| A — TMDL crudo | 16/18 | 2 (`NOT_FOUND` honesto, ver abajo) | 88.9% |
| B — JSON pbi-docs | 18/18 | 0 | **100%** |
| C — MCP/resolver acotado | 18/18 | 0 | **100%** |

Los 2 "fallos" de A fueron **Q13** ("¿qué categoría tiene la measure '% on time orders'?") y
**Q15** ("listá las measures de categoría 'ratio'") — en ambos casos el agente correctamente
identificó que el TMDL crudo no contiene ningún campo de categoría y respondió `NOT_FOUND` en vez
de inventar una respuesta. Esto **no es un error de precisión, es un límite estructural del
formato fuente**: `categorizer.py` es lo que le agrega esa categoría al modelo — Power BI/TMDL no
la tiene. B y C, al consumir el output ya enriquecido por pbi-docs, respondieron ambas
correctamente.

Nota adicional: A necesitó *inferencia* correcta pero no trivial en 2 preguntas más (Q7 — inferir
que una relación está activa por la *ausencia* de una línea `isActive: false`; Q11 — inferir que
una tabla es "técnica" por el patrón de nombre `DateTableTemplate_<GUID>`) — el agente acertó en
ambas, pero tuvo que razonar sobre convenciones del formato en vez de leer un campo explícito
(`is_active: true` / `is_technical: true` en B y C).

---

## 4. Resultados de contexto (bytes)

| Condición | Bytes de contexto usados | Ahorro vs A |
| :--- | ---: | ---: |
| A — TMDL crudo (10 archivos, carga completa) | 25,518 | — |
| B — JSON pbi-docs (8 archivos, carga completa) | 12,082 | -52.7% |
| C — MCP/resolver (12 queries acotadas, solo lo necesario) | 4,314 | -83.1% |

Los valores de A y B son fijos (ambas condiciones cargan todo el archivo por adelantado,
consistente con la metodología de `docs/token_optimization_report.md`). C es acumulativo: la suma
de cada respuesta de `--query` efectivamente usada — el agente decidió qué pedir pregunta por
pregunta, sin cargar nada de más.

**Bug real encontrado en este paso:** la primera corrida de C falló al usar `--search-columns` y
`--measure` — existían en `resolver.py` (y en las 6 tools del servidor MCP) pero nunca se habían
conectado a `cli.py --query`. El agente lo detectó solo (leyó el mensaje de error de argparse) y
compensó cargando tablas completas de más. Se corrigió `cli.py` (2 flags nuevos: `--measure`,
`--search-columns`) y se repitió la condición C — la cifra de 4,314 bytes de la tabla de arriba es
de la corrida corregida, no de la handicapeada. 2 tests nuevos agregados
(`test_cli_query_measure`, `test_cli_query_search_columns`), 161/161 tests pasando.

---

## 5. Matiz honesto: tokens de contexto vs. tokens totales de conversación

Los bytes de la sección 4 miden **solo el contenido de la fuente de datos** — no el costo total de
la conversación del agente (su propio razonamiento, cada ida y vuelta de herramienta, mi prompt de
18 preguntas, etc.). El harness también capturó el conteo real de tokens por subagente:

| Condición | Tokens totales del subagente | Llamadas a herramientas |
| :--- | ---: | ---: |
| A — TMDL crudo | 57,240 | 10 |
| B — JSON pbi-docs | 46,322 | 8 |
| C — MCP/resolver acotado | 49,394 | 15 |

A nivel de bytes-de-fuente, C gana por un margen enorme (-83% vs A). A nivel de tokens totales de
la conversación, la ventaja **se reduce considerablemente** — porque C pagó el costo de **12
idas y vueltas de herramienta** (una por cada consulta `--query` distinta), mientras que A y B
cargaron todo con 7-8 llamadas grandes de una sola vez. Cada llamada a herramienta tiene overhead
fijo (protocolo, formato de respuesta) que no depende del tamaño del dato pedido.

**Esto no invalida la propuesta de valor de C, la matiza:** este experimento hizo 18 preguntas de
una sola pasada, un caso de uso poco realista (stress-test deliberado). Una pregunta real de
usuario en un turno de chat típico necesita 1-3 consultas acotadas, no 12 — en ese escenario
realista, la ventaja de bytes-de-fuente de C (-83%) sí se traduce directamente en tokens totales
más bajos, porque el overhead fijo de pocas llamadas es marginal. El hallazgo correcto no es
"MCP/resolver siempre gana en tokens totales", es: **MCP/resolver gana decisivamente cuando el
patrón de uso es preguntas puntuales (el caso común); la ventaja se diluye si un agente hace muchas
consultas pequeñas en una sola sesión en vez de pocas más dirigidas.**

---

## 6. Limitaciones de este experimento

- **No reemplaza la validación con usuarios humanos** que pide la sección 6 del análisis de
  posicionamiento — mide si un agente de IA (Claude, vía subagentes) puede responder
  correctamente, no si un desarrollador humano real llega más rápido o con más confianza a la
  respuesta correcta usando cada condición.
- **Un solo modelo, chico** (7 tablas). El documento original propone un modelo mediano (10-15
  tablas, 30-50 measures) — a esa escala, tanto la brecha de precisión (si aparece) como la
  brecha de tokens serían más pronunciadas y más representativas.
- **Un solo tipo de agente** (Claude, vía subagentes del mismo proveedor que ejecuta este
  informe) — no valida generalización a otros LLMs (GPT, Gemini, etc.), aunque pbi-docs es
  agnóstico por diseño (JSON plano, sin dependencia de ningún SDK de un proveedor). Ver también
  `docs/token_optimization_report.md` — paso parcial adyacente (soporte Gemini agregado a
  `scripts/count_tokens.py` para conteo real de tokens con un segundo tokenizador; no valida
  calidad de respuesta con otro proveedor, esta limitación sigue abierta).

  **Actualización (2026-07-23):** `docs/answer_quality_gemini_report.md` corrió el eje de calidad
  de respuesta (no solo tokens) con un segundo proveedor real — Gemini, function calling real
  contra `resolver.py`, no subagentes — sobre `Sales Sample.pbip` (11 tablas), no
  `Supply Chain Sample.pbip` (7 tablas) usado en este informe, así que no es una comparación 1:1
  con la tabla de la sección 3, es una medición nueva e independiente. Resultado: 70%/90%/95% de
  precisión en A/B/C, con Condición C ganando en precisión Y en tokens a la vez. Cierra esta
  limitación de "un solo proveedor" para el eje de calidad de respuesta — sigue faltando GPT y
  cualquier otro proveedor más allá de Claude y Gemini.
- **18 preguntas curadas a mano**, no generadas por un tercero independiente — mitigado por
  calificación objetiva (no hay juicio subjetivo de un LLM), pero el conjunto de preguntas en sí
  podría tener sesgos hacia lo que pbi-docs modela bien.

---

## 7. Conclusión

La hipótesis central de Horizonte 3 — que el contexto acotado no sacrifica precisión — **se
sostiene en esta corrida**: B y C empataron en 100% de precisión, superando a A (88.9%, con los
2 "fallos" siendo en realidad límites estructurales del TMDL crudo, no errores). La ventaja de
tokens de C es real y grande quando se mide en bytes de fuente cargados (-83% vs A), pero se
diluye a nivel de conversación completa cuando el patrón de uso implica muchas consultas pequeñas en
una sola sesión — un matiz que vale la pena comunicar con honestidad en vez de solo citar la cifra
más favorable.

Como bonus, el experimento encontró y corrigió un bug de producto real (`--search-columns` y
`--measure` no expuestos en la CLI) que una revisión de código no había detectado — evidencia a
favor de correr este tipo de evaluación de forma recurrente, no solo una vez.
