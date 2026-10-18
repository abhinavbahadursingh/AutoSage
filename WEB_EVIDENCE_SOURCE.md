# Web Evidence Source — Internet Search for Objective Verification

## Problem

The objective verification check **`o3_evidence_sources`** ("Decisions are checked against independent sources, not just internal notes") was reporting **NOT VERIFIED at 0%** because:

- Only `InternalEvidenceSource` (type=`internal`) and `MockExternalEvidenceSource` (type=`external` but `source_id` contains `"mock"`) were registered.
- The check filters out anything with `"mock"` or `"stub"` in its ID, and requires `source_type` in `{paper, web, literature, external}`.
- Result: no independent knowledge source was registered, so the check could never PASS.

## Change

Added a real `WebEvidenceSource` class in `backend/app/engine/evidence/sources.py` that searches the live internet via DuckDuckGo's HTML endpoint (no API key required) and returns results as `EvidencePiece` objects with titles, URLs, and snippets.

### New class: `WebEvidenceSource`

| Attribute | Value |
|-----------|-------|
| `source_id` | `web_search` |
| `source_type` | `web` |
| Search engine | DuckDuckGo HTML (`https://html.duckduckgo.com/html/`) |
| HTTP client | `httpx.AsyncClient` |
| Timeout | 15 seconds (configurable) |
| Credibility score | 0.7 (corroborative, not authoritative) |

It:
- POSTs the query to DuckDuckGo with a browser User-Agent
- Parses result titles, URLs, and snippets from the HTML
- Unwraps DuckDuckGo redirect links (`uddg=...`) to real destination URLs
- Returns empty results gracefully if the network is unavailable (never crashes the verification)
- Credibility is 0.7 — web results are treated as corroborative evidence, not authoritative proof

### Registration

`WebEvidenceSource()` is now registered in `register_builtin_sources()` alongside the existing internal, mock, and memory sources. This function is already called by:
- `app.engine.verification.engine.VerificationEngine` (line 113)
- `app.services.verification_service.VerificationService` (line 60)

### How the check now passes

`check_evidence_sources()` in `checks.py` iterates registered sources and counts those with:
- `source_type` in `{paper, web, literature, external}` AND
- `source_id` NOT containing `"mock"` or `"stub"`

`WebEvidenceSource` has `source_id="web_search"` (no "mock"/"stub") and `source_type="web"`, so it qualifies as an independent knowledge source. The check now reports PASS instead of NOT VERIFIED.

### Example output

```
Query: house price prediction machine learning regression
Total found: 3
  - House Price Prediction using Machine Learning in Python
    URL: https://www.geeksforgeeks.org/machine-learning/house-price-prediction-using-machine-learning-in-python/
    Snippet: Predicting house prices is a key challenge in the real estate industry...
    Type: web, Credibility: 0.7
  - GitHub - tejalp68/house-price-prediction-ml
    URL: https://github.com/tejalp68/house-price-prediction-ml
    Type: web, Credibility: 0.7
```

## Files changed

| File | Change |
|------|--------|
| `backend/app/engine/evidence/sources.py` | Added `WebEvidenceSource` class; registered it in `register_builtin_sources()`; added `httpx` and `re` imports |

## Test results

All 149 backend unit tests pass. A live smoke test confirmed the web search returns real results for house price prediction queries.
