# Plan de implementación del hito 4: respuestas fundamentadas con citas verificables

- Estado: implementado; aceptación en vivo pendiente por credenciales del proveedor
- Fecha: 2026-08-13; estado actualizado 2026-08-21
- Hito objetivo: 4
- Dependencia funcional: hito 3 completo
- Alcance del documento: backend, frontend, proveedor de generación, seguridad,
  evaluación, pruebas, operación local y criterios de aceptación

## 1. Resultado esperado

Al terminar este hito, una persona podrá formular una pregunta sobre los documentos
indexados y recibir uno de tres resultados explícitos:

1. Una respuesta compuesta por afirmaciones respaldadas, cada una enlazada a uno o más
   pasajes recuperados.
2. Un resultado `insufficient_evidence` cuando el corpus recuperado no permita responder.
3. Un resultado `safety_refused` cuando el proveedor rechace la solicitud por seguridad.

Cada cita deberá identificar el documento, nombre del archivo, página, chunk y offsets
exactos, mostrar el pasaje usado y permitir abrir el PDF almacenado en la página
correspondiente. El servidor será responsable de resolver las citas; el modelo nunca
podrá inventar identificadores de documentos, URLs ni metadatos de procedencia.

El hito no se considerará completo por el solo hecho de obtener texto de un modelo. Se
considerará completo cuando:

- los contratos de respuesta y rechazo estén implementados;
- ninguna afirmación aceptada carezca de una cita resoluble;
- el modelo sólo reciba la pregunta y los chunks recuperados;
- los errores del proveedor sean estados visibles y no respuestas vacías;
- las evaluaciones de recuperación y generación estén separadas;
- la aplicación siga funcionando localmente para ingestión y búsqueda aunque no exista
  una API key;
- un flujo real de navegador haya sido verificado de extremo a extremo.

## 2. Línea de base que no se debe romper

El hito 3 ya estableció invariantes que el hito 4 debe reutilizar:

- Los PDFs y sidecars JSON son la fuente de verdad de ingestión.
- `knowledge.db` es un índice derivado y reconstruible.
- Cada chunk pertenece a una única página.
- Cada chunk conserva `document_id`, `page_number`, `chunk_index`, `start_offset` y
  `end_offset`.
- La recuperación usa SQLite FTS5/BM25 y devuelve rangos, no una respuesta.
- La entrada de búsqueda se convierte a tokens citados; no se ejecuta sintaxis FTS
  suministrada por el cliente.
- El índice puede buscar globalmente o dentro de un documento.
- El backend usa dataclasses inmutables para el dominio y Pydantic para HTTP.
- Los errores usan un único envelope y códigos estables.
- El frontend valida la forma de todas las respuestas antes de renderizarlas.
- `make check` representa los mismos gates que CI.

La implementación nueva debe componerse sobre estos contratos. No debe duplicar el
chunking, leer sidecars directamente para responder ni introducir un segundo motor de
recuperación.

## 3. Alcance

### 3.1 Incluido

- `POST /answers` como caso de uso síncrono y sin estado conversacional.
- Recuperación interna de hasta cinco evidencias por pregunta.
- Alcance global o limitado a un `document_id`.
- Un puerto `AnswerGenerator` y un adaptador inicial para OpenAI.
- OpenAI Responses API con salida estructurada validada con Pydantic.
- Afirmaciones con referencias a IDs efímeros de evidencia.
- Resolución de referencias a citas completas realizada por el servidor.
- Rechazo determinista cuando no se recupera evidencia.
- Rechazo decidido por el generador cuando la evidencia recuperada no es suficiente o
  es contradictoria.
- Tratamiento explícito de rechazos de seguridad del proveedor.
- `GET /documents/{document_id}/content` para abrir el PDF fuente.
- Interfaz de preguntas, respuesta por afirmaciones y tarjetas de cita.
- Dataset versionado de evaluación de respuestas.
- Evaluación reproducible de estructura, capacidad de rechazo, citas y cobertura de
  hechos.
- Pruebas unitarias, de contrato HTTP, de componente y un smoke test real opt-in.
- Documentación de configuración local y de la transferencia de datos al proveedor.

### 3.2 Fuera de alcance

- Historial de conversación o preguntas multi-turno.
- Persistencia de preguntas, respuestas o citas.
- Streaming de tokens.
- OCR.
- Embeddings, búsqueda semántica o recuperación híbrida.
- Reranking con otro modelo.
- Herramientas web, file search, code interpreter o function calling.
- Subida del PDF al proveedor; sólo se enviarán los chunks recuperados.
- Autenticación, autorización, multi-tenancy o aislamiento por usuario.
- Colas, workers o generación en background.
- Feedback de usuario, dashboards y cálculo monetario completo; pertenecen al hito 5.
- Soporte offline mediante un modelo local.
- Promesas de cumplimiento regulatorio. La aplicación sigue siendo local y de
  desarrollo.

## 4. Decisiones arquitectónicas

Las decisiones marcadas como **aceptadas** forman parte del alcance del hito. Las
marcadas como **condicionadas por evidencia** tienen un método de cierre definido y no
habilitan cambios arbitrarios de arquitectura.

