# CHOICES.md — Key Technical Decisions

## 1. Detection Model: YOLOv8s

### Options Considered
| Model | Inference Speed | Accuracy (COCO mAP) | Size | Pros | Cons |
|-------|----------------|---------------------|------|------|------|
| YOLOv8n | ~1ms/frame | 37.3% | 6.2MB | Fastest; real-time capable | Lower accuracy on crowded scenes; misses partial occlusion |
| **YOLOv8s** | ~3ms/frame | 44.9% | 22MB | **Best speed-accuracy tradeoff**; handles groups well | Slightly slower than nano |
| YOLOv8m | ~7ms/frame | 50.2% | 52MB | Higher accuracy | Too slow for 15fps processing without GPU batching |
| RT-DETR | ~10ms/frame | 53.0% | 65MB | Transformer-based; better at occlusion | Requires larger GPU memory; complex setup |
| MediaPipe | ~2ms/frame | N/A | <5MB | Lightweight; pose estimation | Not designed for retail density; no built-in tracking |

### What AI Suggested
Claude recommended starting with YOLOv8m for best accuracy, then downgrading if inference was too slow. GPT-4 suggested RT-DETR for better handling of occluded people in billing queues.

### What I Chose and Why
**YOLOv8s** — the "small" variant. My reasoning:

1. **15fps constraint is binding.** The CCTV clips are 15fps, and we process with a stride of 3-5 frames. YOLOv8s at ~3ms/frame with batch size 8 stays comfortably within this budget. YOLOv8m would require aggressive stride (missing fast-moving entries).

2. **ByteTrack compensates for detection gaps.** The tracking layer (ByteTrack) uses IoU-based association, which means a missed detection in one frame is recovered in the next. This makes the marginal accuracy gain from `m` less valuable than the consistency from `s`.

3. **Group entry depends on tracker, not detector.** The key scoring criterion (3 people entering = 3 ENTRY events) is solved at the ByteTrack level, where each person gets a separate `track_id` before hitting the entry line. A more accurate detector doesn't help here — what matters is that the NMS threshold doesn't merge nearby people (we lower NMS to 0.25 for billing cameras).

4. **Practical constraint: the 22MB weight file downloads instantly** via `make weights`. The 52MB medium model adds friction.

I disagreed with the AI suggestion to use RT-DETR — while it handles occlusion better in benchmarks, the complexity of setting up a DETR-based tracker (which doesn't integrate with ByteTrack's IoU association natively) outweighed the accuracy benefit for this specific retail CCTV scenario.

---

## 2. Event Schema Design

### Options Considered
1. **Flat events only** — every detection emits a self-contained JSON event. No session concept.
2. **Session-first** — group all events under a session object; emit the session when it closes.
3. **Hybrid (chosen)** — flat event stream with `visitor_id` as the session key. Events are self-contained but can be grouped by `visitor_id` for session analysis.

### What AI Suggested
Claude recommended the session-first approach, arguing it simplifies funnel computation and avoids orphaned events. It suggested emitting a `SessionComplete` aggregate event at EXIT time containing the full visitor journey.

### What I Chose and Why
**Hybrid flat events with visitor_id linkage.** My reasoning:

1. **Streaming-first design.** The problem statement says "Live Dashboard" with real-time updates. Session-first forces you to wait until EXIT to emit anything — the dashboard would see nothing until visitors leave. Flat events stream immediately, and the API reconstructs sessions on-demand via SQL GROUP BY.

2. **Schema matches the scoring harness.** The provided `sample_events.jsonl` uses flat events with `event_type`, `visitor_id`, and `timestamp`. Diverging from this format risks schema compliance failures (10 pts at stake).

3. **Idempotency is trivial with flat events.** Each event has a unique `event_id` (UUID v4). POST /events/ingest deduplicates by this key. With session-first, you'd need to merge partial session updates, which is more complex.

4. **The `metadata` object provides extensibility** without schema changes. `queue_depth`, `sku_zone`, and `session_seq` are all optional metadata fields. Adding new fields (e.g., `dwell_ms` per zone) doesn't require a schema migration.

I agreed with the AI on one point: session analysis *is* easier with grouped data. But I implemented that at the API layer (`/funnel` endpoint reconstructs sessions from flat events) rather than at the schema layer.

---

## 3. API Architecture: FastAPI + Async PostgreSQL

