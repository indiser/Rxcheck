"""
etl.py — RxCheck openFDA SPL ingestion pipeline.

Pipeline stages:
  1. SEED      – Bootstrap the database from the hardcoded INTERACTION_RULES in
                 data.py so the app is functional before any FDA download.
  2. CHECKPOINT– Read etl_sync_state to determine the last successfully
                 committed batch offset.  Resume from there automatically.
  3. FETCH     – Download a batch of drug-label records from the openFDA API.
  4. PARSE     – Extract drug names and raw drug_interactions text from each record.
  5. LLM       – Call the Groq API to structure the free-text into typed JSON.
  6. LOAD      – Upsert drugs and interactions into PostgreSQL.
  7. COMMIT    – Write the new offset back to etl_sync_state ONLY after a full
                 batch has been successfully written.  A crash anywhere before
                 this point leaves the checkpoint at the previous safe offset
                 so the next run replays at most one batch.

Idempotency / fault-tolerance guarantees:
  • All drug + interaction writes use INSERT … ON CONFLICT DO UPDATE (UPSERT),
    so replaying a batch from the checkpoint cannot create duplicate rows.
  • The checkpoint is updated in the same transaction as the batch data,
    making the commit atomic: either both succeed or neither does.
  • On startup, --skip is IGNORED if etl_sync_state already holds a value
    greater than --skip; the checkpoint always wins so a re-run never
    regresses to an earlier offset.

Usage:
  python etl.py                        # seed + resume from checkpoint, fetch 100
  python etl.py --skip 200 --limit 50  # override start (only if checkpoint is 0)
  python etl.py --seed-only            # just bootstrap from data.py
  python etl.py --dry-run              # fetch + parse, no DB writes
  python etl.py --reset-checkpoint     # reset checkpoint to 0 (dangerous!)

Environment variables (or .env file):
  DATABASE_URL   – PostgreSQL DSN (default: postgresql://postgres:postgres@localhost:5432/rxcheck)
  GROQ_API_KEY   – required for LLM stage
  FDA_LIMIT      – default 100; overridden by --limit
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

import psycopg2
import psycopg2.extras
import requests
from dotenv import load_dotenv
from groq import Groq

from llm_router import extract_clinical_data

# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("rxcheck.etl")

# Directory this script lives in (project root)
PROJECT_ROOT = Path(__file__).parent.resolve()
SCHEMA_FILE  = PROJECT_ROOT / "schema.sql"

# PostgreSQL connection string
DATABASE_URL: str = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/rxcheck",
)

# openFDA drug label endpoint (no API key needed for ≤1000 req/day)
FDA_BASE            = "https://api.fda.gov/drug/label.json"
FDA_REQUEST_TIMEOUT = 30   # seconds

# Groq settings
GROQ_MODEL            = "llama-3.3-70b-versatile"
GROQ_MAX_TOKENS       = 1024
GROQ_RATE_LIMIT_SLEEP = 1.2    # seconds between calls (free tier: 30 RPM)
GROQ_MAX_RETRIES      = 4
GROQ_BACKOFF_BASE     = 2.0    # seconds; doubled on each retry

# System prompt — instructs the LLM to output ONLY valid JSON
GROQ_SYSTEM_PROMPT = """
You are a clinical pharmacology data-extraction engine.

You will receive a raw drug-interactions text block from an FDA drug label.
Your sole task is to extract every drug interaction mentioned and return ONLY
a valid JSON array — no prose, no markdown, no code fences, no explanation.

Each element of the array MUST have exactly these three keys:
  "interacting_drug" : string  (lowercase generic INN name of the other drug)
  "severity"         : string  (MUST be exactly "high" or "medium")
  "description"      : string  (one-sentence clinical consequence, ≤ 120 chars)

Severity classification rules:
  "high"   → contraindicated, life-threatening, avoid combination
  "medium" → use with caution, monitor, dose adjustment may be needed

