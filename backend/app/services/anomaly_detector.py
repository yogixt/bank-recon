"""Anomaly detection: rule-based + statistical methods."""

import uuid
from collections import Counter

import psycopg2
from psycopg2.extras import RealDictCursor

from app.config import get_settings
from app.core.constants import ANOMALY_AMOUNT_ZSCORE


def _get_source_ids(session_id: uuid.UUID) -> tuple[uuid.UUID, uuid.UUID]:
    """Get bank_source_id and bridge_source_id from the session."""
    conn = psycopg2.connect(get_settings().SYNC_DATABASE_URL)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT bank_source_id, bridge_source_id FROM reconciliation_sessions WHERE id = %s",
            (str(session_id),),
        )
        row = cur.fetchone()
        if not row or not row[0] or not row[1]:
            raise ValueError("Session does not have source references")
        return uuid.UUID(str(row[0])), uuid.UUID(str(row[1]))
    finally:
        conn.close()


def detect_anomalies(session_id: uuid.UUID) -> list[dict]:
    """Run all anomaly detection methods and return combined results."""
    bank_source_id, bridge_source_id = _get_source_ids(session_id)

    conn = psycopg2.connect(get_settings().SYNC_DATABASE_URL)
    anomalies: list[dict] = []

    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # 1. Duplicate bank IDs in results
        anomalies.extend(_detect_duplicate_bank_ids(cur, session_id))

        # 2. Suspicious amounts (statistical outliers)
        anomalies.extend(_detect_amount_outliers(cur, session_id))

        # 3. Orphan bridge entries (bridge maps to bank_id not in statement at all)
        anomalies.extend(_detect_orphan_bridge_entries(cur, bridge_source_id, bank_source_id))

        # 4. Duplicate transaction IDs in input
        anomalies.extend(_detect_duplicate_transaction_ids(cur, session_id))

        # 5. Mismatched status (both debit and credit present)
        anomalies.extend(_detect_mismatched_status(cur, session_id))

        return anomalies
    finally:
        conn.close()


def _detect_duplicate_bank_ids(cur, session_id: uuid.UUID) -> list[dict]:
    """Find bank_ids that map to multiple different transaction_ids."""
    cur.execute(
        """
        SELECT bank_id, COUNT(DISTINCT transaction_id) AS txn_count
        FROM reconciliation_results
        WHERE session_id = %s AND bank_id IS NOT NULL
          AND status IN ('MATCHED_SUCCESS', 'MATCHED_FAILED')
        GROUP BY bank_id
        HAVING COUNT(DISTINCT transaction_id) > 1
        """,
        (str(session_id),),
    )
    results = []
    for row in cur.fetchall():
        results.append({
            "anomaly_type": "duplicate_bank_id",
            "severity": "high",
            "description": f"Bank ID '{row['bank_id']}' is mapped to {row['txn_count']} different transaction IDs",
            "bank_id": row["bank_id"],
        })
    return results