### Options Considered
| Stack | Pros | Cons |
|-------|------|------|
| **FastAPI + asyncpg + PostgreSQL** | Async I/O for SSE + ingest concurrency; automatic OpenAPI docs; Pydantic validation | Requires async session management |
| Flask + SQLAlchemy + SQLite | Simple; familiar; single-file possible | Blocking I/O kills SSE; no concurrent ingest; SQLite can't handle concurrent writes |
| Express.js + Prisma + PostgreSQL | Fast development; good for WebSocket | Python CV stack would need separate process; no Pydantic equivalent |
| Go + pgx | Best raw performance | Slower development velocity; no Pydantic; less ecosystem for ML integration |

### What AI Suggested
GPT-4 suggested Flask + SQLite for simplicity ("just get it working"), with an upgrade path to PostgreSQL later. Claude suggested FastAPI but with synchronous SQLAlchemy ("async adds complexity without benefit for a take-home challenge").

### What I Chose and Why
**FastAPI with fully async PostgreSQL (asyncpg) and SQLModel ORM.** My reasoning:

1. **SSE and WebSocket require async.** The live dashboard connects via WebSocket for real-time event streaming. Flask's WSGI model can't handle WebSocket connections alongside HTTP requests without complex workarounds (gevent, SocketIO). FastAPI's ASGI model handles both natively.

2. **Concurrent ingest is critical.** The detection pipeline emits events in batches of up to 500. During replay, multiple batches arrive rapidly. Synchronous Flask would process one batch at a time, creating a bottleneck. Async FastAPI handles concurrent ingest naturally.

3. **PostgreSQL over SQLite for production-readiness.** The scoring rubric specifically says "production-aware" (Part C, 20 pts). SQLite doesn't support concurrent writes, has no real connection pooling, and can't run the partial indexes the addendum requires (`idx_customer_sessions WHERE is_staff = FALSE`).

4. **Automatic OpenAPI docs.** FastAPI generates interactive Swagger UI at `/docs` — this is explicitly called out in the addendum as a documentation criterion. Flask requires separate swagger setup.

5. **Pydantic validation is scoring-critical.** The schema compliance criterion (10 pts) requires strict validation of every event field. FastAPI's native Pydantic integration validates request bodies automatically with detailed error responses. Flask would require manual validation code.

I disagreed with both AI suggestions. Flask + SQLite would fail the production-readiness criteria (no concurrent writes, no SSE, no WebSocket). And synchronous SQLAlchemy would block the event loop during database queries, defeating the purpose of async FastAPI.

The trade-off I accepted: async PostgreSQL adds operational complexity (requires a running PostgreSQL instance, connection string configuration). I mitigated this with Docker Compose — `make up` starts PostgreSQL automatically, and the API container waits for it via healthcheck.

---

## 4. Conversion Rate: POS Time-Window Correlation

### Options Considered
1. **Billing join proxy** — `conversion = distinct(BILLING_QUEUE_JOIN) / distinct(ENTRY)`. Simple but ignores actual purchases.
2. **POS-correlated (chosen)** — match each POS transaction to visitors with `BILLING_QUEUE_JOIN` in the 5-minute window before `transaction_timestamp`.
3. **VLM / receipt OCR** — match faces to receipts. Rejected as out of scope.

### What AI Suggested
GPT-4 suggested using billing queue joins as a proxy for conversion ("good enough for demo"). Claude suggested correlating POS timestamps with session end times.

### What I Chose and Why
**POS-correlated conversion** per the challenge PDF (section 3.4). Implementation in `app/pos.py`:

- Load deduplicated orders from `data/pos_transactions.csv` (Purplle `DD-MM-YYYY` + `HH:MM:SS` format).
- Map legacy `ST1008` → `STORE_BLR_002`.
- For each transaction on the query date, count visitors with a non-staff billing join in `[txn - 5min, txn]`.
- `conversion_rate_pct = pos_matched_visitors / unique_visitors`.

When no POS rows exist for a store/date (isolated tests), metrics fall back to the billing-join proxy and set `conversion_method: billing_proxy`.

---

## 5. Dashboard API Routing: Nginx Same-Origin Proxy

### Options Considered
1. **Browser calls `localhost:8000` directly** — requires CORS; breaks when dashboard is served from Docker on port 5173.
2. **Nginx reverse proxy (chosen)** — dashboard container proxies `/api`, `/health`, `/ws` to the `api` service.
3. **Env-only CORS** — works for dev with Vite proxy but fragile for reviewers running `docker compose up`.

### What I Chose and Why
**Nginx proxy in the dashboard Docker image** (`frontend/nginx.conf`) with `VITE_API_BASE=` at build time so the React client uses same-origin `/api/v1`. Vite dev server keeps equivalent proxies in `vite.config.ts` for local development.

This satisfies the acceptance gate: reviewers open one URL (`http://localhost:5173`) and all API + WebSocket traffic works without manual CORS configuration.