If no interactions can be extracted, return an empty array: []
Do NOT include the primary drug itself in the array.
Do NOT add any text outside the JSON array.
""".strip()


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------


def open_db() -> psycopg2.extensions.connection:
    """
    Open a psycopg2 connection to PostgreSQL and apply the schema DDL.

    All CREATE TABLE / CREATE INDEX statements in schema.sql use IF NOT EXISTS,
    so this is fully idempotent and safe to call on every ETL run.
    """
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False

    schema_sql = SCHEMA_FILE.read_text(encoding="utf-8")

    with conn.cursor() as cur:
        cur.execute(schema_sql)
    conn.commit()

    log.info("Database opened: %s", DATABASE_URL.split("@")[-1])  # hide credentials
    return conn


# def upsert_drug(
#     cur: psycopg2.extensions.cursor,
#     generic_name: str,
#     brand_names: list[str],
# ) -> int:
#     """
#     Insert or update a drug record and return its row id.

#     On conflict (same generic_name) the brand_names JSONB is merged with the
#     existing value so repeated runs don't lose data.

#     Uses psycopg2's Json adapter so the JSONB column receives a proper object,
#     not a double-encoded string.
#     """
#     generic_name = generic_name.lower().strip()
#     new_brands   = sorted({b.strip() for b in brand_names if b.strip()})

#     cur.execute(
#         """
#         INSERT INTO drugs (generic_name, brand_names)
#         VALUES (%s, %s::jsonb)
#         ON CONFLICT (generic_name) DO UPDATE
#             SET brand_names = (
#                 SELECT jsonb_agg(DISTINCT elem ORDER BY elem)
#                 FROM (
#                     SELECT jsonb_array_elements_text(drugs.brand_names) AS elem
#                     UNION
#                     SELECT jsonb_array_elements_text(EXCLUDED.brand_names) AS elem
#                 ) merged
#             )
#         RETURNING id
#         """,
#         (generic_name, psycopg2.extras.Json(new_brands)),
#     )
#     return cur.fetchone()[0]

def upsert_drug(
    cur: psycopg2.extensions.cursor,
    generic_name: str,
    brand_names: list[str],
) -> int:
    """
    Insert or update a drug record and return its row id.
    Uses COALESCE to prevent null violations when merging empty arrays.
    """
    generic_name = generic_name.lower().strip()
    new_brands   = sorted({b.strip() for b in brand_names if b.strip()})

    cur.execute(
        """
        INSERT INTO drugs (generic_name, brand_names)
        VALUES (%s, %s::jsonb)
        ON CONFLICT (generic_name) DO UPDATE
            SET brand_names = COALESCE((
                SELECT jsonb_agg(DISTINCT elem ORDER BY elem)
                FROM (
                    SELECT jsonb_array_elements_text(drugs.brand_names) AS elem
                    UNION
                    SELECT jsonb_array_elements_text(EXCLUDED.brand_names) AS elem
                ) merged
            ), '[]'::jsonb)
        RETURNING id
        """,
        (generic_name, psycopg2.extras.Json(new_brands)),
    )
    return cur.fetchone()[0]

def upsert_interaction(
    cur: psycopg2.extensions.cursor,
    id_a: int,
    id_b: int,
    severity: str,
    description: str,
    action_text: str,
    source: str,
) -> None:
    """
    Insert an interaction row with canonical pair ordering (smaller id first).
    ON CONFLICT DO UPDATE ensures idempotency across replayed batches.
    """
    if id_a == id_b:
        return  # self-interaction — skip
    lo, hi = (id_a, id_b) if id_a < id_b else (id_b, id_a)
    cur.execute(
        """
        INSERT INTO interactions
            (drug_a_id, drug_b_id, severity, description, action_text, source)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (drug_a_id, drug_b_id) DO UPDATE
            SET severity    = EXCLUDED.severity,
                description = EXCLUDED.description,
                action_text = EXCLUDED.action_text,
                source      = EXCLUDED.source
        """,
        (lo, hi, severity, description[:500], action_text[:500], source),
    )


# ---------------------------------------------------------------------------
# Checkpoint helpers
# ---------------------------------------------------------------------------


def read_checkpoint(conn: psycopg2.extensions.connection) -> int:
    """
    Read last_successful_skip from etl_sync_state.

    Returns 0 if no checkpoint row exists yet (first run).
    """
    with conn.cursor() as cur:
        cur.execute("SELECT last_successful_skip FROM etl_sync_state WHERE id = 1")
        row = cur.fetchone()
    return row[0] if row else 0