def _detect_amount_outliers(cur, session_id: uuid.UUID) -> list[dict]:
    """Find transactions with amounts that are statistical outliers (z-score > threshold)."""
    cur.execute(
        """
        SELECT AVG(debit_amount) AS mean_debit, STDDEV(debit_amount) AS std_debit,
               AVG(credit_amount) AS mean_credit, STDDEV(credit_amount) AS std_credit
        FROM reconciliation_results
        WHERE session_id = %s AND status IN ('MATCHED_SUCCESS', 'MATCHED_FAILED')
        """,
        (str(session_id),),
    )
    stats = cur.fetchone()
    if not stats or (not stats["std_debit"] and not stats["std_credit"]):
        return []

    results = []
    # Check debits
    if stats["std_debit"] and stats["std_debit"] > 0:
        threshold = stats["mean_debit"] + ANOMALY_AMOUNT_ZSCORE * stats["std_debit"]
        cur.execute(
            """
            SELECT transaction_id, bank_id, debit_amount
            FROM reconciliation_results
            WHERE session_id = %s AND debit_amount > %s
            LIMIT 50
            """,
            (str(session_id), threshold),
        )
        for row in cur.fetchall():
            results.append({
                "anomaly_type": "suspicious_amount",
                "severity": "medium",
                "description": f"Unusually high debit amount: {row['debit_amount']:,.2f}",
                "transaction_id": row["transaction_id"],
                "bank_id": row["bank_id"],
                "amount": row["debit_amount"],
            })

    # Check credits
    if stats["std_credit"] and stats["std_credit"] > 0:
        threshold = stats["mean_credit"] + ANOMALY_AMOUNT_ZSCORE * stats["std_credit"]
        cur.execute(
            """
            SELECT transaction_id, bank_id, credit_amount
            FROM reconciliation_results
            WHERE session_id = %s AND credit_amount > %s
            LIMIT 50
            """,
            (str(session_id), threshold),
        )
        for row in cur.fetchall():
            results.append({
                "anomaly_type": "suspicious_amount",
                "severity": "medium",
                "description": f"Unusually high credit amount: {row['credit_amount']:,.2f}",
                "transaction_id": row["transaction_id"],
                "bank_id": row["bank_id"],
                "amount": row["credit_amount"],
            })

    return results


def _detect_orphan_bridge_entries(cur, bridge_source_id: uuid.UUID, bank_source_id: uuid.UUID) -> list[dict]:
    """Find bridge mappings where the bank_id doesn't exist in bank_entries at all."""
    cur.execute(
        """
        SELECT bm.transaction_id, bm.bank_id
        FROM bridge_mappings bm
        LEFT JOIN bank_entries be ON be.data_source_id = %s AND be.bank_id = bm.bank_id
        WHERE bm.data_source_id = %s AND be.id IS NULL
        LIMIT 100
        """,
        (str(bank_source_id), str(bridge_source_id)),
    )
    results = []
    for row in cur.fetchall():
        results.append({
            "anomaly_type": "orphan_bridge",
            "severity": "low",
            "description": f"Bridge maps txn '{row['transaction_id']}' to bank ID '{row['bank_id']}' which doesn't exist in statement",
            "transaction_id": row["transaction_id"],
            "bank_id": row["bank_id"],
        })
    return results


def _detect_duplicate_transaction_ids(cur, session_id: uuid.UUID) -> list[dict]:
    """Find transaction IDs that appear more than once in the input."""
    cur.execute(
        """
        SELECT transaction_id, COUNT(*) AS cnt
        FROM transaction_ids
        WHERE session_id = %s
        GROUP BY transaction_id
        HAVING COUNT(*) > 1
        LIMIT 50
        """,
        (str(session_id),),
    )
    results = []
    for row in cur.fetchall():
        results.append({
            "anomaly_type": "duplicate_transaction_id",
            "severity": "medium",
            "description": f"Transaction ID '{row['transaction_id']}' appears {row['cnt']} times in input",
            "transaction_id": row["transaction_id"],
        })
    return results


def _detect_mismatched_status(cur, session_id: uuid.UUID) -> list[dict]:
    """Find entries where both debit and credit are non-zero."""
    cur.execute(
        """
        SELECT transaction_id, bank_id, debit_amount, credit_amount
        FROM reconciliation_results
        WHERE session_id = %s AND debit_amount > 0 AND credit_amount > 0
        LIMIT 50
        """,
        (str(session_id),),
    )
    results = []
    for row in cur.fetchall():
        results.append({
            "anomaly_type": "mismatched_status",
            "severity": "high",
            "description": f"Both debit ({row['debit_amount']:,.2f}) and credit ({row['credit_amount']:,.2f}) present",
            "transaction_id": row["transaction_id"],
            "bank_id": row["bank_id"],
            "amount": row["debit_amount"],
        })
    return results
