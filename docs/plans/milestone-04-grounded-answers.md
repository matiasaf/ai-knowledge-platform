# Milestone 4 implementation plan: grounded answers with verifiable citations

- Status: implemented; live acceptance pending provider credentials
- Date: 2026-08-13; status updated 2026-08-21
- Target milestone: 4
- Functional dependency: milestone 3 complete
- Document scope: backend, frontend, generation provider, security, evaluation,
  testing, local operation and acceptance criteria

## 1. Expected outcome

When this milestone is complete, a person will be able to ask a question about the
indexed documents and receive one of three explicit outcomes:

1. An answer made of supported claims, each linked to one or more retrieved passages.
2. An `insufficient_evidence` outcome when the retrieved corpus does not allow an
   answer.
3. A `safety_refused` outcome when the provider refuses the request for safety reasons.

Each citation must identify the document, filename, page, chunk and exact offsets, show
the passage used and allow opening the stored PDF at the corresponding page. The server
is responsible for resolving citations; the model can never invent document
identifiers, URLs or provenance metadata.

The milestone will not be considered complete merely because a model returned text. It
will be considered complete when:

- the answer and refusal contracts are implemented;
- no accepted claim lacks a resolvable citation;
- the model receives only the question and the retrieved chunks;
- provider errors are visible states, not empty answers;
- retrieval and generation evaluations are separate;
- the application keeps working locally for ingestion and search even without an API
  key;
- a real browser flow has been verified end to end.

## 2. Baseline that must not break

Milestone 3 already established invariants that milestone 4 must reuse:

- PDFs and JSON sidecars are the ingestion source of truth.
- `knowledge.db` is a derived, rebuildable index.
- Every chunk belongs to exactly one page.
- Every chunk keeps `document_id`, `page_number`, `chunk_index`, `start_offset` and
  `end_offset`.
- Retrieval uses SQLite FTS5/BM25 and returns rankings, not an answer.
- Search input is converted into quoted tokens; client-supplied FTS syntax is never
  executed.
- The index can search globally or within one document.
- The backend uses immutable dataclasses for the domain and Pydantic for HTTP.
- Errors use a single envelope and stable codes.
- The frontend validates the shape of every response before rendering it.
- `make check` represents the same gates as CI.

The new implementation must compose on top of these contracts. It must not duplicate
chunking, read sidecars directly to answer, or introduce a second retrieval engine.

## 3. Scope

### 3.1 Included

- `POST /answers` as a synchronous use case with no conversational state.
- Internal retrieval of up to five pieces of evidence per question.
- Global scope or scope limited to one `document_id`.
- An `AnswerGenerator` port and an initial OpenAI adapter.
- OpenAI Responses API with structured output validated by Pydantic.
- Claims that reference ephemeral evidence IDs.
- Server-side resolution of references into complete citations.
- Deterministic refusal when no evidence is retrieved.
- Generator-decided refusal when the retrieved evidence is insufficient or
  contradictory.
- Explicit handling of provider safety refusals.
- `GET /documents/{document_id}/content` to open the source PDF.
- A question interface, claim-by-claim answer and citation cards.
- A versioned answer evaluation dataset.
- Reproducible evaluation of structure, refusal ability, citations and fact coverage.
- Unit, HTTP contract and component tests, plus an opt-in real smoke test.
- Documentation of local configuration and of the data transferred to the provider.

### 3.2 Out of scope

- Conversation history or multi-turn questions.
- Persistence of questions, answers or citations.
- Token streaming.
- OCR.
- Embeddings, semantic search or hybrid retrieval.
- Reranking with another model.
- Web tools, file search, code interpreter or function calling.
- Uploading the PDF to the provider; only the retrieved chunks are sent.
- Authentication, authorization, multi-tenancy or per-user isolation.
- Queues, workers or background generation.
- User feedback, dashboards and full monetary cost calculation; they belong to
  milestone 5.
- Offline support through a local model.
- Regulatory compliance promises. The application remains local and for development.

## 4. Architectural decisions

Decisions marked **accepted** are part of the milestone scope. Decisions marked
**evidence-gated** have a defined closing method and do not authorize arbitrary
architecture changes.

