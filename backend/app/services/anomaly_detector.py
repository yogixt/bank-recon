"""Anomaly detection: rule-based + statistical methods."""

import uuid

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

        # 0. Session-level scope mismatch (wrong period/account/source combination)
        anomalies.extend(_detect_scope_mismatch(cur, session_id))

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


def _detect_scope_mismatch(cur, session_id: uuid.UUID) -> list[dict]:
    """Detect sessions where sources are very likely from different scopes.

    Example: one-day statement reconciled against a full historical bridge dump.
    """
    cur.execute(
        """SELECT total_searched, success_count, failed_count, reversal_count,
                  not_in_bridge_count, not_in_statement_count
           FROM reconciliation_sessions
           WHERE id = %s""",
        (str(session_id),),
    )
    row = cur.fetchone()
    if not row:
        return []

    total = int(row["total_searched"] or 0)
    if total < 100:
        return []

    matched = int(row["success_count"] or 0) + int(row["failed_count"] or 0) + int(row["reversal_count"] or 0)
    not_in_bridge = int(row["not_in_bridge_count"] or 0)
    not_in_statement = int(row["not_in_statement_count"] or 0)

    # Hard mismatch: nothing matched at all despite large input.
    if matched == 0 and (not_in_bridge + not_in_statement) > 0:
        return [{
            "anomaly_type": "source_scope_mismatch",
            "severity": "high",
            "description": (
                f"0 matches out of {total:,} searched transactions. "
                "Selected sources likely belong to different scope (period/account/file set mismatch)."
            ),
        }]

    # Soft mismatch: almost everything missing from statement at scale.
    if total >= 500 and not_in_statement / total >= 0.95:
        return [{
            "anomaly_type": "source_scope_mismatch",
            "severity": "high",
            "description": (
                f"{not_in_statement:,}/{total:,} transactions are missing from statement. "
                "This strongly suggests bank statement period/account does not match the bridge/transaction dataset."
            ),
        }]

    return []


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
    """Summarize bridge mappings where bank_id doesn't exist in the selected statement."""
    cur.execute(
        """
        SELECT COUNT(*) AS orphan_count
        FROM bridge_mappings bm
        LEFT JOIN bank_entries be ON be.data_source_id = %s AND be.bank_id = bm.bank_id
        WHERE bm.data_source_id = %s AND be.id IS NULL
        """,
        (str(bank_source_id), str(bridge_source_id)),
    )
    count_row = cur.fetchone()
    orphan_count = int(count_row["orphan_count"] or 0) if count_row else 0
    if orphan_count == 0:
        return []

    cur.execute(
        """
        SELECT bm.transaction_id, bm.bank_id
        FROM bridge_mappings bm
        LEFT JOIN bank_entries be ON be.data_source_id = %s AND be.bank_id = bm.bank_id
        WHERE bm.data_source_id = %s AND be.id IS NULL
        LIMIT 5
        """,
        (str(bank_source_id), str(bridge_source_id)),
    )
    samples = cur.fetchall()
    examples = ", ".join(f"{row['transaction_id']}->{row['bank_id']}" for row in samples)
    description = f"{orphan_count:,} bridge mappings point to bank IDs missing from the selected statement"
    if examples:
        description += f" (examples: {examples})"

    return [{
        "anomaly_type": "orphan_bridge",
        "severity": "low",
        "description": description,
    }]


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