| ID | Decisión | Estado | Motivo |
| --- | --- | --- | --- |
| D1 | Exponer `POST /answers`, una pregunta por request | Aceptada | Es el caso de uso mínimo y evita introducir un modelo de conversación inexistente. |
| D2 | La API de respuestas recupera su propia evidencia | Aceptada | El cliente no debe elegir ni alterar el contexto que supuestamente fundamenta la respuesta. |
| D3 | Mantener SQLite FTS5 como retrieval del hito | Aceptada | Ya tiene procedencia y evaluación; cambiar retrieval y generación al mismo tiempo impediría atribuir regresiones. |
| D4 | Usar un puerto estrecho `AnswerGenerator` | Aceptada | Aísla la única frontera volátil y externa sin crear una arquitectura de plugins especulativa. |
| D5 | Implementar primero un adaptador OpenAI Responses API | Aceptada | Es la API recomendada actualmente para generación de texto y admite salida estructurada. |
| D6 | Pedir al proveedor una estructura de afirmaciones y `evidence_ids` | Aceptada | Una cadena con marcadores libres es difícil de validar y permite referencias inventadas. |
| D7 | Resolver todas las citas en el servidor | Aceptada | El modelo sólo conoce IDs efímeros `E1...En`; los metadatos confiables vienen del retrieval. |
| D8 | No hacer streaming en este hito | Aceptada | La salida completa debe validarse antes de mostrar una sola afirmación. |
| D9 | No persistir respuestas | Aceptada | Sin identidad ni historial, la persistencia agrega datos sensibles y problemas de ciclo de vida sin valor para el slice. |
| D10 | No agregar el estado de documento `ready` | Aceptada | La disponibilidad para responder combina `indexed` con configuración/salud del proveedor; no es una transición durable del documento. |
| D11 | Mantener funcional la API sin API key | Aceptada | Upload, extracción, indexación y retrieval no deben caer por una capacidad opcional no configurada. |
| D12 | Devolver `503 generation_not_configured` sólo al invocar respuestas sin proveedor | Aceptada | Hace visible la configuración faltante sin convertir liveness en readiness. |
| D13 | Abrir el PDF local mediante un endpoint read-only | Aceptada | Una página y un excerpt son atribuibles; el PDF accesible vuelve la cita verificable por la persona. |
| D14 | No aplicar un umbral absoluto a BM25 | Aceptada | El score no está calibrado ni se expone; un número arbitrario simularía confianza. |
| D15 | Cero matches implica rechazo sin llamada al proveedor | Aceptada | Es determinista, más barato y evita pedir al modelo una respuesta sin contexto. |
| D16 | Con matches, el generador puede devolver `insufficient_evidence` | Aceptada | FTS puede recuperar coincidencias lexicales irrelevantes; recuperar algo no significa poder responder. |
| D17 | Enviar `store=false` y no habilitar herramientas | Aceptada | Minimiza estado del proveedor y mantiene el límite “sólo evidencia local recuperada”. |
| D18 | No registrar pregunta, prompt, respuesta ni texto de evidencia | Aceptada | Evita convertir logs locales en una copia inadvertida de documentos o datos personales. |
| D19 | Elegir y fijar el modelo exacto después de la evaluación comparativa | Condicionada por evidencia | La arquitectura no debe depender de una preferencia de modelo; disponibilidad, costo, latencia y calidad se miden. |
| D20 | Preferir un snapshot del modelo cuando esté disponible | Condicionada por evidencia | La reproducibilidad mejora si el proveedor ofrece un identificador versionado accesible al proyecto. |

## 5. Arquitectura objetivo

~~~
Browser
  |
  | POST /answers { question, document_id? }
  v
FastAPI answers/router.py
  |
  | transport -> domain
  v
AnswerService
  |                          no matches
  | EvidenceRetriever  --------------------> insufficient_evidence
  |        |
  |        v
  |  SQLite FTS5 -> RetrievalMatch[0..5]
  |
  | assign E1..En + build untrusted evidence payload
  v
AnswerGenerator port
  |
  v
OpenAI adapter -> Responses API -> structured ProviderAnswer
  |
  v
domain validation
  |
  | resolve E1..En against original RetrievalMatch objects
  v
GroundedAnswer + trusted Citation objects
  |
  v
HTTP schema -> frontend validation -> answer claims + citation cards
                                         |
                                         v
                         GET /documents/{id}/content#page=N
~~~

### 5.1 Dirección de dependencias

La dirección permitida será:

~~~
HTTP router -> application service -> domain + ports
provider adapter ---------------------> domain + ports
retrieval adapter --------------------> existing retrieval service
HTTP schemas -------------------------> domain
domain -------------------------------> standard library only
~~~

No se permiten estas dependencias:

- `domain.py` importando FastAPI, Pydantic, el SDK de OpenAI o SQLite.
- El router invocando directamente el SDK.
- El adaptador de OpenAI leyendo `Request`, devolviendo `JSONResponse` o construyendo
  citas HTTP.
- El frontend suministrando chunks al backend.
- El servicio de respuestas consultando tablas FTS directamente.

## 6. Flujo completo

1. Pydantic valida que `question` tenga entre 2 y 500 caracteres.
2. El servicio normaliza espacios exteriores, pero conserva el contenido de la
   pregunta.
3. Se comprueba que el generador esté configurado. Si falta key o modelo, se devuelve
   `503 generation_not_configured` antes de producir un outcome de negocio.
4. Si existe `document_id`, se carga el documento:
   - ID inexistente: `404 document_not_found`;
   - estado distinto de `indexed`: `409 document_not_indexed`;
   - `indexed`: continúa.
5. Se recuperan hasta `AKP_ANSWER_EVIDENCE_LIMIT` chunks. El cliente no controla este
   límite.
6. Si no hay matches, se devuelve `200 insufficient_evidence` y no se realiza una
   request al proveedor.
7. Se asignan IDs efímeros `E1`, `E2`, etc. en el orden del ranking.
8. Se construye un payload JSON con pregunta y evidencia. El JSON se serializa; no se
   interpolan delimitadores controlados por el documento.
9. El adaptador invoca al proveedor con:
   - instrucciones estables y versionadas en código;
   - salida estructurada;
   - sin herramientas;
   - sin estado conversacional;
   - `store=false`;
   - timeout y retry acotados.
10. El adaptador convierte el resultado externo a tipos internos:
   - respuesta estructurada válida;
   - rechazo de seguridad;
   - timeout;
   - error transitorio o permanente;
   - salida ausente/incompleta.
11. El servicio valida invariantes semánticos adicionales.
12. Si el resultado es `answered`, cada `evidence_id` se resuelve contra el mapa
    construido antes de la llamada.
13. Una referencia inexistente, una afirmación sin evidencia o una estructura
    contradictoria invalida la respuesta completa; nunca se entrega parcialmente.
14. Las evidencias usadas se convierten a citas confiables y se deduplican en orden de
    primera aparición.
15. El router serializa el resultado.
16. El frontend vuelve a validar el payload y sólo entonces lo renderiza.

## 7. Contrato HTTP

### 7.1 Request

`POST /answers`

~~~json
{
  "question": "How soon must a lost company device be reported?",
  "document_id": null
}
~~~

Reglas:

- `question`: string, mínimo 2 y máximo 500 caracteres.
- `document_id`: UUID opcional.
- No se aceptan `model`, `prompt`, `temperature`, `limit`, chunks ni URLs.
- Los campos adicionales se rechazarán con `extra="forbid"` en este contrato. Esto
  evita que un cliente crea que está controlando parámetros que la API ignora.

### 7.2 Respuesta contestada

~~~json
{
  "question": "How soon must a lost company device be reported?",
  "outcome": "answered",
  "claims": [
    {
      "text": "A lost company device must be reported to the Security team within one hour.",
      "citation_ids": ["C1"]
    }
  ],
  "citations": [
    {
      "id": "C1",
      "document_id": "22222222-2222-4222-8222-222222222222",
      "filename": "security-runbook.pdf",
      "page_number": 1,
      "chunk_index": 0,
      "start_offset": 0,
      "end_offset": 145,
      "excerpt": "A lost company device must be reported to the Security team within one hour...",
      "source_path": "/documents/22222222-2222-4222-8222-222222222222/content"
    }
  ]
}
~~~