def write_checkpoint(conn: psycopg2.extensions.connection, skip: int) -> None:
    """
    Persist the new checkpoint value.

    This is called INSIDE the same transaction as the batch data commit, so
    the checkpoint and the data are always consistent — either both land in
    the database or neither does.

    Uses an UPSERT so the first write creates the singleton row automatically.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO etl_sync_state (id, last_successful_skip, updated_at)
            VALUES (1, %s, NOW())
            ON CONFLICT (id) DO UPDATE
                SET last_successful_skip = EXCLUDED.last_successful_skip,
                    updated_at           = EXCLUDED.updated_at
            """,
            (skip,),
        )


# ---------------------------------------------------------------------------
# Stage 1: Seed from data.py INTERACTION_RULES
# ---------------------------------------------------------------------------


def seed_from_rules(conn: psycopg2.extensions.connection) -> None:
    """
    Bootstrap the database from the hardcoded INTERACTION_RULES in data.py.

    This makes the API fully functional immediately — before any FDA download.
    Each rule maps to potentially multiple drug pairs (Cartesian product of
    rule['a'] × rule['b'], excluding self-pairs).
    """
    log.info("=== SEED: importing data.py INTERACTION_RULES ===")

    try:
        from data import INTERACTION_RULES  # type: ignore[import]
    except ImportError:
        log.warning("data.py not found — skipping seed stage.")
        return

    action_map = {
        "high":   "Consult your prescriber or pharmacist before combining these medicines.",
        "medium": "Use with caution; monitor for adverse effects and review with a clinician.",
    }

    inserted_pairs = 0
    with conn.cursor() as cur:
        for rule in INTERACTION_RULES:
            level: str      = rule.get("level", "medium")
            message: str    = rule.get("message", "")
            action: str     = rule.get("action", action_map.get(level, ""))
            drugs_a: list[str] = rule.get("a", [])
            drugs_b: list[str] = rule.get("b", [])

            ids_a = [upsert_drug(cur, name, []) for name in drugs_a]
            ids_b = [upsert_drug(cur, name, []) for name in drugs_b]

            for id_a in ids_a:
                for id_b in ids_b:
                    if id_a == id_b:
                        continue
                    upsert_interaction(
                        cur, id_a, id_b,
                        severity=level,
                        description=message,
                        action_text=action,
                        source="RxCheck seed data",
                    )
                    inserted_pairs += 1

    conn.commit()
    log.info("Seed complete: %d interaction pairs inserted/updated.", inserted_pairs)


# ---------------------------------------------------------------------------
# Stage 2: Fetch from openFDA
# ---------------------------------------------------------------------------


def fetch_fda_batch(skip: int = 0, limit: int = 100) -> list[dict[str, Any]]:
    """
    Download a batch of drug label records from the openFDA SPL endpoint.

    Returns a list of raw result dicts.  Raises on HTTP / timeout errors.
    """
    log.info("Fetching FDA batch: skip=%d  limit=%d", skip, limit)
    params = {"limit": limit, "skip": skip}
    try:
        resp = requests.get(FDA_BASE, params=params, timeout=FDA_REQUEST_TIMEOUT)
        resp.raise_for_status()
    except requests.exceptions.Timeout:
        log.error("FDA API timed out after %ds.", FDA_REQUEST_TIMEOUT)
        raise
    except requests.exceptions.HTTPError as exc:
        log.error("FDA API returned HTTP %s: %s", exc.response.status_code, exc)
        raise

    data    = resp.json()
    results = data.get("results", [])
    log.info("Received %d records from FDA.", len(results))
    return results


# ---------------------------------------------------------------------------
# Stage 3: Transform / Extract
# ---------------------------------------------------------------------------


def _first_string(value: Any) -> str:
    """Return the first element if value is a list, else the value itself, as str."""
    if isinstance(value, list):
        return str(value[0]) if value else ""
    return str(value) if value else ""


def _extract_list(value: Any) -> list[str]:
    """Normalise an FDA field that may be a list or a single string."""
    if isinstance(value, list):
        return [str(v) for v in value if v]
    if value:
        return [str(value)]
    return []


