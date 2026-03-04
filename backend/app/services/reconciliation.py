"""Core reconciliation engine - operates on PostgreSQL, not in-memory DataFrames.

Uses batch SQL lookups for bank entries instead of loading everything into RAM.
"""

import uuid
from typing import Any

import psycopg2
from psycopg2.extras import RealDictCursor

from app.config import get_settings
from app.core.constants import RECONCILE_LOOKUP_BATCH


def _get_conn():
    return psycopg2.connect(get_settings().SYNC_DATABASE_URL)


def load_bridge_map(data_source_id: uuid.UUID) -> dict[str, str]:
    """Load bridge mappings into a Python dict for O(1) lookup."""
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT transaction_id, bank_id FROM bridge_mappings WHERE data_source_id = %s",
            (str(data_source_id),),
        )
        return {row[0]: row[1] for row in cur.fetchall()}
    finally:
        conn.close()


def load_transaction_ids(session_id: uuid.UUID) -> list[str]:
    """Load transaction IDs for this session."""
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT DISTINCT transaction_id FROM transaction_ids WHERE session_id = %s",
            (str(session_id),),
        )
        return [row[0] for row in cur.fetchall()]
    finally:
        conn.close()


def batch_lookup_bank_entries(
    data_source_id: uuid.UUID, bank_ids: list[str]
) -> dict[str, list[dict[str, Any]]]:
    """Look up bank entries by bank_id in batches using ANY() operator.

    Returns {bank_id: [list of matching entry dicts]}.
    """
    if not bank_ids:
        return {}

    conn = _get_conn()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        grouped: dict[str, list[dict]] = {}

        for i in range(0, len(bank_ids), RECONCILE_LOOKUP_BATCH):
            batch = bank_ids[i : i + RECONCILE_LOOKUP_BATCH]
            cur.execute(
                "SELECT bank_id, date, description, debit_amount, credit_amount, "
                "branch, reference_no, customer_name "
                "FROM bank_entries "
                "WHERE data_source_id = %s AND bank_id = ANY(%s)",
                (str(data_source_id), batch),
            )
            for row in cur.fetchall():
                bid = row["bank_id"]
                grouped.setdefault(bid, []).append(dict(row))

        return grouped
    finally:
        conn.close()


def determine_status(debit: float, credit: float) -> str:
    """Determine transaction status from debit/credit amounts."""
    if debit > 0 and credit == 0:
        return "MATCHED_SUCCESS"
    if credit > 0 and debit == 0:
        return "MATCHED_FAILED"
    if debit > 0 and credit > 0:
        return "REVERSAL"
    return "MATCHED_SUCCESS"  # default for ambiguous


def _get_session_source_ids(session_id: uuid.UUID) -> tuple[uuid.UUID, uuid.UUID]:
    """Get bank_source_id and bridge_source_id from the session."""
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT bank_source_id, bridge_source_id FROM reconciliation_sessions WHERE id = %s",
            (str(session_id),),
        )
        row = cur.fetchone()
        if not row or not row[0] or not row[1]:
            raise ValueError("Session does not have bank/bridge source references")
        return uuid.UUID(str(row[0])), uuid.UUID(str(row[1]))
    finally:
        conn.close()


