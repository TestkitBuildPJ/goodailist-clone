"""Phase B ingest pipeline — GitHub API client, ETag store, scheduler.

Module split (TIP-B02 → B03):
- ``etag_store``  — in-memory ETag cache keyed by ``(owner, repo)``
- ``github_client`` — async HTTP client with ETag + 429 handling
- ``ingestor``    — orchestration (TIP-B03)
- ``scheduler``   — APScheduler wiring (TIP-B03)
"""
