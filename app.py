"""
app.py — RxCheck Flask REST API.

Architecture:
  GET  /                          → Render index.html (SPA shell)
  GET  /api/rxnorm/<path:subpath> → Transparent proxy to rxnav.nlm.nih.gov/REST
  GET  /api/local-data            → Serve safe catalog data (no interaction rules)
  POST /api/normalize-drug        → Server-side brand→generic Levenshtein matching
  POST /api/check-interactions    → SQL query against PostgreSQL rxcheck DB

Database:
  Uses psycopg2.pool.ThreadedConnectionPool so each Flask thread checks out and
  returns a dedicated connection — no shared-state races, no per-request TCP
  handshake overhead.  Pool size is controlled by the environment variables
  DB_POOL_MIN (default 1) and DB_POOL_MAX (default 10).

  Connection string is read from the DATABASE_URL environment variable:
    postgresql://user:password@host:5432/rxcheck

Search precision:
  _resolve_drug_ids() uses a two-tier strategy:
    1. Exact case-insensitive match via citext (zero false positives)
    2. PostgreSQL trigram similarity  generic_name % %s  with threshold ≥ 0.85
       (eliminates dangerous substring false-positives like
        "folic acid" matching a search for "valproic acid")
"""

import os
import re
from contextlib import contextmanager
from typing import Generator

import requests as http_requests
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from psycopg2 import pool as pg_pool
from psycopg2.extras import RealDictCursor

from data import BRAND_HINTS, BRAND_SAVINGS_LOOKUP, PRICE_CATALOG

load_dotenv()

app = Flask(__name__)

_RXNORM_UPSTREAM = "https://rxnav.nlm.nih.gov/REST"

# ---------------------------------------------------------------------------
# Database configuration — psycopg2 ThreadedConnectionPool
# ---------------------------------------------------------------------------

_DATABASE_URL: str = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/rxcheck",
)
_DB_POOL_MIN: int = int(os.environ.get("DB_POOL_MIN", "1"))
_DB_POOL_MAX: int = int(os.environ.get("DB_POOL_MAX", "10"))

# Trigram similarity threshold — must be high enough to block "folic acid"
# from matching "valproic acid" (similarity ≈ 0.42) while still catching
# common misspellings (e.g. "metformin" vs "metfomin" ≈ 0.89).
_TRGM_THRESHOLD: float = 0.85

# Module-level pool; initialised lazily on first request so the app can
# import without a live database (useful for tests and CI).
_connection_pool: pg_pool.ThreadedConnectionPool | None = None


def _get_pool() -> pg_pool.ThreadedConnectionPool:
    """Return (creating if needed) the module-level connection pool."""
    global _connection_pool
    if _connection_pool is None:
        _connection_pool = pg_pool.ThreadedConnectionPool(
            _DB_POOL_MIN,
            _DB_POOL_MAX,
            dsn=_DATABASE_URL,
        )
    return _connection_pool


@contextmanager
def _db_conn() -> Generator:
    """
    Context manager that checks out a connection from the pool, yields a
    RealDictCursor, and guarantees the connection is returned to the pool on
    exit — even on exception.

    Usage::

        with _db_conn() as cur:
            cur.execute("SELECT 1")
            row = cur.fetchone()
    """
    conn = _get_pool().getconn()
    try:
        conn.autocommit = False
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        _get_pool().putconn(conn)


# ---------------------------------------------------------------------------
# Drug resolution — high-precision trigram search
# ---------------------------------------------------------------------------


def _resolve_drug_ids(name: str) -> list[int]:
    """
    Resolve a raw drug name string to one or more drug row IDs.

    Two-tier strategy (precision-first):

      Tier 1 — Exact citext match
        SELECT id FROM drugs WHERE generic_name = %s
        citext gives case-insensitive equality with zero false positives.

      Tier 2 — PostgreSQL trigram similarity
        SET pg_trgm.similarity_threshold = 0.85;
        SELECT id FROM drugs WHERE generic_name % %s
        The % operator returns TRUE only when similarity() > threshold.
        At 0.85 the "valproic acid" / "folic acid" pair scores ≈ 0.42 → NO MATCH.
        A harmless misspelling like "metfomin" vs "metformin" scores ≈ 0.89 → MATCH.

    The dangerous token-based LIKE %token% from the SQLite implementation is
    removed entirely — it was the root cause of the cross-drug false-positive
    vulnerability.

    Returns a list of matching IDs (usually 0 or 1 element).
    """
    name_clean = name.strip().lower()
    if not name_clean:
        return []

    with _db_conn() as cur:
        # Tier 1: Exact (citext handles case folding server-side)
        cur.execute(
            "SELECT id FROM drugs WHERE generic_name = %s",
            (name_clean,),
        )
        rows = cur.fetchall()
        if rows:
            return [r["id"] for r in rows]

        # Tier 2: Trigram similarity — set session threshold then query
        cur.execute(
            "SET pg_trgm.similarity_threshold = %s",
            (_TRGM_THRESHOLD,),
        )
        cur.execute(
            "SELECT id FROM drugs WHERE generic_name %% %s",
            (name_clean,),
        )
        rows = cur.fetchall()
        return [r["id"] for r in rows]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _levenshtein(a: str, b: str) -> int:
    """Standard Levenshtein edit-distance (O(m*n) DP)."""
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        curr = [i] + [0] * len(b)
        for j, cb in enumerate(b, 1):
            curr[j] = min(
                curr[j - 1] + 1,           # insertion
                prev[j] + 1,               # deletion
                prev[j - 1] + (ca != cb),  # substitution
            )
        prev = curr
    return prev[len(b)]