def run_reconciliation(session_id: uuid.UUID) -> dict[str, Any]:
    """Execute the core reconciliation algorithm.

    1. Load bridge map from permanent data source
    2. Load transaction IDs from session
    3. For each txn: look up in bridge → look up bank entry → determine status
    4. Return all results + statistics
    """
    bank_source_id, bridge_source_id = _get_session_source_ids(session_id)

    bridge_map = load_bridge_map(bridge_source_id)
    txn_ids = load_transaction_ids(session_id)

    # Collect all needed bank_ids from bridge lookups
    needed_bank_ids = set()
    txn_to_bank: dict[str, str | None] = {}
    not_in_bridge: list[str] = []

    for txn_id in txn_ids:
        if txn_id in bridge_map:
            bank_id = bridge_map[txn_id]
            txn_to_bank[txn_id] = bank_id
            needed_bank_ids.add(bank_id)
        else:
            not_in_bridge.append(txn_id)
            txn_to_bank[txn_id] = None

    # Batch lookup all needed bank entries from permanent data source
    bank_entries = batch_lookup_bank_entries(bank_source_id, list(needed_bank_ids))

    # Build results
    results: list[dict] = []
    not_in_statement: list[str] = []

    for txn_id in txn_ids:
        bank_id = txn_to_bank.get(txn_id)

        if bank_id is None:
            # Not in bridge
            results.append({
                "transaction_id": txn_id,
                "bank_id": None,
                "date": None,
                "debit_amount": 0.0,
                "credit_amount": 0.0,
                "status": "NOT_IN_BRIDGE",
                "customer_name": None,
                "branch": None,
                "reference_no": None,
                "description": None,
                "error_type": "Bridge file does not contain this transaction ID",
            })
            continue

        entries = bank_entries.get(bank_id, [])
        if not entries:
            not_in_statement.append(txn_id)
            results.append({
                "transaction_id": txn_id,
                "bank_id": bank_id,
                "date": None,
                "debit_amount": 0.0,
                "credit_amount": 0.0,
                "status": "NOT_IN_STATEMENT",
                "customer_name": None,
                "branch": None,
                "reference_no": None,
                "description": None,
                "error_type": "Bank ID found in bridge but not in bank statement",
            })
            continue

        # Cross-entry reversal detection: if the same txn_id has entries
        # with debit > 0 AND entries with credit > 0, all entries = REVERSAL
        has_debit = any((e.get("debit_amount") or 0.0) > 0 for e in entries)
        has_credit = any((e.get("credit_amount") or 0.0) > 0 for e in entries)

        if has_debit and has_credit:
            cross_status = "REVERSAL"
        elif has_debit:
            cross_status = "MATCHED_SUCCESS"
        elif has_credit:
            cross_status = "MATCHED_FAILED"
        else:
            cross_status = None  # fall back to per-entry logic

        # Return ALL matches
        for entry in entries:
            debit = entry.get("debit_amount", 0.0) or 0.0
            credit = entry.get("credit_amount", 0.0) or 0.0
            status = cross_status if cross_status else determine_status(debit, credit)
            results.append({
                "transaction_id": txn_id,
                "bank_id": bank_id,
                "date": entry.get("date"),
                "debit_amount": debit,
                "credit_amount": credit,
                "status": status,
                "customer_name": entry.get("customer_name"),
                "branch": entry.get("branch"),
                "reference_no": entry.get("reference_no"),
                "description": entry.get("description"),
                "error_type": None,
            })

    # Statistics
    success_count = sum(1 for r in results if r["status"] == "MATCHED_SUCCESS")
    failed_count = sum(1 for r in results if r["status"] == "MATCHED_FAILED")
    reversal_count = sum(1 for r in results if r["status"] == "REVERSAL")
    
    total_success_amount = sum(r["debit_amount"] for r in results if r["status"] == "MATCHED_SUCCESS")
    total_failed_amount = sum(r["credit_amount"] for r in results if r["status"] == "MATCHED_FAILED")
    total_reversal_amount = sum(r["debit_amount"] + r["credit_amount"] for r in results if r["status"] == "REVERSAL")

    stats = {
        "total_searched": len(txn_ids),
        "total_found": success_count + failed_count + reversal_count,
        "success_count": success_count,
        "failed_count": failed_count,
        "reversal_count": reversal_count,
        "not_in_bridge": len(not_in_bridge),
        "not_in_statement": len(not_in_statement),
        "total_success_amount": total_success_amount,
        "total_failed_amount": total_failed_amount,
        "total_reversal_amount": total_reversal_amount,
    }

    return {"results": results, "statistics": stats}