| ID | Decision | Status | Rationale |
| --- | --- | --- | --- |
| D1 | Expose `POST /answers`, one question per request | Accepted | It is the minimal use case and avoids introducing a conversation model that does not exist. |
| D2 | The answers API retrieves its own evidence | Accepted | The client must not choose or alter the context that supposedly grounds the answer. |
| D3 | Keep SQLite FTS5 as this milestone's retrieval | Accepted | It already has provenance and evaluation; changing retrieval and generation at the same time would make regressions impossible to attribute. |
| D4 | Use a narrow `AnswerGenerator` port | Accepted | It isolates the only volatile, external boundary without creating a speculative plugin architecture. |
| D5 | Implement an OpenAI Responses API adapter first | Accepted | It is the currently recommended API for text generation and supports structured output. |
| D6 | Ask the provider for a structure of claims and `evidence_ids` | Accepted | A string with free-form markers is hard to validate and allows invented references. |
| D7 | Resolve every citation on the server | Accepted | The model only knows ephemeral IDs `E1...En`; trusted metadata comes from retrieval. |
| D8 | No streaming in this milestone | Accepted | The complete output must be validated before a single claim is shown. |
| D9 | Do not persist answers | Accepted | Without identity or history, persistence adds sensitive data and lifecycle problems with no value for the slice. |
| D10 | Do not add the `ready` document status | Accepted | Answer availability combines `indexed` with provider configuration/health; it is not a durable document transition. |
| D11 | Keep the API functional without an API key | Accepted | Upload, extraction, indexing and retrieval must not fail because an optional capability is not configured. |
| D12 | Return `503 generation_not_configured` only when answers are invoked without a provider | Accepted | It makes the missing configuration visible without turning liveness into readiness. |
| D13 | Open the local PDF through a read-only endpoint | Accepted | A page and an excerpt are attributable; an accessible PDF makes the citation verifiable by a person. |
| D14 | Do not apply an absolute threshold to BM25 | Accepted | The score is neither calibrated nor exposed; an arbitrary number would simulate confidence. |
| D15 | Zero matches means refusal without calling the provider | Accepted | It is deterministic, cheaper and avoids asking the model for an answer without context. |
| D16 | With matches, the generator may return `insufficient_evidence` | Accepted | FTS can retrieve irrelevant lexical matches; retrieving something does not mean being able to answer. |
| D17 | Send `store=false` and enable no tools | Accepted | It minimizes provider state and keeps the "only retrieved local evidence" boundary. |
| D18 | Do not log the question, prompt, answer or evidence text | Accepted | It avoids turning local logs into an inadvertent copy of documents or personal data. |
| D19 | Choose and pin the exact model after the comparative evaluation | Evidence-gated | The architecture must not depend on a model preference; availability, cost, latency and quality are measured. |
| D20 | Prefer a model snapshot when one is available | Evidence-gated | Reproducibility improves if the provider offers a versioned identifier accessible to the project. |

## 5. Target architecture

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

### 5.1 Dependency direction

The allowed direction is:

~~~
HTTP router -> application service -> domain + ports
provider adapter ---------------------> domain + ports
retrieval adapter --------------------> existing retrieval service
HTTP schemas -------------------------> domain
domain -------------------------------> standard library only
~~~

These dependencies are not allowed:

- `domain.py` importing FastAPI, Pydantic, the OpenAI SDK or SQLite.
- The router invoking the SDK directly.
- The OpenAI adapter reading `Request`, returning `JSONResponse` or building HTTP
  citations.
- The frontend supplying chunks to the backend.
- The answers service querying FTS tables directly.

## 6. Complete flow

1. Pydantic validates that `question` has between 2 and 500 characters.
2. The service normalizes surrounding whitespace but preserves the question content.
3. It checks that the generator is configured. If the key or model is missing, it
   returns `503 generation_not_configured` before producing a business outcome.
4. If a `document_id` is present, the document is loaded:
   - unknown ID: `404 document_not_found`;
   - status other than `indexed`: `409 document_not_indexed`;
   - `indexed`: continue.
5. Up to `AKP_ANSWER_EVIDENCE_LIMIT` chunks are retrieved. The client does not control
   this limit.
6. If there are no matches, it returns `200 insufficient_evidence` and makes no
   provider request.
7. Ephemeral IDs `E1`, `E2`, etc. are assigned in ranking order.
8. A JSON payload with the question and evidence is built. The JSON is serialized;
   document-controlled delimiters are never interpolated.
9. The adapter calls the provider with:
   - stable instructions versioned in code;
   - structured output;
   - no tools;
   - no conversational state;
   - `store=false`;
   - bounded timeout and retry.
10. The adapter converts the external result into internal types:
   - valid structured answer;
   - safety refusal;
   - timeout;
   - transient or permanent error;
   - missing/incomplete output.
11. The service validates additional semantic invariants.
12. If the outcome is `answered`, every `evidence_id` is resolved against the map built
    before the call.
13. A nonexistent reference, a claim without evidence or a contradictory structure
    invalidates the entire answer; it is never delivered partially.
14. The evidence used is converted into trusted citations and deduplicated in order of
    first appearance.
15. The router serializes the result.
16. The frontend validates the payload again and only then renders it.

## 7. HTTP contract

### 7.1 Request

`POST /answers`

~~~json
{
  "question": "How soon must a lost company device be reported?",
  "document_id": null
}
~~~

Rules:

- `question`: string, minimum 2 and maximum 500 characters.
- `document_id`: optional UUID.
- `model`, `prompt`, `temperature`, `limit`, chunks and URLs are not accepted.
- Additional fields are rejected with `extra="forbid"` in this contract. This prevents
  a client from believing it controls parameters the API ignores.

### 7.2 Answered response

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

Duplicating `answer` as a string and `claims` as a structure is avoided. The claims are
the answer. The frontend can present them as paragraphs and add citation markers
without maintaining two representations that could diverge.

### 7.3 Insufficient evidence

~~~json
{
  "question": "What is the parental leave policy?",
  "outcome": "insufficient_evidence",
  "claims": [],
  "citations": []
}
~~~

