"""Bulk database operations using psycopg2 COPY protocol for maximum throughput."""

import io
import uuid

import psycopg2
from psycopg2.extras import execute_values

from app.config import get_settings


def get_sync_conn():
    """Get a synchronous psycopg2 connection for COPY operations."""
    settings = get_settings()
    return psycopg2.connect(settings.SYNC_DATABASE_URL)


def bulk_insert_bank_entries(data_source_id: uuid.UUID, rows: list[dict]) -> int:
    """Insert bank entries using COPY protocol (5-10x faster than INSERT)."""
    if not rows:
        return 0

    conn = get_sync_conn()
    try:
        buf = io.StringIO()
        for r in rows:
            # tab-separated: data_source_id, bank_id, date, description, debit, credit, branch, ref, customer
            line = "\t".join([
                str(data_source_id),
                r.get("bank_id") or "\\N",
                r.get("date") or "\\N",
                (r.get("description") or "").replace("\t", " ").replace("\n", " "),
                str(r.get("debit_amount", 0.0)),
                str(r.get("credit_amount", 0.0)),
                (r.get("branch") or "").replace("\t", " "),
                (r.get("reference_no") or "").replace("\t", " "),
                (r.get("customer_name") or "").replace("\t", " "),
            ])
            buf.write(line + "\n")
        buf.seek(0)

        cur = conn.cursor()
        cur.copy_from(
            buf,
            "bank_entries",
            columns=(
                "data_source_id", "bank_id", "date", "description",
                "debit_amount", "credit_amount", "branch", "reference_no", "customer_name",
            ),
        )
        conn.commit()
        return len(rows)
    finally:
        conn.close()


def bulk_insert_bridge_mappings(data_source_id: uuid.UUID, bridge_map: dict[str, str]) -> int:
    if not bridge_map:
        return 0
    conn = get_sync_conn()
    try:
        cur = conn.cursor()
        values = [(str(data_source_id), txn_id, bank_id) for txn_id, bank_id in bridge_map.items()]
        execute_values(
            cur,
            "INSERT INTO bridge_mappings (data_source_id, transaction_id, bank_id) VALUES %s "
            "ON CONFLICT (data_source_id, transaction_id) DO NOTHING",
            values,
            page_size=1000,
        )
        conn.commit()
        return len(values)
    finally:
        conn.close()


def bulk_insert_transaction_ids(session_id: uuid.UUID, txn_ids: list[str]) -> int:
    if not txn_ids:
        return 0
    conn = get_sync_conn()
    try:
        cur = conn.cursor()
        values = [(str(session_id), tid) for tid in txn_ids]
        execute_values(
            cur,
            "INSERT INTO transaction_ids (session_id, transaction_id) VALUES %s",
            values,
            page_size=1000,
        )
        conn.commit()
        return len(values)
    finally:
        conn.close()


def bulk_insert_results(session_id: uuid.UUID, results: list[dict]) -> int:
    if not results:
        return 0
    conn = get_sync_conn()
    try:
        buf = io.StringIO()
        for r in results:
            line = "\t".join([
                str(session_id),
                r.get("transaction_id") or "\\N",
                r.get("bank_id") or "\\N",
                r.get("date") or "\\N",
                str(r.get("debit_amount", 0.0)),
                str(r.get("credit_amount", 0.0)),
                r.get("status") or "UNKNOWN",
                (r.get("customer_name") or "").replace("\t", " "),
                (r.get("branch") or "").replace("\t", " "),
                (r.get("reference_no") or "").replace("\t", " "),
                (r.get("description") or "").replace("\t", " ").replace("\n", " "),
                r.get("error_type") or "\\N",
            ])
            buf.write(line + "\n")
        buf.seek(0)

        cur = conn.cursor()
        cur.copy_from(
            buf,
            "reconciliation_results",
            columns=(
                "session_id", "transaction_id", "bank_id", "date",
                "debit_amount", "credit_amount", "status", "customer_name",
                "branch", "reference_no", "description", "error_type",
            ),
        )
        conn.commit()
        return len(results)
    finally:
        conn.close()


def bulk_insert_anomalies(session_id: uuid.UUID, anomalies: list[dict]) -> int:
    if not anomalies:
        return 0
    conn = get_sync_conn()
    try:
        cur = conn.cursor()
        values = [
            (
                str(session_id),
                a["anomaly_type"],
                a.get("severity", "medium"),
                a["description"],
                a.get("transaction_id"),
                a.get("bank_id"),
                a.get("amount"),
            )
            for a in anomalies
        ]
        execute_values(
            cur,
            "INSERT INTO anomalies (session_id, anomaly_type, severity, description, "
            "transaction_id, bank_id, amount) VALUES %s",
            values,
            page_size=1000,
        )
        conn.commit()
        return len(values)
    finally:
        conn.close()
