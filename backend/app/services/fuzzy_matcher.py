"""Fuzzy matching service using pg_trgm for NOT_IN_STATEMENT records."""

import uuid

import psycopg2
from psycopg2.extras import RealDictCursor

from app.config import get_settings
from app.core.constants import FUZZY_SIMILARITY_THRESHOLD, FUZZY_MAX_CANDIDATES


def _get_bank_source_id(session_id: uuid.UUID) -> uuid.UUID:
    """Get bank_source_id from the session."""
    conn = psycopg2.connect(get_settings().SYNC_DATABASE_URL)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT bank_source_id FROM reconciliation_sessions WHERE id = %s",
            (str(session_id),),
        )
        row = cur.fetchone()
        if not row or not row[0]:
            raise ValueError("Session does not have a bank source reference")
        return uuid.UUID(str(row[0]))
    finally:
        conn.close()


def find_fuzzy_matches(session_id: uuid.UUID) -> list[dict]:
    """Find fuzzy matches for bank_ids that were NOT_IN_STATEMENT.

    Uses pg_trgm similarity() with a GIN index for fast trigram lookups.
    Returns a list of {transaction_id, bank_id, candidate_bank_id, similarity} dicts.
    """
    bank_source_id = _get_bank_source_id(session_id)

    conn = psycopg2.connect(get_settings().SYNC_DATABASE_URL)
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Get all NOT_IN_STATEMENT results for this session
        cur.execute(
            "SELECT DISTINCT transaction_id, bank_id FROM reconciliation_results "
            "WHERE session_id = %s AND status = 'NOT_IN_STATEMENT' AND bank_id IS NOT NULL",
            (str(session_id),),
        )
        unmatched = cur.fetchall()

        if not unmatched:
            return []

        results = []
        for row in unmatched:
            bank_id = row["bank_id"]
            # Use pg_trgm similarity — query bank_entries by data_source_id
            cur.execute(
                """
                SELECT bank_id AS candidate_bank_id,
                       similarity(bank_id, %s) AS sim,
                       date, description, debit_amount, credit_amount
                FROM bank_entries
                WHERE data_source_id = %s
                  AND bank_id %% %s
                  AND similarity(bank_id, %s) >= %s
                ORDER BY sim DESC
                LIMIT %s
                """,
                (
                    bank_id, str(bank_source_id), bank_id, bank_id,
                    FUZZY_SIMILARITY_THRESHOLD, FUZZY_MAX_CANDIDATES,
                ),
            )
            candidates = cur.fetchall()
            for c in candidates:
                results.append({
                    "transaction_id": row["transaction_id"],
                    "bank_id": bank_id,
                    "candidate_bank_id": c["candidate_bank_id"],
                    "similarity": round(c["sim"], 3),
                    "date": c["date"],
                    "description": c["description"],
                    "debit_amount": c["debit_amount"],
                    "credit_amount": c["credit_amount"],
                })

        return results
    finally:
        conn.close()