Se evita duplicar `answer` como string y `claims` como estructura. Las afirmaciones son
la respuesta. El frontend puede presentarlas como párrafos y agregar marcadores de cita
sin mantener dos representaciones que puedan divergir.

### 7.3 Evidencia insuficiente

~~~json
{
  "question": "What is the parental leave policy?",
  "outcome": "insufficient_evidence",
  "claims": [],
  "citations": []
}
~~~

Es un `200`, no un error técnico. La operación funcionó y determinó que no debe
responder.

### 7.4 Rechazo de seguridad

~~~json
{
  "question": "...",
  "outcome": "safety_refused",
  "claims": [],
  "citations": []
}
~~~

La UI mostrará copy propio y estable. No se expondrá directamente texto arbitrario del
proveedor.

### 7.5 PDF fuente

`GET /documents/{document_id}/content`

- Carga primero el metadata sidecar para validar existencia.
- Resuelve el path únicamente a partir del UUID.
- Responde `application/pdf`.
- Usa `Content-Disposition: inline` con el nombre original sólo como metadata.
- Nunca acepta una ruta o filename del cliente.
- Devuelve `404 document_not_found` si el documento no existe.
- Devuelve `500 internal_error` si el metadata existe pero el PDF falta o es inválido.

El frontend construirá:

~~~
${API_BASE_URL}${sourcePath}#page=${pageNumber}
~~~

Se verificará en los navegadores objetivo que el visor respete `#page=N`. Si un visor
ignora el fragmento, el fallback seguirá abriendo el PDF y la tarjeta conservará el
número de página.

## 8. Modelo de dominio

Los nombres son orientativos pero las responsabilidades son obligatorias.

~~~python
class AnswerOutcome(StrEnum):
    ANSWERED = "answered"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    SAFETY_REFUSED = "safety_refused"


@dataclass(frozen=True, slots=True)
class Evidence:
    id: str
    match: RetrievalMatch


@dataclass(frozen=True, slots=True)
class GeneratedClaim:
    text: str
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class GenerationResult:
    outcome: AnswerOutcome
    claims: tuple[GeneratedClaim, ...]


@dataclass(frozen=True, slots=True)
class Citation:
    id: str
    document_id: UUID
    filename: str
    page_number: int
    chunk_index: int
    text: str
    start_offset: int
    end_offset: int


@dataclass(frozen=True, slots=True)
class GroundedClaim:
    text: str
    citation_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class GroundedAnswer:
    question: str
    outcome: AnswerOutcome
    claims: tuple[GroundedClaim, ...]
    citations: tuple[Citation, ...]
~~~

### 8.1 Invariantes

Para `answered`:

- debe existir entre 1 y 5 afirmaciones;
- cada texto debe ser no vacío y tener un máximo definido;
- cada afirmación debe tener entre 1 y 3 `evidence_ids`;
- todos los IDs deben existir en la evidencia suministrada;
- los IDs repetidos dentro de una afirmación se deduplican conservando orden;
- cada cita publicada debe ser usada por al menos una afirmación;
- ningún metadata de cita se toma del resultado del proveedor.

Para `insufficient_evidence` y `safety_refused`:

- `claims` debe estar vacío;
- `citations` debe estar vacío.

Una respuesta que mezcle `insufficient_evidence` con afirmaciones es inválida. Una
respuesta `answered` sin citas es inválida. Esas situaciones son `502
generation_invalid_response`, no evidencia insuficiente: el proveedor incumplió el
contrato.

## 9. Puerto del generador

Sólo se abstraerá la frontera que realmente cambia:

~~~python
class AnswerGenerator(Protocol):
    async def generate(
        self,
        *,
        question: str,
        evidence: tuple[Evidence, ...],
    ) -> GenerationResult: ...
~~~

No se implementará:

- un registro dinámico de proveedores;
- descubrimiento de plugins;
- una jerarquía de clases base;
- factories genéricas con strings arbitrarios;
- un adapter para un segundo proveedor “por si acaso”.

El fake de pruebas implementará el mismo protocolo. Si en el futuro un modelo local o
otro proveedor demuestra valor, se agregará como un segundo adapter sin cambiar el
servicio de aplicación.

## 10. Integración con OpenAI

### 10.1 API

Se usará la Responses API. La documentación oficial recomienda Responses sobre Chat
Completions para aplicaciones nuevas de generación de texto. La salida se solicitará
con `responses.parse(..., text_format=ProviderAnswer)` y modelos Pydantic.

Structured Outputs asegura la forma JSON declarada, pero no reemplaza:

- el tratamiento específico de rechazos de seguridad;
- la comprobación de resultados incompletos;
- la resolución de IDs;
- las invariantes entre outcome y claims;
- la evaluación de soporte semántico.

Fuentes oficiales:

- [Text generation](https://developers.openai.com/api/docs/guides/text)
- [Structured model outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
- [Data controls in the OpenAI platform](https://developers.openai.com/api/docs/guides/your-data)

### 10.2 Modelo exacto

El modelo no se importará ni codificará en el dominio. Se configurará mediante
`AKP_OPENAI_MODEL`.

Proceso de selección:

1. Elegir dos candidatos vigentes que soporten Responses y Structured Outputs: uno
   optimizado por costo/latencia y otro por calidad.
2. Ejecutar el mismo dataset con la misma configuración.
3. Comparar gates de calidad, p50/p95 observados, tokens y costo estimado.
4. Elegir el modelo más económico que cumpla todos los gates.
5. Fijar un snapshot si el proveedor ofrece uno accesible.
6. Registrar modelo, snapshot, fecha y métricas en `docs/progress/day-04.md`.

La selección de modelo es una decisión operativa medible, no una dependencia
arquitectónica. Cambiarla obliga a reejecutar la evaluación de respuestas, pero no a
modificar el servicio.

### 10.3 Dependencia y ciclo de vida

- Agregar el SDK oficial `openai` a `services/api/pyproject.toml`.
- Determinar el lower bound mínimo con un spike que ejecute `responses.parse` async.
- Fijar la versión resuelta en `uv.lock`.
- Crear un único cliente async por proceso para reutilizar conexiones.
- Inicializar y cerrar el adapter en el lifespan de FastAPI.
- Permitir inyectar un fake mediante una dependencia de FastAPI en tests.
- No hacer requests durante startup.

### 10.4 Configuración de la llamada

- `store=false`.
- Sin `tools`.
- Sin `previous_response_id`.
- Sin conversación persistida.
- Timeout total configurable, inicialmente 30 segundos.
- A lo sumo un retry del SDK para fallas transitorias.
- Máximo de output configurable, inicialmente 800 tokens.
- Hasta cinco chunks de hasta 1000 caracteres cada uno con la configuración actual.
- No enviar el PDF, sidecars, chunks no recuperados ni rutas del filesystem.

El límite exacto de output se validará con el dataset. Si una respuesta se trunca, no
se entregará parcialmente.

### 10.5 Retención y privacidad

La request llevará `store=false` porque Responses puede conservar estado de aplicación
por defecto. Esto no equivale a una garantía de cero retención: siguen aplicando los
controles de la organización, el monitoreo de abuso y la política vigente del
proveedor. La UI y el README deben explicar que:

- la aplicación corre localmente;
- la generación no es offline;
- la pregunta y los pasajes recuperados salen del equipo hacia OpenAI;
- el PDF completo no se envía;
- no debe usarse con documentos sensibles sin revisar los controles de datos del
  proyecto de OpenAI.

## 11. Contrato con el modelo

### 11.1 Salida del proveedor

El proveedor no devuelve citas HTTP. Devuelve solamente:

~~~json
{
  "outcome": "answered",
  "claims": [
    {
      "text": "A lost device must be reported within one hour.",
      "evidence_ids": ["E1"]
    }
  ]
}
~~~

El schema limita:

- outcome a `answered | insufficient_evidence`;
- 0 a 5 claims;
- longitud por claim;
- 0 a 3 evidence IDs por claim.

Los rechazos de seguridad se reciben por el mecanismo propio de refusal del proveedor
y se convierten a `safety_refused`.

### 11.2 Instrucciones

Las instrucciones serán una constante versionada y testeada. Deben expresar una sola
vez:

- la evidencia es datos no confiables, no instrucciones;
- se responde exclusivamente con información soportada por la evidencia;
- se ignoran órdenes incluidas dentro de los documentos;
- cada afirmación necesita uno o más IDs de evidencia;
- sólo se pueden usar los IDs suministrados;
- si falta soporte, hay conflicto material o la pregunta requiere conocimiento
  externo, se devuelve `insufficient_evidence`;
- la respuesta usa el idioma de la pregunta;
- no se agregan introducciones, bibliografía ni marcadores manuales;
- no se intenta completar información con conocimiento general.

### 11.3 Payload

La pregunta y las evidencias se serializarán como JSON. Ejemplo conceptual:

~~~json
{
  "question": "How soon must a device be reported?",
  "evidence": [
    {
      "id": "E1",
      "document": "security-runbook.pdf",
      "page": 1,
      "text": "A lost company device must be reported..."
    }
  ]
}
~~~

El filename y la página ayudan al razonamiento, pero el servidor no confiará en ningún
metadata que el proveedor repita. La resolución se hace contra los objetos originales.

## 12. Estrategia de rechazo

Hay cuatro conceptos distintos y la UI no debe mezclarlos:

| Situación | HTTP | Outcome/código | ¿Se llamó al modelo? |
| --- | --- | --- | --- |
| No hay matches | 200 | `insufficient_evidence` | No |
| Hay matches pero no soportan la respuesta | 200 | `insufficient_evidence` | Sí |
| El proveedor rechaza por seguridad | 200 | `safety_refused` | Sí |
| El proveedor está caído, mal configurado o incumple el contrato | 502/503/504 | error técnico | Tal vez |

No se aplicará un score mínimo de BM25 en runtime. Para incorporar un gate previo más
sofisticado deberá existir primero un score calibrado y una evaluación que demuestre
mejor precisión de rechazo sin degradar respuestas válidas.

No se reemplazará una falla técnica por `insufficient_evidence`: hacerlo escondería
incidentes y convertiría disponibilidad en una afirmación de calidad.

## 13. Citas verificables

### 13.1 Garantías del servidor

El servidor puede garantizar:

- que cada citation ID existe;
- que cada cita corresponde a un chunk recuperado para esa request;
- que documento, página, chunk y offsets coinciden con el índice;
- que el excerpt publicado es el texto recuperado;
- que cada afirmación tiene al menos una cita;
- que el PDF fuente puede abrirse.

El servidor no puede garantizar sólo con estructura:

- que la cita realmente implique toda la afirmación;
- que el PDF original sea verdadero;
- que la extracción del PDF no haya perdido diseño o contexto visual;
- que el top-k contenga toda la evidencia relevante.

Las últimas propiedades se abordan con evaluación, UX honesta y mejoras futuras de
retrieval, no con nombres más optimistas.

### 13.2 Identidad

- `E1...En`: IDs privados del request hacia el proveedor.
- `C1...Cn`: IDs públicos de la respuesta, asignados por primera aparición.
- Los IDs no se persisten ni son estables entre requests.
- La identidad durable sigue siendo
  `(document_id, page_number, chunk_index, start_offset, end_offset)`.

### 13.3 Presentación

Cada marcador de cita debe:

- ser navegable por teclado;
- enlazar con una tarjeta de evidencia en la misma vista;
- mostrar filename y página en texto visible;
- ofrecer “Open source PDF” en una pestaña nueva;
- incluir `rel="noreferrer"` si se usa `target="_blank"`;
- no depender sólo del color.

## 14. Organización del código

Estructura propuesta:

~~~
services/api/src/ai_knowledge_platform/
├── answers/
│   ├── __init__.py
│   ├── domain.py              tipos inmutables e invariantes
│   ├── ports.py               AnswerGenerator
│   ├── service.py             orquestación retrieve -> generate -> resolve
│   ├── prompt.py              instrucciones y serialización del payload
│   ├── openai_generator.py    adapter del SDK y traducción de errores
│   ├── schemas.py             request/response HTTP
│   ├── router.py              POST /answers
│   └── evaluation.py          runner de respuestas
├── documents/
│   └── router.py              GET /documents/{id}/content
├── retrieval/
│   └── service.py             se reutiliza; no se duplica
└── main.py                    lifespan, dependency wiring, router

apps/web/
├── app/
│   ├── grounded-answer.tsx
│   ├── grounded-answer.module.css
│   ├── grounded-answer.test.tsx
│   └── page.tsx
└── lib/
    ├── api.ts
    └── api.test.ts

services/api/evals/
└── answers_v1.json

docs/
├── adr/
│   └── 0005-structured-grounded-answer-pipeline.md
└── progress/
    └── day-04.md
~~~

Si un archivo supera una responsabilidad clara durante la implementación, se divide.
No se crearán directorios `utils`, `helpers` o `common`: ocultan ownership y tienden a
acumular dependencias no relacionadas.

## 15. Criterios de clean code

### 15.1 Nombres y contratos

- Usar nombres del dominio: `Evidence`, `GroundedClaim`, `Citation`,
  `GenerationResult`.
- Evitar nombres genéricos como `Data`, `ResultManager`, `AIService` o `process`.
- Una función pública debe expresar una acción completa: `answer_question`,
  `resolve_citations`, `generate`.
- Los códigos de error son parte del contrato público y no se reutilizan para causas
  distintas.

### 15.2 Funciones

- El router valida transporte y delega.
- El servicio orquesta; no formatea JSON ni conoce el SDK.
- La construcción del prompt es pura.
- La resolución de citas es pura y testeable.
- La traducción de excepciones del SDK vive en el adapter.
- No capturar `Exception` salvo en la frontera donde se traduce a una categoría
  estable; nunca perder cancellation.

### 15.3 Tipos e inmutabilidad

- Dataclasses `frozen=True, slots=True` en dominio.
- Pydantic sólo en configuración, HTTP, schema del proveedor y datasets.
- Uniones discriminadas para outcomes cuando mejoren la exhaustividad.
- `tuple` en dominio y `list` en JSON.
- `SecretStr` para API keys.
- `mypy --strict` debe seguir pasando sin `Any` propagado desde el SDK.

### 15.4 Errores como datos explícitos

- Resultados de negocio (`insufficient_evidence`, `safety_refused`) son valores.
- Fallas técnicas son excepciones traducidas al envelope HTTP.
- El frontend sigue usando `ApiResult<T>`; ninguna vista depende de excepciones de
  `fetch`.
- Los mensajes inesperados del proveedor no se renderizan directamente.

### 15.5 Abstracción proporcional

Se aplica arquitectura limpia en fronteras con valor:

- dominio separado de transporte;
- puerto para el proveedor externo;
- adapter para retrieval existente;
- inyección de dependencias para tests.

No se busca una arquitectura “pura” a costa del slice:

- no se reescribe el módulo de retrieval;
- no se agrega un contenedor DI;
- no se crea un repository para respuestas que no se persisten;
- no se generaliza para múltiples LLMs antes de tener un segundo caso real.

## 16. Configuración

Variables nuevas propuestas:

| Variable | Default | Regla |
| --- | --- | --- |
| `AKP_OPENAI_API_KEY` | vacío | Secreto opcional para arrancar; requerido al usar `/answers`. |
| `AKP_OPENAI_MODEL` | vacío | Requerido junto con la key; se fija luego de la evaluación. |
| `AKP_ANSWER_EVIDENCE_LIMIT` | `5` | Entero entre 1 y 10; el cliente no lo sobrescribe. |
| `AKP_ANSWER_MAX_OUTPUT_TOKENS` | `800` | Entero positivo con límite superior razonable. |
| `AKP_ANSWER_TIMEOUT_SECONDS` | `30` | Timeout total positivo. |

Reglas:

- Key sin modelo o modelo sin key es configuración incompleta para generación.
- La aplicación puede iniciar, pero `/answers` devuelve
  `generation_not_configured`.
- Nunca se imprime la key, ni siquiera en representaciones de `Settings`.
- `.env.example` contiene el nombre de la variable, nunca un secreto.
- El frontend no recibe la key ni el model ID.
- La URL base del proveedor no será configurable en este hito; evita convertir una
  variable aparentemente inocua en una vía de exfiltración.

## 17. Errores

Nuevos códigos:

| Código | HTTP | Significado |
| --- | --- | --- |
| `document_not_indexed` | 409 | El scope solicitado existe pero no está indexado. |
| `generation_not_configured` | 503 | Falta key o modelo. |
| `generation_timeout` | 504 | El proveedor no terminó dentro del límite. |
| `generation_provider_error` | 502 | El proveedor respondió con error o conexión fallida no clasificada como timeout. |
| `generation_invalid_response` | 502 | Salida ausente, truncada o contraria a invariantes. |

Los errores de autenticación del proveedor no se traducen a un 401 hacia el usuario:
la credencial es del servidor, por lo que se reportan como `502
generation_provider_error` con copy que indica revisar la configuración del API.

Los detalles sensibles de la excepción externa se registran sólo de forma sanitizada:
tipo de error, status externo, request ID externo si existe, modelo y duración. Nunca
body, headers de autorización, prompt o evidencia.

## 18. Seguridad

### 18.1 Prompt injection en documentos

Los documentos son datos no confiables aunque el usuario los considere “trusted”.
Controles:

- instrucciones de sistema separadas;
- evidencia serializada como JSON;
- orden explícita de ignorar instrucciones dentro de evidencia;
- ninguna herramienta disponible para el modelo;
- ningún secreto incluido en el prompt;
- salida restringida a claims e IDs;
- IDs resueltos contra un allowlist creado por request;
- casos adversariales en evaluación.

Esto reduce el impacto, pero no “soluciona” prompt injection. El riesgo residual se
documenta.

### 18.2 Acceso a PDFs

`GET /documents/{id}/content` es aceptable sólo mientras la aplicación sea local y sin
usuarios. Antes de desplegar:

- autenticación y autorización deben envolver upload, retrieval, answers y content;
- el tenant debe formar parte de todas las claves e índices;
- CORS no se considera un control de acceso;
- los IDs UUID no se consideran secretos.

### 18.3 Abuso y costo

Para el hito local:

- longitud de pregunta limitada;
- top-k y output acotados por servidor;
- un retry máximo;
- sin tools ni loops;
- sin endpoint batch;
- sin parámetros de modelo controlados por cliente.

Rate limiting y cuotas por usuario se difieren hasta que exista identidad. Si se
despliega antes, se convierte en un blocker y no en una mejora opcional.

### 18.4 Contenido activo

- Las afirmaciones se renderizan como texto React, no `dangerouslySetInnerHTML`.
- Los excerpts se renderizan como texto.
- `source_path` se valida y deriva del UUID.
- No se aceptan URLs devueltas por el modelo.

## 19. Frontend y experiencia de uso

### 19.1 Ubicación

La nueva sección “Ask grounded questions” irá después de la ingestión y antes de
“Retrieval only”. La búsqueda de evidencia existente se conserva como superficie de
diagnóstico: ayuda a distinguir una falla de retrieval de una decisión del generador.

### 19.2 Máquina de estados

~~~typescript
type AnswerState =
  | { status: "idle" }
  | { status: "answering"; question: string }
  | { status: "answered"; response: GroundedAnswer }
  | { status: "insufficient"; question: string }
  | { status: "safetyRefused"; question: string }
  | { status: "error"; message: string };
~~~

No se representa “searching” y “generating” como dos requests del navegador: el
backend posee el caso de uso atómico. La UI puede mostrar “Finding evidence and
checking an answer…” sin inventar progreso porcentual.

### 19.3 Render

Respuesta:

- encabezado con la pregunta;
- cada claim como párrafo;
- marcadores `[1]`, `[2]` navegables;
- lista “Sources” con filename, página y excerpt;
- link al PDF;
- label visible “Generated only from retrieved evidence”.

Evidencia insuficiente:

- texto directo: el sistema no encontró soporte suficiente;
- recomendación de probar otros términos o indexar otra fuente;
- nunca una respuesta aproximada.

Error:

- `role="alert"`;
- mantiene el texto de la pregunta para reintentar;
- distingue configuración, timeout y proveedor.

Accesibilidad:

- `aria-busy` en el form;
- live region para el progreso;
- foco al resultado sólo en éxito de negocio;
- fallo mantiene el foco útil;
- `aria-disabled` conserva el patrón de la UI actual;
- los marcadores de cita tienen nombre accesible, por ejemplo
  “Source 1, security-runbook.pdf, page 1”.

### 19.4 Validación del payload

`apps/web/lib/api.ts` debe comprobar:

- outcome conocido;
- arrays presentes;
- claims no vacíos sólo en `answered`;
- IDs de cita únicos;
- todos los `citationIds` resuelven;
- UUID/string, páginas, chunks y offsets válidos;
- `sourcePath` con el patrón exacto de documentos;
- ninguna cita no utilizada;
- invariantes vacías de outcomes sin respuesta.

Si falla una comprobación, la UI usa copy propio `unexpected_error` y no muestra una
respuesta parcial.

## 20. Evaluación

### 20.1 Separación de calidad

Se mantendrán dos evaluaciones:

1. Retrieval: “¿llegó la página correcta al top-k?”
2. Answer: “dada la evidencia recuperada, ¿respondió, rechazó y citó correctamente?”

Mezclarlas ocultaría la causa. Un answer incorrecto con retrieval correcto es una
falla de generación. Un rechazo con la página relevante ausente es una falla de
retrieval.

### 20.2 Dataset `answers_v1.json`

El dataset será versionado y contendrá, como mínimo:

- 6 preguntas contestables de una página;
- 2 preguntas que requieren dos evidencias;
- 3 preguntas no contestables;
- 1 pregunta con una coincidencia lexical irrelevante;
- 1 documento con una instrucción adversarial dentro de su texto;
- casos en inglés y español;
- respuestas esperadas como hechos atómicos, no como una única redacción;
- páginas aceptables por hecho;
- términos o afirmaciones prohibidas cuando sean relevantes.

Schema conceptual:

~~~json
{
  "schema_version": 1,
  "name": "answers-v1-grounded-policy",
  "documents": [],
  "cases": [
    {
      "id": "lost-device-window",
      "question": "How soon must a lost device be reported?",
      "expected_outcome": "answered",
      "required_facts": [
        {
          "id": "reporting-window",
          "concepts": [["one hour", "within an hour"]],
          "acceptable_pages": [
            {
              "document_id": "22222222-2222-4222-8222-222222222222",
              "page_number": 1
            }
          ]
        }
      ]
    }
  ]
}
~~~

Los `concepts` permiten alternativas controladas sin exigir una oración literal. El
runner valida el schema aun cuando no exista una API key.

### 20.3 Métricas bloqueantes

Métricas deterministas:

- outcome accuracy: answered vs insufficient;
- citation validity: referencias resolubles;
- citation completeness: porcentaje de claims con citas;
- citation page correctness: citas en páginas aceptables para los hechos cubiertos;
- required fact coverage: hechos esperados presentes mediante alternativas
  normalizadas;
- forbidden fact rate;
- provider error rate durante el run.

Gates iniciales para el dataset pequeño:

| Métrica | Gate |
| --- | --- |
| Citation validity | `1.00` |
| Citation completeness | `1.00` |
| Answerable outcome accuracy | `1.00` |
| Unanswerable refusal accuracy | `1.00` |
| Citation page correctness | `>= 0.95` |
| Required fact coverage | `>= 0.90` |
| Forbidden fact rate | `0.00` |
| Provider error rate | `0.00` en el run de aceptación |

Con pocos casos, un promedio puede esconder un fallo importante. El reporte también
lista resultados por caso y los casos adversariales son must-pass.

### 20.4 Fidelidad semántica

Los checks lexicales no demuestran por sí solos que una afirmación esté implicada por
su cita. Para el hito 4:

- todas las respuestas del dataset v1 reciben una revisión humana con una rúbrica
  binaria de soporte;
- el reporte conserva pregunta, claims, citas y decisión, pero no se commitea si
  contiene documentos reales;
- un judge LLM puede agregarse como señal diagnóstica, nunca como único gate;
- el mismo modelo generador no se usa como juez único de su propia salida.

La rúbrica pregunta:

1. ¿Cada claim está plenamente soportado por sus citas?
2. ¿La respuesta agrega una condición o causalidad ausente?
3. ¿Omite un hecho necesario para no inducir a error?
4. ¿El rechazo fue correcto?

### 20.5 CI y evaluación live

- CI no llama proveedores pagos ni depende de red.
- `make check` ejecuta unit tests, contract tests y validación del dataset.
- `make eval-answers` es opt-in, requiere key/model y genera un reporte.
- El hito no se declara completo hasta ejecutar ese comando contra el modelo fijado y
  registrar las métricas agregadas en `day-04.md`.
- Cambiar prompt, modelo, chunking, top-k o schema obliga a reejecutar la evaluación
  live.

## 21. Estrategia de pruebas

### 21.1 Dominio

- asignación determinista de `E1...En`;
- resolución de un ID válido;
- deduplicación preservando orden;
- rechazo de ID desconocido;
- rechazo de claim sin IDs;
- rechazo de `answered` sin claims;
- rechazo de outcome vacío con claims;
- citas derivadas exactamente de `RetrievalMatch`;
- una evidencia usada por varios claims produce una sola cita.

### 21.2 Servicio de aplicación

Con retriever y generator fake:

- cero matches no invoca generator;
- top-k respeta settings;
- `document_id` se propaga;
- documento inexistente;
- documento no indexado;
- respuesta válida;
- insuficiencia decidida por generador;
- safety refusal;
- generador inválido;
- orden de claims y citas;
- la pregunta se conserva en la respuesta.

### 21.3 Adapter OpenAI

Sin red, mockeando la superficie del SDK:

- request lleva `store=false`;
- request no lleva tools;
- input contiene sólo pregunta y evidencia permitida;
- parseo de structured output;
- refusal;
- timeout;
- 401/429/5xx;
- output incompleto;
- SDK devuelve `None`;
- detalles sensibles no aparecen en errores.

No se mockeará internamente Pydantic ni la resolución de citas.

### 21.4 HTTP

- schema de request;
- campos extra rechazados;
- todos los outcomes 200;
- todos los errores usan envelope;
- OpenAPI documenta respuestas;
- PDF inline exitoso;
- PDF inexistente;
- metadata sin PDF;
- Content-Type y filename;
- dependency override del generator.

### 21.5 Frontend

- request y parseo de los tres outcomes;
- payload malformado;
- claim con citation ID inexistente;
- resultado answer mueve foco;
- insufficient y safety copy;
- error conserva pregunta;
- estado pending evita doble submit;
- marcadores accesibles;
- link al PDF y página;
- múltiples claims compartiendo cita;
- excerpts se renderizan como texto.

### 21.6 Integración local

Flujo real:

1. iniciar API y web;
2. subir PDF;
3. extraer;
4. indexar;
5. hacer una pregunta contestable;
6. verificar answer y cita;
7. abrir PDF en la página;
8. hacer pregunta no contestable;
9. verificar rechazo;
10. inspeccionar consola del browser y logs sanitizados.

La prueba live usa una key explícita del entorno. Nunca escribe el secreto ni persiste
el answer.

## 22. Plan de implementación por fases

### Fase 0 — Spike y ADR

Objetivo: cerrar la única incertidumbre externa antes de tocar el flujo de producto.

- agregar temporalmente el SDK mediante el flujo normal de dependencias;
- verificar `AsyncOpenAI.responses.parse` con Pydantic;
- verificar refusal, timeout, `store=false` y cierre del cliente;
- comparar dos modelos sobre 3 a 5 casos representativos;
- elegir modelo inicial o documentar por qué el ID queda requerido por configuración;
- crear ADR 5 con el pipeline estructurado y la decisión de no persistencia/streaming.

Gate:

- spike reproducible;
- no secretos en git;
- decisión de modelo registrada con evidencia.

### Fase 1 — Dominio y servicio puros

- crear `answers/domain.py`;
- crear `answers/ports.py`;
- implementar construcción de evidencias;
- implementar resolución de citas;
- implementar outcomes e invariantes;
- implementar `answer_question` con fakes;
- agregar códigos de error.

Gate:

- tests puros cubren todas las invariantes;
- sin imports de FastAPI/SDK en dominio;
- mypy strict.

### Fase 2 — Contrato HTTP y PDF fuente

- schemas request/response;
- `POST /answers`;
- `GET /documents/{id}/content`;
- OpenAPI responses;
- validación de scope indexado;
- tests HTTP.

Inicialmente el endpoint de answers usa un fake inyectado. Esto permite estabilizar el
contrato antes de agregar red.

Gate:

- contrato completo probado;
- PDFs abribles;
- error envelope consistente.

### Fase 3 — Adapter del proveedor

- prompt y payload;
- adapter async;
- lifespan;
- configuración opcional;
- traducción de errores;
- `store=false`;
- tests mock del SDK.

Gate:

- sin llamadas reales en tests;
- API arranca sin key;
- key ausente afecta sólo `/answers`;
- una llamada live manual parsea output estructurado.

### Fase 4 — Frontend

- tipos y parser runtime;
- cliente `answerQuestion`;
- componente y estilos;
- outcomes y accesibilidad;
- tarjetas y links a source;
- conservar panel de retrieval.

Gate:

- tests de componente y API client;
- build de producción;
- navegación por teclado.

### Fase 5 — Evaluación

- dataset v1;
- runner;
- métricas y gates;
- `make eval-answers`;
- validación de dataset en CI;
- run comparativo final;
- revisión humana de fidelidad.

Gate:

- todos los hard gates;
- cero respuesta no soportada en casos adversariales;
- modelo/snapshot fijado.

### Fase 6 — Documentación y aceptación

- actualizar README: estado, arquitectura, configuración, privacidad y roadmap;
- actualizar ADR 2 para aclarar por qué `indexed` sigue siendo el estado terminal del
  documento;
- documentar ADR 5;
- crear `docs/progress/day-04.md`;
- ejecutar `make check`;
- ejecutar `make eval-answers`;
- smoke test real de navegador;
- verificar `git diff --check` y dependency audits.

Gate:

- definición de terminado completa.

## 23. Orden de cambios y commits recomendado

Para mantener cambios revisables:

1. `feat(api): add grounded answer domain and contracts`
2. `feat(api): integrate structured OpenAI answer generation`
3. `feat(web): render grounded answers and source citations`
4. `test(evals): add answer quality evaluation`
5. `docs: record milestone 4 architecture and results`

Si el trabajo se entrega en un único commit, el mensaje recomendado será:

~~~
feat: add grounded answers with verifiable citations
~~~

No se debe mezclar una migración de retrieval, autenticación o despliegue en estos
commits.

## 24. Compatibilidad y migraciones

- No cambia el schema SQLite v1.
- No se persisten tablas de respuestas.
- Los endpoints existentes son compatibles.
- `DocumentStatus` no cambia.
- Se agregan variables opcionales.
- Se agregan rutas y códigos de error.
- El frontend debe aceptar el vocabulario existente sin nuevos estados.
- Los artefactos locales actuales siguen siendo válidos.

Si se cambia chunking o retrieval durante el hito por una corrección inevitable:

1. se incrementa la versión de schema o algoritmo correspondiente;
2. se reconstruye el índice derivado;
3. se reejecutan retrieval eval y answer eval;
4. se documenta como una decisión separada.

## 25. Operación y recuperación de fallas

### 25.1 Proveedor no configurado

- API/web arrancan.
- Ingestión y retrieval funcionan.
- Answer muestra configuración faltante.
- No hay retry automático infinito.

### 25.2 Timeout o rate limit

- Request termina con error estable.
- La persona puede reintentar manualmente.
- No se muestra output parcial.
- La ingestión previa no cambia.

### 25.3 Proceso reiniciado

- No hay answer job que recuperar.
- Los documentos e índice permanecen.
- La siguiente pregunta inicia una operación nueva.

### 25.4 Rollback

El feature es aditivo:

- se puede retirar el router de answers y el componente sin migrar datos;
- se puede mantener el endpoint de content para citations/retrieval;
- se puede quitar el SDK y variables sin tocar PDFs o SQLite;
- no hay estados de documento que revertir.

## 26. Riesgos y mitigaciones

| Riesgo | Impacto | Mitigación del hito |
| --- | --- | --- |
| FTS recupera evidencia lexical pero irrelevante | Respuesta falsa | El generador puede rechazar; dataset con false friends; no asumir match=answer. |
| El modelo cita un ID válido que no soporta el claim | Falsa sensación de confianza | Claims estructurados, evaluación por página y revisión humana de soporte. |
| Prompt injection dentro del PDF | Manipulación de salida | Evidencia no confiable, JSON, sin tools/secrets, allowlist de IDs, casos adversariales. |
| Modelo o alias cambia | Regresión silenciosa | Snapshot cuando exista; eval obligatoria al cambiar ID/prompt. |
| API key falta o vence | Feature caída | 503 localizado; resto de la app sigue operativo. |
| Retención externa de datos | Privacidad | `store=false`, mínima evidencia, aviso claro y revisión de controles del proyecto. |
| El visor PDF ignora `#page` | Verificación menos directa | Página visible en cita y fallback al PDF completo. |
| Output truncado | JSON/claims incompletos | Límite medido, detección y 502; sin render parcial. |
| Retry duplica costo | Costo/latencia | Un retry máximo sólo en fallas transitorias. |
| Dataset demasiado pequeño | Métricas engañosas | Casos adversariales must-pass, resultados por caso y crecimiento versionado. |
| Abstracción excesiva | Demora y código ceremonial | Un puerto, un adapter, sin registry ni persistencia. |

## 27. Alternativas descartadas

### Llamar al modelo desde el router

Descartado porque mezcla HTTP, prompt, proveedor, recuperación y validación; impide
tests puros y vuelve cada error una rama del endpoint.

### Permitir que el frontend envíe los chunks

Descartado porque un cliente podría omitir, alterar o fabricar evidencia manteniendo
una respuesta aparentemente “citada”.

### Pedir una respuesta Markdown con `[1]`

Descartado porque parsear marcadores libres es frágil: faltan IDs, sobran referencias
y no existe una relación estructural por afirmación.

### Generar una respuesta y buscar citas después

Descartado porque la atribución post-hoc puede encontrar texto parecido sin haber
fundamentado la generación.

### Persistir chat y respuestas

Descartado porque multiplica responsabilidades de identidad, retención, borrado,
schema y UX sin ser necesario para demostrar grounding.

### Streaming

Descartado porque una afirmación no validada podría aparecer antes de descubrir una
cita inválida. Puede revisitarse con buffering server-side en un hito posterior.

### Enviar el PDF completo a file search

Descartado porque duplica ingestión e índice, reduce control sobre procedencia y envía
más datos de los necesarios.

### Agregar embeddings ahora

Descartado porque cambiar simultáneamente retrieval y generation vuelve imposible
diagnosticar la fuente de una mejora o regresión.

### Usar el score BM25 como “confidence”

Descartado porque no es una probabilidad calibrada y el índice actual deliberadamente
no expone ese score como contrato.

### Fallar el startup sin API key

Descartado porque el proveedor no es necesario para upload, extracción, indexación o
búsqueda.

### Soporte genérico multi-provider desde el primer día

Descartado porque un protocolo estrecho ya protege el caso de uso; factories, registros
y configuración polimórfica serían especulación.

## 28. Decisiones que requieren evidencia antes de cerrar

No son preguntas abiertas de arquitectura; son parámetros que deben medirse:

1. Modelo y snapshot exactos.
2. Timeout definitivo.
3. Máximo de output.
4. Si top-5 supera top-3 en cobertura sin degradar rechazo.
5. Copy final de insufficient/safety.
6. Si el visor local respeta `#page=N` en los navegadores verificados.

Cada una se cierra con el dataset, una prueba de navegador o una medición de operación.
Ninguna requiere rediseñar los límites definidos en este documento.

## 29. Definición de terminado

Arquitectura:

- [ ] Existe el puerto `AnswerGenerator`.
- [ ] Dominio no importa framework ni SDK.
- [ ] Router, servicio y adapter tienen responsabilidades separadas.
- [ ] No existe persistencia de answers ni estado `ready`.

Backend:

- [ ] `POST /answers` implementado.
- [ ] `GET /documents/{id}/content` implementado.
- [ ] Outcomes e invariantes validados.
- [ ] Citas resueltas sólo desde retrieval.
- [ ] OpenAI adapter async con Structured Outputs.
- [ ] `store=false`, sin tools y con límites.
- [ ] Errores estables y sanitizados.
- [ ] API inicia sin key.

Frontend:

- [ ] Form de pregunta y todos los estados.
- [ ] Claims con citas navegables.
- [ ] Tarjetas con excerpt y link al PDF.
- [ ] Payload validado antes de render.
- [ ] Accesibilidad cubierta por tests.

Calidad:

- [ ] Unit, HTTP y frontend tests.
- [ ] Dataset answer v1.
- [ ] Gates deterministas aprobados.
- [ ] Revisión humana de fidelidad aprobada.
- [ ] Retrieval eval sigue aprobando.
- [ ] `make check` aprobado.
- [ ] `make eval-answers` aprobado con modelo registrado.
- [ ] Smoke test real sin errores de consola.

Documentación:

- [ ] ADR 2 actualizado.
- [ ] ADR 5 aceptado.
- [ ] README actualizado sin sobrepromesas.
- [ ] `.env.example` documentado.
- [ ] `day-04.md` registra resultados reales.
- [ ] Privacidad y limitaciones explicadas.

## 30. Próxima acción concreta

Comenzar por la Fase 0, no por la UI:

1. Crear una rama `codex/milestone-04-grounded-answers`.
2. Ejecutar un spike mínimo del SDK contra Responses API con salida Pydantic.
3. Probar dos modelos con tres casos answerable y dos unanswerable.
4. Registrar modelo, snapshot, timeout, tokens y resultados.
5. Convertir este plan en ADR 5 con las decisiones externas cerradas.
6. Implementar dominio y resolución de citas con fakes antes de hacer la integración
   real.

Ese orden reduce el riesgo principal —la frontera externa y su contrato— sin acoplar el
resto del producto a una prueba exploratoria.
