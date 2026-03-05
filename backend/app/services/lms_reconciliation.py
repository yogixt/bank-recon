"""Stage 2: LMS cross-verification engine.

Matches Stage 1 reconciliation results against LMS entries by trans_id,
then verifies amount, bank_id/PAYMENTREFNO, and TXN_STATUS.
"""

import logging
import uuid
from typing import Any

import psycopg2
from psycopg2.extras import RealDictCursor, execute_values

from app.config import get_settings

logger = logging.getLogger(__name__)


def _get_conn():
    return psycopg2.connect(get_settings().SYNC_DATABASE_URL)


def _get_lms_source_id(session_id: uuid.UUID) -> uuid.UUID | None:
    """Get lms_source_id from scheduled_reconciliations linked to this session."""
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT lms_source_id FROM scheduled_reconciliations WHERE session_id = %s",
            (str(session_id),),
        )
        row = cur.fetchone()
        if row and row[0]:
            return uuid.UUID(str(row[0]))
        return None
    finally:
        conn.close()


def run_lms_verification(session_id: uuid.UUID, lms_source_id: uuid.UUID | None = None) -> dict[str, Any]:
    """Stage 2: Cross-verify Stage 1 results against LMS entries.

    1. Get session's lms_source_id from scheduled_reconciliations (or use provided)
    2. Load LMS Bank rows into {trans_id: lms_entry} dict
    3. Load LMS TDS/Gift trans_ids into a set
    4. For each reconciliation_result row:
       - If trans_id in lms_bank_map -> run 3 checks -> LMS_VERIFIED or mismatch
       - If trans_id in tds_set -> LMS_TDS_ONLY
       - Else -> LMS_NOT_FOUND
    5. Bulk insert lms_verification_results
    6. Return statistics
    """
    if lms_source_id is None:
        lms_source_id = _get_lms_source_id(session_id)
    if lms_source_id is None:
        raise ValueError("No LMS source found for this session")

    conn = _get_conn()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Load LMS Bank rows: {trans_id: entry}
        cur.execute(
            """SELECT trans_id, amount, payment_ref_no, txn_status, utr_no, bene_name
            FROM lms_entries
            WHERE data_source_id = %s AND LOWER(TRIM(withdraw_type)) = 'bank'""",
            (str(lms_source_id),),
        )
        lms_bank_map: dict[str, dict] = {}
        for row in cur.fetchall():
            tid = row["trans_id"].strip()
            lms_bank_map[tid] = dict(row)

        # Load TDS/Gift trans_ids
        cur.execute(
            """SELECT DISTINCT trans_id FROM lms_entries
            WHERE data_source_id = %s AND LOWER(TRIM(withdraw_type)) IN ('tds', 'gift')""",
            (str(lms_source_id),),
        )
        tds_gift_set = {row["trans_id"].strip() for row in cur.fetchall()}

        # Load Stage 1 results for this session (only matchable statuses)
        cur.execute(
            """SELECT id, transaction_id, bank_id, status, debit_amount, credit_amount
            FROM reconciliation_results
            WHERE session_id = %s AND status IN ('MATCHED_SUCCESS', 'MATCHED_FAILED', 'REVERSAL')""",
            (str(session_id),),
        )
        stage1_results = cur.fetchall()

        verification_rows: list[tuple] = []
        stats: dict[str, int] = {
            "LMS_VERIFIED": 0,
            "LMS_AMOUNT_MISMATCH": 0,
            "LMS_BANKID_MISMATCH": 0,
            "LMS_STATUS_MISMATCH": 0,
            "LMS_NOT_FOUND": 0,
            "LMS_TDS_ONLY": 0,
            "BANK_NOT_IN_LMS": 0,
        }

        for result in stage1_results:
            txn_id = result["transaction_id"]
            bank_id = (result["bank_id"] or "").upper()
            stage1_status = result["status"]
            debit = result["debit_amount"] or 0.0
            credit = result["credit_amount"] or 0.0
            bank_amount = debit if stage1_status == "MATCHED_SUCCESS" else credit

            if txn_id in lms_bank_map:
                lms = lms_bank_map[txn_id]
                lms_amount = lms.get("amount", 0.0) or 0.0
                lms_payment_ref = (lms.get("payment_ref_no") or "").upper()
                lms_txn_status = lms.get("txn_status") or ""
                lms_utr = lms.get("utr_no") or ""
                lms_bene = lms.get("bene_name") or ""

                mismatches = []

                # Check 1: Amount
                if abs(bank_amount - lms_amount) > 0.01:
                    mismatches.append(f"Amount: bank={bank_amount}, lms={lms_amount}")

                # Check 2: bank_id vs PAYMENTREFNO
                if bank_id and lms_payment_ref and bank_id != lms_payment_ref:
                    mismatches.append(f"BankID: bank={bank_id}, lms_ref={lms_payment_ref}")

                # Check 3: TXN_STATUS consistency
                if stage1_status == "MATCHED_SUCCESS" and lms_txn_status and lms_txn_status != "Processed":
                    mismatches.append(f"Status: bank=SUCCESS but LMS={lms_txn_status}")

                if not mismatches:
                    stage2_status = "LMS_VERIFIED"
                elif any("Amount" in m for m in mismatches):
                    stage2_status = "LMS_AMOUNT_MISMATCH"
                elif any("BankID" in m for m in mismatches):
                    stage2_status = "LMS_BANKID_MISMATCH"
                else:
                    stage2_status = "LMS_STATUS_MISMATCH"

                stats[stage2_status] += 1
                verification_rows.append((
                    str(session_id), txn_id, bank_id, txn_id,
                    stage1_status, stage2_status,
                    bank_amount, lms_amount,
                    lms_payment_ref, lms_txn_status, lms_utr, lms_bene,
                    "; ".join(mismatches) if mismatches else None,
                ))

            elif txn_id in tds_gift_set:
                stage2_status = "LMS_TDS_ONLY"
                stats[stage2_status] += 1
                verification_rows.append((
                    str(session_id), txn_id, bank_id, txn_id,
                    stage1_status, stage2_status,
                    bank_amount, None,
                    None, None, None, None,
                    "Only TDS/Gift entry exists in LMS",
                ))

            else:
                stage2_status = "LMS_NOT_FOUND"
                stats[stage2_status] += 1
                verification_rows.append((
                    str(session_id), txn_id, bank_id, None,
                    stage1_status, stage2_status,
                    bank_amount, None,
                    None, None, None, None,
                    None,
                ))

        # Bulk insert verification results
        if verification_rows:
            execute_values(
                cur,
                """INSERT INTO lms_verification_results
                (session_id, transaction_id, bank_id, lms_trans_id,
                 stage1_status, stage2_status,
                 bank_amount, lms_amount,
                 lms_payment_ref, lms_txn_status, lms_utr_no, lms_bene_name,
                 mismatch_details)
                VALUES %s""",
                verification_rows,
                page_size=1000,
            )
            conn.commit()

        stats["total"] = len(verification_rows)
        logger.info(f"LMS verification complete for session {session_id}: {stats}")
        return stats

    finally:
        conn.close()
