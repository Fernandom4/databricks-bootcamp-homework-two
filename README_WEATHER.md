# Weather Intelligence

Harvests weather alerts + forecasts, embeds them for semantic search, and
exposes a search API — same pattern as the ticker/news pipeline, applied to
weather.

## Data source

**National Weather Service API** (`api.weather.gov`) — free, no API key,
generous rate limits. Chosen over OpenWeatherMap/DWD for simplicity, even
though it's US-only (not personally relevant to my location) — the goal here
was learning the pipeline pattern, not building something I'd use daily.

Pulls two kinds of narrative text per location:
- **Active alerts** — `description` + `instruction` combined
- **Forecast periods** — `detailedForecast`

Locations are lat/lon pairs (no built-in geocoding — NWS itself has none,
and adding a geocoder felt like unnecessary scope for this assignment).

## Schema

**`weather_documents`** — one row per alert or forecast period.
`id, location, source_type, headline, narrative_text, issued_at, payload, synced_at`

**`weather_embeddings`** — one row per chunk of a document's `narrative_text`.
`id, document_id (FK), chunk_index, chunk_text, embedding vector(384), model_name, created_at`

Both use `id TEXT PRIMARY KEY` with `ON CONFLICT DO UPDATE`/`DO NOTHING`
upserts, so syncing/embedding is safe to re-run without duplicating rows.

## Chunking & embedding

- `CHUNK_SIZE=800`, `CHUNK_OVERLAP=100` — sliding-window over `narrative_text`.
  Most NWS text is well under 800 characters, so most documents end up as a
  single chunk; chunking mainly kicks in for long combined alert text.
- Model: `sentence-transformers/all-MiniLM-L6-v2` (384-dim), same model as
  the reference news pipeline, for consistent distance-operator conventions.

## Running the pipeline

1. **Harvest** — `POST /weather/sync`
   ```json
   {"locations": [{"lat": 32.7767, "lon": -96.797, "label": "Dallas, TX"}], "limit": 20}
   ```
   Fetches + upserts into `weather_documents`.

2. **Embed** — run `ingest_weather_embeddings.py` as a Databricks notebook
   (not a plain script — see Limitations). Finds unembedded documents,
   chunks, embeds in batches, writes to `weather_embeddings`.

3. **Search** — `POST /weather/search`
   ```json
   {"query": "flood risk this weekend", "top_k": 5}
   ```
   Embeds the query, runs a cosine-similarity search (`<=>`) over
   `weather_embeddings`, returns the top matches with location, headline,
   chunk text, and similarity score.

## Known limitations / would improve with more time

- **US-only**: NWS has no international coverage; a global source would
  need a different API entirely.
- **No geocoding**: callers must supply lat/lon directly, not city names.
- **Embedding script runs as a notebook, not a standalone script**: running
  it via Databricks' inline "Run" button (rather than a real Job/terminal
  process) meant `__file__`-based imports weren't reliable, so the DB
  connection logic is duplicated inline in the notebook instead of
  importing `lakebase.py`. A scheduled Job would be the more production-
  ready way to run this.
- **Table-creation guardrails (`ensure_*_table`) silently no-op on
  permission errors**: the app's DB role doesn't own the tables (created
  manually under a different role), so `CREATE TABLE/INDEX IF NOT EXISTS`
  calls fail with `InsufficientPrivilege` and are caught + skipped. Works
  because the tables already exist, but a cleaner setup would grant the
  app's role ownership, or provision schema via a separate migration step
  with the right privileges.
- **No scheduled sync**: `/weather/sync` and the embedding notebook are
  both manually triggered; a real deployment would run these on a
  schedule (e.g. a Databricks Job with a trigger).