This is a `200`, not a technical error. The operation worked and determined that it
must not answer.

### 7.4 Safety refusal

~~~json
{
  "question": "...",
  "outcome": "safety_refused",
  "claims": [],
  "citations": []
}
~~~

The UI will show its own stable copy. Arbitrary provider text will not be exposed
directly.

### 7.5 Source PDF

`GET /documents/{document_id}/content`

- Loads the metadata sidecar first to validate existence.
- Resolves the path solely from the UUID.
- Responds with `application/pdf`.
- Uses `Content-Disposition: inline` with the original name only as metadata.
- Never accepts a path or filename from the client.
- Returns `404 document_not_found` if the document does not exist.
- Returns `500 internal_error` if the metadata exists but the PDF is missing or
  invalid.

The frontend will build:

~~~
${API_BASE_URL}${sourcePath}#page=${pageNumber}
~~~

The target browsers will be checked to confirm that the viewer honors `#page=N`. If a
viewer ignores the fragment, the fallback still opens the PDF and the card keeps the
page number.

## 8. Domain model

The names are indicative but the responsibilities are mandatory.

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

### 8.1 Invariants

For `answered`:

- there must be between 1 and 5 claims;
- each text must be non-empty and have a defined maximum length;
- each claim must have between 1 and 3 `evidence_ids`;
- every ID must exist in the supplied evidence;
- repeated IDs within a claim are deduplicated, preserving order;
- every published citation must be used by at least one claim;
- no citation metadata is taken from the provider result.

For `insufficient_evidence` and `safety_refused`:

- `claims` must be empty;
- `citations` must be empty.

A response that mixes `insufficient_evidence` with claims is invalid. An `answered`
response without citations is invalid. Those situations are `502
generation_invalid_response`, not insufficient evidence: the provider broke the
contract.

## 9. Generator port

Only the boundary that actually changes will be abstracted:

~~~python
class AnswerGenerator(Protocol):
    async def generate(
        self,
        *,
        question: str,
        evidence: tuple[Evidence, ...],
    ) -> GenerationResult: ...
~~~

The following will not be implemented:

- a dynamic provider registry;
- plugin discovery;
- a base class hierarchy;
- generic factories keyed by arbitrary strings;
- an adapter for a second provider "just in case".

The test fake will implement the same protocol. If a local model or another provider
proves valuable in the future, it will be added as a second adapter without changing
the application service.

## 10. OpenAI integration

### 10.1 API

The Responses API will be used. The official documentation recommends Responses over
Chat Completions for new text generation applications. Output will be requested with
`responses.parse(..., text_format=ProviderAnswer)` and Pydantic models.

Structured Outputs guarantees the declared JSON shape, but it does not replace:

- specific handling of safety refusals;
- checks for incomplete results;
- ID resolution;
- the invariants between outcome and claims;
- evaluation of semantic support.

Official sources:

- [Text generation](https://developers.openai.com/api/docs/guides/text)
- [Structured model outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
- [Data controls in the OpenAI platform](https://developers.openai.com/api/docs/guides/your-data)

### 10.2 Exact model

The model will not be imported or hardcoded in the domain. It will be configured through
`AKP_OPENAI_MODEL`.

Selection process:

1. Choose two current candidates that support Responses and Structured Outputs: one
   optimized for cost/latency and one for quality.
2. Run the same dataset with the same configuration.
3. Compare quality gates, observed p50/p95, tokens and estimated cost.
4. Choose the cheapest model that passes every gate.
5. Pin a snapshot if the provider offers an accessible one.
6. Record the model, snapshot, date and metrics in `docs/progress/day-04.md`.

Model selection is a measurable operational decision, not an architectural dependency.
Changing it requires rerunning the answer evaluation, but not modifying the service.

### 10.3 Dependency and lifecycle

- Add the official `openai` SDK to `services/api/pyproject.toml`.
- Determine the minimum lower bound with a spike that runs async `responses.parse`.
- Pin the resolved version in `uv.lock`.
- Create a single async client per process to reuse connections.
- Initialize and close the adapter in the FastAPI lifespan.
- Allow injecting a fake through a FastAPI dependency in tests.
- Make no requests during startup.

### 10.4 Call configuration

- `store=false`.
- No `tools`.
- No `previous_response_id`.
- No persisted conversation.
- Configurable total timeout, initially 30 seconds.
- At most one SDK retry for transient failures.
- Configurable output maximum, initially 800 tokens.
- Up to five chunks of up to 1000 characters each with the current configuration.
- Do not send the PDF, sidecars, unretrieved chunks or filesystem paths.

The exact output limit will be validated with the dataset. If an answer is truncated, it
will not be delivered partially.

### 10.5 Retention and privacy

The request will carry `store=false` because Responses may keep application state by
default. This is not a zero-retention guarantee: organization controls, abuse
monitoring and the provider's current policy still apply. The UI and the README must
explain that:

- the application runs locally;
- generation is not offline;
- the question and the retrieved passages leave the machine and go to OpenAI;
- the complete PDF is not sent;
- it must not be used with sensitive documents without reviewing the OpenAI project's
  data controls.

## 11. Contract with the model

### 11.1 Provider output

The provider does not return HTTP citations. It returns only:

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

The schema limits:

- outcome to `answered | insufficient_evidence`;
- 0 to 5 claims;
- length per claim;
- 0 to 3 evidence IDs per claim.

Safety refusals are received through the provider's own refusal mechanism and converted
to `safety_refused`.

### 11.2 Instructions

The instructions will be a versioned, tested constant. They must state exactly once:

- evidence is untrusted data, not instructions;
- answers use only information supported by the evidence;
- commands contained inside documents are ignored;
- every claim needs one or more evidence IDs;
- only the supplied IDs may be used;
- if support is missing, there is a material conflict or the question requires external
  knowledge, `insufficient_evidence` is returned;
- the answer uses the language of the question;
- no introductions, bibliographies or manual markers are added;
- no attempt is made to fill in information with general knowledge.

### 11.3 Payload

The question and the evidence will be serialized as JSON. Conceptual example:

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

The filename and page help the model reason, but the server will not trust any metadata
the provider repeats. Resolution is done against the original objects.

## 12. Refusal strategy

There are four distinct concepts and the UI must not mix them:

| Situation | HTTP | Outcome/code | Was the model called? |
| --- | --- | --- | --- |
| No matches | 200 | `insufficient_evidence` | No |
| Matches exist but do not support the answer | 200 | `insufficient_evidence` | Yes |
| The provider refuses for safety reasons | 200 | `safety_refused` | Yes |
| The provider is down, misconfigured or breaks the contract | 502/503/504 | technical error | Maybe |

No minimum BM25 score will be applied at runtime. Introducing a more sophisticated
pre-generation gate first requires a calibrated score and an evaluation that
demonstrates better refusal precision without degrading valid answers.

A technical failure will not be replaced by `insufficient_evidence`: doing so would hide
incidents and turn availability into a quality claim.

## 13. Verifiable citations

### 13.1 Server guarantees

The server can guarantee:

- that every citation ID exists;
- that every citation corresponds to a chunk retrieved for that request;
- that document, page, chunk and offsets match the index;
- that the published excerpt is the retrieved text;
- that every claim has at least one citation;
- that the source PDF can be opened.

Structure alone does not let the server guarantee:

- that the citation actually entails the whole claim;
- that the original PDF is true;
- that PDF extraction did not lose layout or visual context;
- that the top-k contains all the relevant evidence.

These last properties are addressed through evaluation, honest UX and future retrieval
improvements, not through more optimistic names.

### 13.2 Identity

- `E1...En`: request-private IDs sent to the provider.
- `C1...Cn`: public response IDs, assigned by first appearance.
- The IDs are neither persisted nor stable across requests.
- Durable identity remains
  `(document_id, page_number, chunk_index, start_offset, end_offset)`.

### 13.3 Presentation

Each citation marker must:

- be keyboard navigable;
- link to an evidence card in the same view;
- show filename and page in visible text;
- offer "Open source PDF" in a new tab;
- include `rel="noreferrer"` if `target="_blank"` is used;
- not rely on color alone.

## 14. Code organization

Proposed structure:

~~~
services/api/src/ai_knowledge_platform/
├── answers/
│   ├── __init__.py
│   ├── domain.py              immutable types and invariants
│   ├── ports.py               AnswerGenerator
│   ├── service.py             retrieve -> generate -> resolve orchestration
│   ├── prompt.py              instructions and payload serialization
│   ├── openai_generator.py    SDK adapter and error translation
│   ├── schemas.py             HTTP request/response
│   ├── router.py              POST /answers
│   └── evaluation.py          answer runner
├── documents/
│   └── router.py              GET /documents/{id}/content
├── retrieval/
│   └── service.py             reused; not duplicated
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

If a file grows beyond one clear responsibility during implementation, it is split. No
`utils`, `helpers` or `common` directories will be created: they hide ownership and
tend to accumulate unrelated dependencies.

## 15. Clean code criteria

### 15.1 Names and contracts

- Use domain names: `Evidence`, `GroundedClaim`, `Citation`, `GenerationResult`.
- Avoid generic names such as `Data`, `ResultManager`, `AIService` or `process`.
- A public function must express a complete action: `answer_question`,
  `resolve_citations`, `generate`.
- Error codes are part of the public contract and are not reused for different causes.

### 15.2 Functions

- The router validates transport and delegates.
- The service orchestrates; it neither formats JSON nor knows the SDK.
- Prompt construction is pure.
- Citation resolution is pure and testable.
- Translation of SDK exceptions lives in the adapter.
- Do not catch `Exception` except at the boundary where it is translated into a stable
  category; never lose cancellation.

### 15.3 Types and immutability

- `frozen=True, slots=True` dataclasses in the domain.
- Pydantic only in configuration, HTTP, the provider schema and datasets.
- Discriminated unions for outcomes when they improve exhaustiveness.
- `tuple` in the domain and `list` in JSON.
- `SecretStr` for API keys.
- `mypy --strict` must keep passing with no `Any` propagated from the SDK.

### 15.4 Errors as explicit data

- Business outcomes (`insufficient_evidence`, `safety_refused`) are values.
- Technical failures are exceptions translated into the HTTP envelope.
- The frontend keeps using `ApiResult<T>`; no view depends on `fetch` exceptions.
- Unexpected provider messages are not rendered directly.

### 15.5 Proportional abstraction

Clean architecture is applied at boundaries where it adds value:

- domain separated from transport;
- a port for the external provider;
- an adapter for the existing retrieval;
- dependency injection for tests.

A "pure" architecture is not pursued at the expense of the slice:

- the retrieval module is not rewritten;
- no DI container is added;
- no repository is created for answers that are not persisted;
- nothing is generalized for multiple LLMs before a second real case exists.

## 16. Configuration

Proposed new variables:

| Variable | Default | Rule |
| --- | --- | --- |
| `AKP_OPENAI_API_KEY` | empty | Optional secret for startup; required when using `/answers`. |
| `AKP_OPENAI_MODEL` | empty | Required together with the key; pinned after the evaluation. |
| `AKP_ANSWER_EVIDENCE_LIMIT` | `5` | Integer between 1 and 10; the client does not override it. |
| `AKP_ANSWER_MAX_OUTPUT_TOKENS` | `800` | Positive integer with a reasonable upper bound. |
| `AKP_ANSWER_TIMEOUT_SECONDS` | `30` | Positive total timeout. |

Rules:

- A key without a model, or a model without a key, is incomplete generation
  configuration.
- The application can start, but `/answers` returns `generation_not_configured`.
- The key is never printed, not even in `Settings` representations.
- `.env.example` contains the variable name, never a secret.
- The frontend receives neither the key nor the model ID.
- The provider base URL will not be configurable in this milestone; this avoids turning
  a seemingly harmless variable into an exfiltration path.

## 17. Errors

New codes:

| Code | HTTP | Meaning |
| --- | --- | --- |
| `document_not_indexed` | 409 | The requested scope exists but is not indexed. |
| `generation_not_configured` | 503 | The key or model is missing. |
| `generation_timeout` | 504 | The provider did not finish within the limit. |
| `generation_provider_error` | 502 | The provider returned an error, or a connection failed in a way not classified as a timeout. |
| `generation_invalid_response` | 502 | Output missing, truncated or violating invariants. |

Provider authentication errors are not translated into a 401 for the user: the
credential belongs to the server, so they are reported as `502
generation_provider_error` with copy that says to check the API configuration.

Sensitive details of the external exception are logged only in sanitized form: error
type, external status, external request ID if present, model and duration. Never the
body, authorization headers, prompt or evidence.

## 18. Security

### 18.1 Prompt injection in documents

Documents are untrusted data even if the user considers them "trusted". Controls:

- separate system instructions;
- evidence serialized as JSON;
- an explicit order to ignore instructions inside evidence;
- no tools available to the model;
- no secrets included in the prompt;
- output restricted to claims and IDs;
- IDs resolved against an allowlist created per request;
- adversarial cases in the evaluation.

This reduces the impact but does not "solve" prompt injection. The residual risk is
documented.

### 18.2 Access to PDFs

`GET /documents/{id}/content` is acceptable only while the application is local and has
no users. Before deploying:

- authentication and authorization must wrap upload, retrieval, answers and content;
- the tenant must be part of every key and index;
- CORS is not considered an access control;
- UUIDs are not considered secrets.

### 18.3 Abuse and cost

For the local milestone:

- bounded question length;
- top-k and output bounded by the server;
- at most one retry;
- no tools or loops;
- no batch endpoint;
- no client-controlled model parameters.

Rate limiting and per-user quotas are deferred until identity exists. If the application
is deployed before then, they become a blocker rather than an optional improvement.

### 18.4 Active content

- Claims are rendered as React text, not `dangerouslySetInnerHTML`.
- Excerpts are rendered as text.
- `source_path` is validated and derived from the UUID.
- URLs returned by the model are not accepted.

## 19. Frontend and user experience

### 19.1 Placement

The new "Ask grounded questions" section will go after ingestion and before "Retrieval
only". The existing evidence search is kept as a diagnostic surface: it helps
distinguish a retrieval failure from a generator decision.

### 19.2 State machine

~~~typescript
type AnswerState =
  | { status: "idle" }
  | { status: "answering"; question: string }
  | { status: "answered"; response: GroundedAnswer }
  | { status: "insufficient"; question: string }
  | { status: "safetyRefused"; question: string }
  | { status: "error"; message: string };
~~~

"Searching" and "generating" are not represented as two browser requests: the backend
owns the atomic use case. The UI can show "Finding evidence and checking an answer…"
without inventing percentage progress.

### 19.3 Rendering

Answer:

- a heading with the question;
- each claim as a paragraph;
- navigable `[1]`, `[2]` markers;
- a "Sources" list with filename, page and excerpt;
- a link to the PDF;
- a visible "Generated only from retrieved evidence" label.

Insufficient evidence:

- direct text: the system did not find enough support;
- a suggestion to try other terms or index another source;
- never an approximate answer.

Error:

- `role="alert"`;
- keeps the question text for retrying;
- distinguishes configuration, timeout and provider failures.

Accessibility:

- `aria-busy` on the form;
- a live region for progress;
- focus moves to the result only on business success;
- a failure keeps focus where it is useful;
- `aria-disabled` keeps the current UI pattern;
- citation markers have an accessible name, for example
  "Source 1, security-runbook.pdf, page 1".

### 19.4 Payload validation

`apps/web/lib/api.ts` must check:

- a known outcome;
- arrays present;
- non-empty claims only for `answered`;
- unique citation IDs;
- every `citationIds` entry resolves;
- valid UUID/string, pages, chunks and offsets;
- `sourcePath` matching the exact documents pattern;
- no unused citations;
- empty invariants for outcomes without an answer.

If a check fails, the UI uses its own `unexpected_error` copy and does not show a
partial answer.

## 20. Evaluation

### 20.1 Separating quality

Two evaluations will be kept:

1. Retrieval: "did the correct page reach the top-k?"
2. Answer: "given the retrieved evidence, did it answer, refuse and cite correctly?"

Mixing them would hide the cause. An incorrect answer with correct retrieval is a
generation failure. A refusal with the relevant page missing is a retrieval failure.

### 20.2 Dataset `answers_v1.json`

The dataset will be versioned and will contain, at minimum:

- 6 answerable single-page questions;
- 2 questions that require two pieces of evidence;
- 3 unanswerable questions;
- 1 question with an irrelevant lexical match;
- 1 document with an adversarial instruction inside its text;
- cases in English and Spanish;
- expected answers as atomic facts, not as a single phrasing;
- acceptable pages per fact;
- forbidden terms or claims where relevant.

Conceptual schema:

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

`concepts` allow controlled alternatives without requiring a literal sentence. The
runner validates the schema even when no API key exists.

### 20.3 Blocking metrics

Deterministic metrics:

- outcome accuracy: answered vs insufficient;
- citation validity: resolvable references;
- citation completeness: percentage of claims with citations;
- citation page correctness: citations on acceptable pages for the covered facts;
- required fact coverage: expected facts present through normalized alternatives;
- forbidden fact rate;
- provider error rate during the run.

Initial gates for the small dataset:

| Metric | Gate |
| --- | --- |
| Citation validity | `1.00` |
| Citation completeness | `1.00` |
| Answerable outcome accuracy | `1.00` |
| Unanswerable refusal accuracy | `1.00` |
| Citation page correctness | `>= 0.95` |
| Required fact coverage | `>= 0.90` |
| Forbidden fact rate | `0.00` |
| Provider error rate | `0.00` in the acceptance run |

With few cases, an average can hide an important failure. The report also lists
per-case results, and the adversarial cases are must-pass.

### 20.4 Semantic faithfulness

Lexical checks alone do not prove that a claim is entailed by its citation. For
milestone 4:

- every answer in the v1 dataset receives a human review with a binary support rubric;
- the report keeps the question, claims, citations and decision, but it is not
  committed if it contains real documents;
- an LLM judge can be added as a diagnostic signal, never as the only gate;
- the generating model is not used as the sole judge of its own output.

The rubric asks:

1. Is every claim fully supported by its citations?
2. Does the answer add a condition or causality that is absent?
3. Does it omit a fact needed to avoid being misleading?
4. Was the refusal correct?

### 20.5 CI and live evaluation

- CI does not call paid providers or depend on the network.
- `make check` runs unit tests, contract tests and dataset validation.
- `make eval-answers` is opt-in, requires key/model and generates a report.
- The milestone is not declared complete until that command runs against the pinned
  model and the aggregate metrics are recorded in `day-04.md`.
- Changing the prompt, model, chunking, top-k or schema requires rerunning the live
  evaluation.

## 21. Testing strategy

### 21.1 Domain

- deterministic assignment of `E1...En`;
- resolution of a valid ID;
- deduplication preserving order;
- rejection of an unknown ID;
- rejection of a claim without IDs;
- rejection of `answered` without claims;
- rejection of an empty outcome with claims;
- citations derived exactly from `RetrievalMatch`;
- one piece of evidence used by several claims produces a single citation.

### 21.2 Application service

With a fake retriever and generator:

- zero matches does not invoke the generator;
- top-k respects settings;
- `document_id` is propagated;
- nonexistent document;
- unindexed document;
- valid answer;
- generator-decided insufficiency;
- safety refusal;
- invalid generator output;
- order of claims and citations;
- the question is preserved in the response.

### 21.3 OpenAI adapter

Without network, mocking the SDK surface:

- the request carries `store=false`;
- the request carries no tools;
- the input contains only the question and allowed evidence;
- structured output parsing;
- refusal;
- timeout;
- 401/429/5xx;
- incomplete output;
- the SDK returns `None`;
- sensitive details do not appear in errors.

Pydantic and citation resolution will not be mocked internally.

### 21.4 HTTP

- request schema;
- extra fields rejected;
- all 200 outcomes;
- all errors use the envelope;
- OpenAPI documents the responses;
- successful inline PDF;
- nonexistent PDF;
- metadata without a PDF;
- Content-Type and filename;
- generator dependency override.

### 21.5 Frontend

- request and parsing of the three outcomes;
- malformed payload;
- claim with a nonexistent citation ID;
- an answer result moves focus;
- insufficient and safety copy;
- an error keeps the question;
- the pending state prevents double submit;
- accessible markers;
- link to the PDF and page;
- multiple claims sharing a citation;
- excerpts render as text.

### 21.6 Local integration

Real flow:

1. start the API and web;
2. upload a PDF;
3. extract;
4. index;
5. ask an answerable question;
6. verify the answer and citation;
7. open the PDF at the page;
8. ask an unanswerable question;
9. verify the refusal;
10. inspect the browser console and sanitized logs.

The live test uses an explicit key from the environment. It never writes the secret or
persists the answer.

## 22. Phased implementation plan

### Phase 0 — Spike and ADR

Goal: close the only external uncertainty before touching the product flow.

- temporarily add the SDK through the normal dependency flow;
- verify `AsyncOpenAI.responses.parse` with Pydantic;
- verify refusal, timeout, `store=false` and client shutdown;
- compare two models on 3 to 5 representative cases;
- choose an initial model or document why the ID remains required configuration;
- create ADR 5 with the structured pipeline and the no-persistence/no-streaming
  decision.

Gate:

- reproducible spike;
- no secrets in git;
- model decision recorded with evidence.

### Phase 1 — Pure domain and service

- create `answers/domain.py`;
- create `answers/ports.py`;
- implement evidence construction;
- implement citation resolution;
- implement outcomes and invariants;
- implement `answer_question` with fakes;
- add error codes.

Gate:

- pure tests cover every invariant;
- no FastAPI/SDK imports in the domain;
- mypy strict.

### Phase 2 — HTTP contract and source PDF

- request/response schemas;
- `POST /answers`;
- `GET /documents/{id}/content`;
- OpenAPI responses;
- indexed-scope validation;
- HTTP tests.

Initially the answers endpoint uses an injected fake. This allows stabilizing the
contract before adding the network.

Gate:

- complete contract tested;
- PDFs can be opened;
- consistent error envelope.

### Phase 3 — Provider adapter

- prompt and payload;
- async adapter;
- lifespan;
- optional configuration;
- error translation;
- `store=false`;
- SDK mock tests.

Gate:

- no real calls in tests;
- the API starts without a key;
- a missing key affects only `/answers`;
- one manual live call parses structured output.

### Phase 4 — Frontend

- types and runtime parser;
- `answerQuestion` client;
- component and styles;
- outcomes and accessibility;
- cards and source links;
- keep the retrieval panel.

Gate:

- component and API client tests;
- production build;
- keyboard navigation.

### Phase 5 — Evaluation

- v1 dataset;
- runner;
- metrics and gates;
- `make eval-answers`;
- dataset validation in CI;
- final comparative run;
- human faithfulness review.

Gate:

- every hard gate;
- zero unsupported answers in adversarial cases;
- model/snapshot pinned.

### Phase 6 — Documentation and acceptance

- update the README: status, architecture, configuration, privacy and roadmap;
- update ADR 2 to clarify why `indexed` remains the terminal document status;
- document ADR 5;
- create `docs/progress/day-04.md`;
- run `make check`;
- run `make eval-answers`;
- real browser smoke test;
- verify `git diff --check` and dependency audits.

Gate:

- complete definition of done.

## 23. Recommended change and commit order

To keep changes reviewable:

1. `feat(api): add grounded answer domain and contracts`
2. `feat(api): integrate structured OpenAI answer generation`
3. `feat(web): render grounded answers and source citations`
4. `test(evals): add answer quality evaluation`
5. `docs: record milestone 4 architecture and results`

If the work is delivered in a single commit, the recommended message is:

~~~
feat: add grounded answers with verifiable citations
~~~

A retrieval migration, authentication or deployment must not be mixed into these
commits.

## 24. Compatibility and migrations

- The SQLite v1 schema does not change.
- No answer tables are persisted.
- Existing endpoints remain compatible.
- `DocumentStatus` does not change.
- Optional variables are added.
- Routes and error codes are added.
- The frontend must accept the existing vocabulary without new states.
- Current local artifacts remain valid.

If chunking or retrieval changes during the milestone because of an unavoidable fix:

1. the corresponding schema or algorithm version is incremented;
2. the derived index is rebuilt;
3. the retrieval eval and answer eval are rerun;
4. it is documented as a separate decision.

## 25. Operation and failure recovery

### 25.1 Provider not configured

- API/web start.
- Ingestion and retrieval work.
- Answers show the missing configuration.
- There is no infinite automatic retry.

### 25.2 Timeout or rate limit

- The request ends with a stable error.
- The person can retry manually.
- No partial output is shown.
- Previous ingestion does not change.

### 25.3 Process restarted

- There is no answer job to recover.
- Documents and the index remain.
- The next question starts a new operation.

### 25.4 Rollback

The feature is additive:

- the answers router and component can be removed without migrating data;
- the content endpoint can be kept for citations/retrieval;
- the SDK and variables can be removed without touching PDFs or SQLite;
- there are no document states to revert.

## 26. Risks and mitigations

| Risk | Impact | Milestone mitigation |
| --- | --- | --- |
| FTS retrieves lexically matching but irrelevant evidence | False answer | The generator can refuse; dataset with false friends; never assume match = answer. |
| The model cites a valid ID that does not support the claim | False sense of confidence | Structured claims, per-page evaluation and human support review. |
| Prompt injection inside the PDF | Output manipulation | Untrusted evidence, JSON, no tools/secrets, ID allowlist, adversarial cases. |
| Model or alias changes | Silent regression | Snapshot when available; evaluation mandatory when the ID/prompt changes. |
| API key missing or expired | Feature down | Localized 503; the rest of the app keeps working. |
| External data retention | Privacy | `store=false`, minimal evidence, clear notice and review of project controls. |
| The PDF viewer ignores `#page` | Less direct verification | Page visible in the citation and fallback to the full PDF. |
| Truncated output | Incomplete JSON/claims | Measured limit, detection and 502; no partial render. |
| Retry doubles cost | Cost/latency | At most one retry, only for transient failures. |
| Dataset too small | Misleading metrics | Must-pass adversarial cases, per-case results and versioned growth. |
| Excessive abstraction | Delay and ceremonial code | One port, one adapter, no registry or persistence. |

## 27. Rejected alternatives

### Calling the model from the router

Rejected because it mixes HTTP, prompt, provider, retrieval and validation; it prevents
pure tests and turns every error into a branch of the endpoint.

### Letting the frontend send the chunks

Rejected because a client could omit, alter or fabricate evidence while keeping an
apparently "cited" answer.

### Asking for a Markdown answer with `[1]`

Rejected because parsing free-form markers is fragile: IDs go missing, extra references
appear and there is no structural relationship per claim.

### Generating an answer and looking for citations afterwards

Rejected because post-hoc attribution can find similar text without having grounded the
generation.

### Persisting chat and answers

Rejected because it multiplies responsibilities for identity, retention, deletion,
schema and UX without being necessary to demonstrate grounding.

### Streaming

Rejected because an unvalidated claim could appear before an invalid citation is
discovered. It can be revisited with server-side buffering in a later milestone.

### Sending the complete PDF to file search

Rejected because it duplicates ingestion and the index, reduces control over provenance
and sends more data than necessary.

### Adding embeddings now

Rejected because changing retrieval and generation simultaneously makes it impossible to
diagnose the source of an improvement or regression.

### Using the BM25 score as "confidence"

Rejected because it is not a calibrated probability and the current index deliberately
does not expose that score as a contract.

### Failing startup without an API key

Rejected because the provider is not needed for upload, extraction, indexing or search.

### Generic multi-provider support from day one

Rejected because a narrow protocol already protects the use case; factories, registries
and polymorphic configuration would be speculation.

## 28. Decisions that require evidence before closing

These are not open architecture questions; they are parameters that must be measured:

1. Exact model and snapshot.
2. Final timeout.
3. Output maximum.
4. Whether top-5 beats top-3 in coverage without degrading refusal.
5. Final insufficient/safety copy.
6. Whether the local viewer honors `#page=N` in the verified browsers.

Each one is closed with the dataset, a browser test or an operational measurement. None
requires redesigning the boundaries defined in this document.

## 29. Definition of done

Architecture:

- [ ] The `AnswerGenerator` port exists.
- [ ] The domain imports no framework or SDK.
- [ ] Router, service and adapter have separate responsibilities.
- [ ] There is no answer persistence and no `ready` status.

Backend:

- [ ] `POST /answers` implemented.
- [ ] `GET /documents/{id}/content` implemented.
- [ ] Outcomes and invariants validated.
- [ ] Citations resolved only from retrieval.
- [ ] Async OpenAI adapter with Structured Outputs.
- [ ] `store=false`, no tools and with limits.
- [ ] Stable, sanitized errors.
- [ ] The API starts without a key.

Frontend:

- [ ] Question form and every state.
- [ ] Claims with navigable citations.
- [ ] Cards with excerpt and link to the PDF.
- [ ] Payload validated before rendering.
- [ ] Accessibility covered by tests.

Quality:

- [ ] Unit, HTTP and frontend tests.
- [ ] Answer dataset v1.
- [ ] Deterministic gates passed.
- [ ] Human faithfulness review passed.
- [ ] Retrieval eval still passes.
- [ ] `make check` passes.
- [ ] `make eval-answers` passes with the model recorded.
- [ ] Real smoke test without console errors.

Documentation:

- [ ] ADR 2 updated.
- [ ] ADR 5 accepted.
- [ ] README updated without overpromising.
- [ ] `.env.example` documented.
- [ ] `day-04.md` records real results.
- [ ] Privacy and limitations explained.

## 30. Concrete next action

Start with Phase 0, not with the UI:

1. Create a `codex/milestone-04-grounded-answers` branch.
2. Run a minimal SDK spike against the Responses API with Pydantic output.
3. Test two models with three answerable and two unanswerable cases.
4. Record the model, snapshot, timeout, tokens and results.
5. Turn this plan into ADR 5 with the external decisions closed.
6. Implement the domain and citation resolution with fakes before the real integration.

That order reduces the main risk—the external boundary and its contract—without coupling
the rest of the product to an exploratory test.
