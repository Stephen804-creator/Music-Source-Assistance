# Music Source Assistant — architecture notes

## Core request flow
`brief -> ontology matcher -> structured intent -> query expansion -> provider adapters -> normalize -> deduplicate -> explainable rank -> response`

Direct search bypasses intent parsing. Both modes share provider adapters and normalized records.

## Components
- `app/music_ontology.json`: curated vocabulary and synonyms.
- `app/query_understanding.py`: deterministic extraction and query expansion.
- `app/providers.py`: provider clients, normalization, partial failures and metadata indexing.
- `app/ranking.py`: transparent scoring and match reasons.
- `app/metadata_index.py`: SQLite FTS5 local index with fallback.
- `migrations/001_music_catalogue.sql`: PostgreSQL schema for later hosted integration.
- `app/audio_features.py`: optional upload-only audio signal analysis.
- `app/main.py`: FastAPI routes and Streamable HTTP MCP tools.
- `frontend/`: responsive Discover Music and AI Studio interface.

## Important boundaries
1. Search relevance and licence permission are separate. Ranking never implies permission.
2. Provider source pages are authoritative; licence metadata can be missing or stale.
3. Do not download or store provider audio unless provider terms and the work licence permit it and the user initiates it.
4. Audio analysis accepts bounded user uploads only; it does not fetch arbitrary remote URLs.
5. SQLite is a local/single-instance index. PostgreSQL migration exists but is not wired into runtime yet.
6. The brief parser is not a generative language model. Ambiguity is exposed rather than concealed.

## Evaluation
Build a golden dataset of anonymized briefs with human-labelled relevant tracks. Measure recall@k, precision@k, nDCG@k, provider coverage, licence metadata completeness and latency. Add embeddings or an LLM only if evaluation shows a meaningful gap that deterministic retrieval cannot close economically.