def transform_record(record: dict[str, Any]) -> dict[str, Any] | None:
    """
    Extract structured fields from a raw openFDA label record.

    Returns None if the record lacks a usable drug name.

    Output dict:
      generic_name      : str
      brand_names       : list[str]
      interactions_text : str | None  (raw free text; may be None)
    """
    openfda = record.get("openfda", {})

    generic_names   = _extract_list(openfda.get("generic_name"))
    brand_names     = _extract_list(openfda.get("brand_name"))
    substance_names = _extract_list(openfda.get("substance_name"))

    if generic_names:
        primary_generic = generic_names[0].lower().strip()
    elif substance_names:
        primary_generic = substance_names[0].lower().strip()
    elif brand_names:
        primary_generic = brand_names[0].lower().strip()
    else:
        return None  # unusable record

    raw_interactions = record.get("drug_interactions")
    interactions_text: str | None = None
    if raw_interactions:
        text = _first_string(raw_interactions).strip()
        if text and len(text) > 30:
            interactions_text = text

    return {
        "generic_name":      primary_generic,
        "brand_names":       brand_names,
        "interactions_text": interactions_text,
    }


# ---------------------------------------------------------------------------
# Stage 4: LLM parsing via Groq
# ---------------------------------------------------------------------------

_groq_client: Groq | None = None


def _get_groq_client() -> Groq:
    global _groq_client
    if _groq_client is None:
        api_key = os.getenv("GROQ_API_KEY", "").strip()
        if not api_key:
            raise EnvironmentError(
                "GROQ_API_KEY is not set. Add it to your .env file or environment."
            )
        _groq_client = Groq(api_key=api_key)
    return _groq_client


_JSON_ARRAY_RE = re.compile(r"\[.*?\]", re.DOTALL)


def _parse_llm_response(raw: str) -> list[dict[str, str]]:
    """
    Robustly extract a JSON array from the LLM's response string.

    The model is instructed to return only JSON, but may wrap it in markdown
    fences or add a small amount of prose.  We extract the first [ … ] block.
    """
    raw   = raw.strip()
    match = _JSON_ARRAY_RE.search(raw)
    if not match:
        return []
    try:
        parsed = json.loads(match.group())
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    valid = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        drug     = str(item.get("interacting_drug", "")).strip().lower()
        severity = str(item.get("severity", "medium")).strip().lower()
        desc     = str(item.get("description", "")).strip()
        if not drug or not desc:
            continue
        if severity not in ("high", "medium", "low"):
            severity = "medium"
        valid.append({"interacting_drug": drug, "severity": severity, "description": desc})
    return valid


# def call_groq_with_retry(text: str, drug_name: str) -> list[dict[str, str]]:
#     """
#     Send the interaction text to Groq and return parsed structured interactions.

#     Implements exponential back-off on 429 (rate limit) and transient errors.
#     Returns an empty list on unrecoverable failure so the pipeline continues.
#     """
#     client       = _get_groq_client()
#     user_content = (
#         f"Primary drug: {drug_name}\n\n"
#         f"--- FDA DRUG INTERACTIONS TEXT ---\n{text[:3000]}\n---"
#     )

#     for attempt in range(1, GROQ_MAX_RETRIES + 1):
#         try:
#             response = client.chat.completions.create(
#                 model=GROQ_MODEL,
#                 max_tokens=GROQ_MAX_TOKENS,
#                 temperature=0.0,
#                 messages=[
#                     {"role": "system", "content": GROQ_SYSTEM_PROMPT},
#                     {"role": "user",   "content": user_content},
#                 ],
#             )
#             raw_reply = response.choices[0].message.content or ""
#             result    = _parse_llm_response(raw_reply)
#             log.debug("LLM extracted %d interactions for '%s'.", len(result), drug_name)
#             return result

#         except Exception as exc:  # noqa: BLE001
#             err_str       = str(exc)
#             is_rate_limit = "429" in err_str or "rate_limit" in err_str.lower()
#             wait          = GROQ_BACKOFF_BASE ** attempt + (2.0 if is_rate_limit else 0.0)
#             if attempt < GROQ_MAX_RETRIES:
#                 log.warning(
#                     "Groq call failed (attempt %d/%d): %s — retrying in %.1fs",
#                     attempt, GROQ_MAX_RETRIES, exc, wait,
#                 )
#                 time.sleep(wait)
#             else:
#                 log.error("Groq call failed permanently for '%s': %s", drug_name, exc)
#                 return []

#     return []

