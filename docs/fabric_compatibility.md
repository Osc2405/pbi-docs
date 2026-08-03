# Informe de Compatibilidad — Microsoft Fabric (modelos semánticos TMDL)

**Fecha:** 2026-07-31
**Estado: 🟡 Compatibilidad esperada, NO validada empíricamente.**

Este informe es distinto en naturaleza a `docs/pbip_validation_report.md`: aquel documenta una
corrida real del pipeline contra un export PBIP real, con bugs encontrados y corregidos. Este
documento **no** tiene una corrida real detrás — no hay acceso a un export real de un modelo
semántico de Microsoft Fabric en este entorno de desarrollo. Lo que sigue es una evaluación de
compatibilidad esperada por inspección de código y de la especificación pública de TMDL, marcada
explícitamente como tal para no confundirla con una validación. Mismo tratamiento que ya reciben
otros bloqueos externos de este proyecto (`docs/human_validation_protocol.md`, conteo real de
tokens vía Anthropic en `docs/token_optimization_report.md`): documentar el bloqueo en vez de
simular el resultado.

---

## 1. Por qué se espera compatibilidad

Los modelos semánticos de Microsoft Fabric y los proyectos PBIP de Power BI Desktop/Service
comparten el mismo formato de definición: TMDL (Tabular Model Definition Language). Fuentes
públicas consultadas (Microsoft Learn, 2026-07-31):

- [SemanticModel definition — Fabric REST APIs](https://learn.microsoft.com/en-us/rest/api/fabric/articles/item-management/definitions/semantic-model-definition) —
  confirma que la definición de un semantic model en Fabric usa TMDL o TMSL (no ambos a la vez),
  con TMDL como formato por defecto.
- [Power BI Desktop projects (PBIP) — overview](https://learn.microsoft.com/en-us/power-bi/developer/projects/projects-overview) —
  describe la misma gramática TMDL que consume `pbi_extractor/pbip_extractor.py`.
- [Use TMDL view in Power BI](https://learn.microsoft.com/en-us/power-bi/transform-model/desktop-tmdl-view) —
  documenta la sintaxis (indentación por tabs, bloques `table`/`column`/`measure`) que el parser
  de este repo ya soporta.

`pbip_extractor.py` parsea la gramática TMDL general — bloques `table`/`column`/`measure`/
`relationship` con indentación por tabs — sin depender de ningún artefacto específico de Power BI
Desktop. `find_semantic_model()` no requiere `.platform`/`.pbi` para localizar el
`.SemanticModel/`, y los tolera si faltan o difieren; un export de Fabric vía Git integration debería
producir una carpeta `.SemanticModel/definition/` equivalente en estructura.

## 2. Riesgos identificados por inspección de código (no probados)

- **Particiones en modo `directLake`** (exclusivo de Fabric, sin archivo de partición de import
  detrás — lee directamente de OneLake). El parser actual solo cuenta
  `partition_count = len(partitions)` (`pbip_extractor.py` → `processor.py`), sin ramificar sobre
  el modo de partición (`import`/`directLake`/`directQuery`) — debería ser robusto sin cambios de
  código, pero es una expectativa razonada por lectura del código, no una prueba contra un
  `mode: directLake` real.
- **Anotaciones/metadatos específicos de Fabric** (si existieran) que el parser no reconozca:
  ya hay precedente de "degradación elegante" para constructos no soportados (anotaciones,
  jerarquías, páginas de reporte se saltan silenciosamente, ver `CLAUDE.md` sección 1) — el
  comportamiento esperado ante algo nuevo de Fabric sería el mismo (ignorar, no fallar), pero no
  hay forma de confirmarlo sin un export real.

## 3. Qué se necesita para cerrar esto de verdad

Un export real de un modelo semántico de Fabric — vía Git integration de un workspace Fabric
(produce la misma estructura `.SemanticModel/definition/*.tmdl` que PBIP) — corrido contra el
pipeline completo (`pbi-context -i <carpeta> -o <salida>`), documentando el resultado con el mismo
formato que `docs/pbip_validation_report.md` (bugs encontrados, si los hay; estado final;
alcance). Hasta entonces, este documento permanece en estado 🟡, no ✅.

## 4. Qué NO se afirma

Este documento no afirma que `pbi-context` funcione contra Fabric — afirma que hay una base pública
razonable para esperar que funcione, y documenta exactamente qué falta para confirmarlo. No usar
esta nota como evidencia de soporte probado en comunicación externa (README, marketing) sin
aclarar el matiz "esperado, no validado".