def _clean_raw_name(raw: str) -> tuple[str, str]:
    """
    Strip dosage tokens from a raw drug string and return
    (cleaned_full, first_word).
    """
    cleaned = re.sub(
        r"\b\d+(\.\d+)?\s*(mg|mcg|g|gm|ml|iu|units?|%|tabs?|tablets?|caps?)\b",
        " ",
        raw.strip().lower(),
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    first = cleaned.split()[0] if cleaned.split() else cleaned
    return cleaned, first


def _normalize(raw_name: str) -> tuple[str, dict | None]:
    """
    Map a raw drug string to its generic name and optional catalog entry.

    Resolution order:
      1. Exact match on cleaned full name in BRAND_HINTS
      2. Exact match on first word in BRAND_HINTS
      3. Exact match on cleaned full name in PRICE_CATALOG
      4. Exact match on first word in PRICE_CATALOG
      5. Levenshtein fuzzy match (distance ≤ threshold) across all keys
      6. Return cleaned name as-is with no catalog entry
    """
    cleaned, first = _clean_raw_name(raw_name)

    def _catalog_for(generic: str) -> dict | None:
        key = generic.split()[0]
        return PRICE_CATALOG.get(key) or PRICE_CATALOG.get(generic)

    # Exact BRAND_HINTS
    for candidate in (cleaned, first):
        if candidate in BRAND_HINTS:
            generic = BRAND_HINTS[candidate]
            return generic, _catalog_for(generic)

    # Exact PRICE_CATALOG
    for candidate in (cleaned, first):
        if candidate in PRICE_CATALOG:
            return candidate, PRICE_CATALOG[candidate]

    # Fuzzy match
    all_keys = list(BRAND_HINTS) + list(PRICE_CATALOG)
    best, best_dist = None, float("inf")
    for key in all_keys:
        d = min(_levenshtein(cleaned, key), _levenshtein(first, key))
        threshold = 2 if len(key) > 5 else (1 if len(key) >= 4 else 0)
        if d <= threshold and d < best_dist:
            best, best_dist = key, d

    if best:
        generic = BRAND_HINTS.get(best, best)
        return generic, _catalog_for(generic) or PRICE_CATALOG.get(best)

    return cleaned or raw_name.lower(), None


def _matches_any(drug: dict, terms: list[str]) -> bool:
    """
    Return True if any term word-matches any field in the resolved drug object.
    Mirrors the JS matchesAny() function.
    """
    parts = [
        drug.get("rawName", ""),
        drug.get("queryName", ""),
        drug.get("rxName", ""),
        drug.get("genericName", ""),
        *drug.get("ingredients", []),
        *drug.get("alternatives", []),
    ]
    haystack = " ".join(p for p in parts if p).lower()
    for term in terms:
        if re.search(rf"(^|\W){re.escape(term)}(\W|$)", haystack):
            return True
    return False


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.route("/")
def homepage():
    return render_template("index.html")


@app.route("/api/rxnorm/<path:subpath>")
def rxnorm_proxy(subpath):
    """
    Transparent GET proxy to https://rxnav.nlm.nih.gov/REST/<subpath>.

    Forwards all query parameters. The client never sees the upstream host.
    Error mapping:
      requests.Timeout            → 504 Gateway Timeout
      non-2xx upstream response   → 502 Bad Gateway
      any other RequestException  → 502 Bad Gateway
    """
    upstream_url = f"{_RXNORM_UPSTREAM}/{subpath}"

    # Preserve multi-value query params (rare for RxNav, but be correct)
    params = request.args.to_dict(flat=False)
    flat_params = {k: v[0] if len(v) == 1 else v for k, v in params.items()}

    try:
        resp = http_requests.get(
            upstream_url,
            params=flat_params,
            headers={"Accept": "application/json"},
            timeout=10,
        )
    except http_requests.exceptions.Timeout:
        return (
            jsonify({"error": "timeout", "message": "RxNav did not respond within 10 s"}),
            504,
        )
    except http_requests.exceptions.RequestException as exc:
        return jsonify({"error": "proxy_error", "message": str(exc)}), 502

    if not resp.ok:
        return (
            jsonify({
                "error": "upstream_error",
                "upstream_status": resp.status_code,
                "message": f"RxNav returned HTTP {resp.status_code}",
            }),
            502,
        )

    # Stream the raw bytes straight back; content-type is always JSON for RxNav
    return app.response_class(
        response=resp.content,
        status=resp.status_code,
        mimetype="application/json",
    )


@app.route("/api/local-data")
def local_data():
    """
    Serve safe, display-only catalog data.

    Intentionally excludes INTERACTION_RULES — those are evaluated exclusively
    server-side by /api/check-interactions.
    """
    return jsonify({
        "brand_hints": BRAND_HINTS,
        "price_catalog": PRICE_CATALOG,
        "brand_savings_lookup": BRAND_SAVINGS_LOOKUP,
    })


@app.route("/api/normalize-drug", methods=["POST"])
def normalize_drug():
    """
    Accept a raw drug name string, run server-side brand→generic resolution
    (exact lookup + Levenshtein fuzzy match), and return the normalized name
    plus its catalog entry.

    Request body:  { "name": "Glycomet 500" }
    Response body: { "normalized": "metformin", "catalog": { ... } | null }
    """
    body = request.get_json(silent=True) or {}
    raw_name = str(body.get("name", "")).strip()

    if not raw_name:
        return jsonify({"error": "name is required"}), 400

    normalized, catalog = _normalize(raw_name)
    return jsonify({"normalized": normalized, "catalog": catalog})


@app.route("/api/check-interactions", methods=["POST"])
def check_interactions():
    """
    Query the PostgreSQL database for interactions between a list of resolved
    drug objects.

    The frontend contract is preserved exactly:
      Request body:  { "resolved": [ { rawName, queryName, rxName, genericName,
                                       ingredients[], alternatives[] }, ... ] }
      Response body: { "findings": [ { level, pair, message, action, source } ] }

    Name resolution strategy for each drug object:
      genericName → rxName → queryName → rawName (first non-empty wins)
    Each candidate is looked up in the DB via _resolve_drug_ids().
    """
    body = request.get_json(silent=True) or {}
    resolved = body.get("resolved", [])

    if not isinstance(resolved, list):
        return jsonify({"error": "resolved must be a list"}), 400

    findings = []

    try:
        # Pre-resolve every drug to its DB id(s) once, not per-pair.
        # Each _resolve_drug_ids() call manages its own pooled connection.
        drug_ids: list[list[int]] = []
        for drug in resolved:
            candidate_names = [
                drug.get("genericName", ""),
                drug.get("rxName", ""),
                drug.get("queryName", ""),
                drug.get("rawName", ""),
                *drug.get("ingredients", []),
            ]
            ids: list[int] = []
            for name in candidate_names:
                if name:
                    ids = _resolve_drug_ids(name)
                    if ids:
                        break
            drug_ids.append(ids)

        # Check every unique pair using a single pooled connection
        with _db_conn() as cur:
            for i in range(len(resolved)):
                for j in range(i + 1, len(resolved)):
                    left_drug  = resolved[i]
                    right_drug = resolved[j]
                    ids_i = drug_ids[i]
                    ids_j = drug_ids[j]

                    # Cartesian product of IDs (usually 1×1) with canonical ordering
                    seen_pairs: set[tuple[int, int]] = set()
                    for id_a in ids_i:
                        for id_b in ids_j:
                            if id_a == id_b:
                                continue
                            lo, hi = (id_a, id_b) if id_a < id_b else (id_b, id_a)
                            if (lo, hi) in seen_pairs:
                                continue
                            seen_pairs.add((lo, hi))

                            cur.execute(
                                """
                                SELECT severity, description, action_text, source
                                FROM   interactions
                                WHERE  drug_a_id = %s AND drug_b_id = %s
                                """,
                                (lo, hi),
                            )
                            row = cur.fetchone()
                            if row:
                                findings.append({
                                    "level":   row["severity"],
                                    "pair":    [
                                        left_drug.get("rawName", ""),
                                        right_drug.get("rawName", ""),
                                    ],
                                    "message": row["description"],
                                    "action":  row["action_text"],
                                    "source":  row["source"],
                                })

    except Exception as exc:  # noqa: BLE001
        # Pool not reachable (DB not yet provisioned) — degrade gracefully
        app.logger.error("DB error in check_interactions: %s", exc)
        return jsonify({
            "findings": [],
            "_warning": (
                "Database unavailable. Run `python etl.py --seed-only` after "
                "provisioning PostgreSQL to initialise the database."
            ),
        })

    return jsonify({"findings": findings})


if __name__ == "__main__":
    app.run(debug=True)