def call_llm_with_retry(text: str, drug_name: str) -> list[dict[str, str]]:
    """
    Send the interaction text to the Multi-Provider Router.
    The router handles its own failovers and rate limits.
    """
    user_content = (
        f"Primary drug: {drug_name}\n\n"
        f"--- FDA DRUG INTERACTIONS TEXT ---\n{text[:3000]}\n---"
    )

    try:
        raw_reply = extract_clinical_data(GROQ_SYSTEM_PROMPT, user_content)
        result = _parse_llm_response(raw_reply)
        log.debug("LLM router extracted %d interactions for '%s'.", len(result), drug_name)
        return result
    except Exception as exc:
        log.error("All LLM providers exhausted for '%s': %s", drug_name, exc)
        # Return empty list so the ETL pipeline doesn't crash, it just skips this record
        return []

# ---------------------------------------------------------------------------
# Stage 5-7: Load into PostgreSQL + commit checkpoint atomically
# ---------------------------------------------------------------------------


def load_fda_records(
    conn: psycopg2.extensions.connection,
    records: list[dict[str, Any]],
    batch_skip: int,
    dry_run: bool = False,
) -> None:
    """
    Process a list of raw FDA records through the transform → LLM → load pipeline.

    After all records in the batch are processed and written, the checkpoint
    (etl_sync_state.last_successful_skip) is updated to batch_skip + len(records)
    in the SAME transaction as the data writes.  This ensures atomicity:
    a crash during processing leaves the checkpoint unchanged and the next run
    replays the batch from scratch (idempotent upserts handle duplicates).

    dry_run=True runs all stages but skips all database writes and checkpoint
    updates.
    """
    total = len(records)
    log.info("=== LOAD: processing %d FDA records (batch_skip=%d) ===", total, batch_skip)

    with conn.cursor() as cur:
        for idx, raw in enumerate(records, 1):
            transformed = transform_record(raw)
            if transformed is None:
                log.debug("Record %d/%d: skipped (no usable drug name).", idx, total)
                continue

            generic = transformed["generic_name"]
            brands  = transformed["brand_names"]
            itext   = transformed["interactions_text"]

            log.info(
                "[%d/%d] %s  (%d brands, has_interactions=%s)",
                idx, total, generic, len(brands), itext is not None,
            )

            # Upsert the primary drug
            if not dry_run:
                primary_id = upsert_drug(cur, generic, brands)

            # If there is no interaction text, nothing more to do for this record
            if not itext:
                continue

            # --- LLM stage ---
            time.sleep(GROQ_RATE_LIMIT_SLEEP)  # honour rate limit before each call
            # structured = call_groq_with_retry(itext, generic)
            structured = call_llm_with_retry(itext, generic)

            if not structured:
                log.info("  └─ No interactions extracted (LLM returned empty).")
                continue

            log.info("  └─ LLM extracted %d interactions.", len(structured))

            if dry_run:
                for item in structured:
                    log.info(
                        "    [DRY-RUN] %s ↔ %s  severity=%s",
                        generic, item["interacting_drug"], item["severity"],
                    )
                continue

            # --- DB write stage ---
            for item in structured:
                other_drug = item["interacting_drug"].strip().lower()
                if not other_drug or other_drug == generic:
                    continue
                other_id = upsert_drug(cur, other_drug, [])
                upsert_interaction(
                    cur, primary_id, other_id,
                    severity=item["severity"],
                    description=item["description"],
                    action_text="Consult your prescriber or pharmacist before combining these medicines.",
                    source="openFDA SPL",
                )

        # ---------------------------------------------------------------
        # Atomic checkpoint update — runs inside the same cursor / transaction
        # as all the batch writes above.  If anything above raised an exception,
        # conn.rollback() is called by the caller and this is never reached.
        # ---------------------------------------------------------------
        if not dry_run:
            next_skip = batch_skip + total
            write_checkpoint(conn, next_skip)
            log.info("Checkpoint advanced to skip=%d.", next_skip)

    # Single commit for the entire batch + checkpoint
    if not dry_run:
        conn.commit()

    log.info("=== LOAD complete ===")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "RxCheck ETL: download openFDA SPL data and populate PostgreSQL.\n"
            "Resumes automatically from the last successful batch checkpoint."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--skip", type=int, default=None,
        help=(
            "FDA offset to start from.  If the checkpoint in etl_sync_state "
            "is GREATER than this value, the checkpoint wins (safe resume). "
            "Defaults to the checkpoint value (0 on first run)."
        ),
    )
    parser.add_argument(
        "--limit", type=int, default=int(os.getenv("FDA_LIMIT", "100")),
        help="Number of FDA records to fetch per run.",
    )
    parser.add_argument(
        "--seed-only", action="store_true",
        help="Only seed from data.py INTERACTION_RULES; skip FDA fetch.",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Run all stages but skip database writes.",
    )
    parser.add_argument(
        "--reset-checkpoint", action="store_true",
        help="Reset etl_sync_state to skip=0 before running (use with care).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    log.info(
        "RxCheck ETL starting  db=%s  dry_run=%s",
        DATABASE_URL.split("@")[-1],   # hide credentials from logs
        args.dry_run,
    )

    # Open DB (also applies schema DDL idempotently)
    if args.dry_run:
        # For dry-run, still open the DB to read the checkpoint, but we
        # won't write anything.  Use an in-memory PG connection if the real
        # DB is unreachable — fall back to skip=0.
        try:
            conn = open_db()
        except Exception as exc:
            log.warning("Could not connect to DB for dry-run checkpoint read: %s", exc)
            conn = None
    else:
        conn = open_db()

    try:
        # ---------------------------------------------------------------
        # Reset checkpoint if requested (destructive — confirm in logs)
        # ---------------------------------------------------------------
        if args.reset_checkpoint and conn is not None and not args.dry_run:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO etl_sync_state (id, last_successful_skip, updated_at)
                    VALUES (1, 0, NOW())
                    ON CONFLICT (id) DO UPDATE
                        SET last_successful_skip = 0,
                            updated_at = NOW()
                    """
                )
            conn.commit()
            log.warning("Checkpoint RESET to skip=0.")

        # ---------------------------------------------------------------
        # Stage 1: Seed from hardcoded rules
        # ---------------------------------------------------------------
        if not args.dry_run and conn is not None:
            seed_from_rules(conn)
        else:
            log.info("[DRY-RUN] Skipping seed stage.")

        if args.seed_only:
            log.info("--seed-only flag set; skipping FDA fetch.")
            return

        # ---------------------------------------------------------------
        # Stage 2: Resolve effective skip offset
        # The checkpoint always wins if it is ahead of --skip.
        # This prevents a user accidentally passing --skip 0 and doubling
        # all data that was already ingested.
        # ---------------------------------------------------------------
        checkpoint_skip = read_checkpoint(conn) if conn is not None else 0
        cli_skip        = args.skip if args.skip is not None else 0
        effective_skip  = max(checkpoint_skip, cli_skip)

        if effective_skip != cli_skip:
            log.info(
                "Checkpoint (%d) is ahead of --skip (%d); resuming from checkpoint.",
                effective_skip, cli_skip,
            )
        else:
            log.info("Starting from skip=%d.", effective_skip)

        # ---------------------------------------------------------------
        # Stage 3: Fetch from openFDA
        # ---------------------------------------------------------------
        records = fetch_fda_batch(skip=effective_skip, limit=args.limit)

        if not records:
            log.warning("No records returned from FDA API.")
            return

        # ---------------------------------------------------------------
        # Stages 4-7: Transform → LLM → Load → Checkpoint
        # ---------------------------------------------------------------
        if conn is not None:
            load_fda_records(conn, records, batch_skip=effective_skip, dry_run=args.dry_run)
        else:
            log.info("[DRY-RUN] No DB connection; parsing preview only.")
            # Simulate via an in-memory parse pass (no DB writes, no checkpoint)
            for raw in records:
                t = transform_record(raw)
                if t and t["interactions_text"]:
                    # structured = call_groq_with_retry(t["interactions_text"], t["generic_name"])
                    structured = call_llm_with_retry(t["interactions_text"], t["generic_name"])

                    for item in structured:
                        log.info(
                            "  [DRY-RUN] %s ↔ %s  severity=%s",
                            t["generic_name"], item["interacting_drug"], item["severity"],
                        )

    except Exception:
        log.exception("ETL pipeline aborted.  Checkpoint NOT advanced.")
        sys.exit(1)
    finally:
        if conn is not None:
            conn.close()
            log.info("Database connection closed.")

    log.info("ETL pipeline finished.")


if __name__ == "__main__":
    main()
