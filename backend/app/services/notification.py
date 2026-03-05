"""HTML email notification builder + sender for reconciliation results.

Provides:
- standard summary notification (Stage 1 + Stage 2)
- optional detailed audit report section with transaction-level LMS checks
"""

from __future__ import annotations

import html
import logging
from collections import Counter
from typing import Any

import psycopg2
from psycopg2.extras import RealDictCursor

from app.config import get_settings
from app.services.agentmail_client import send_email

logger = logging.getLogger(__name__)


def _conn():
    return psycopg2.connect(get_settings().SYNC_DATABASE_URL)


def _fmt_inr(amount: float) -> str:
    """Format amount in INR style: 1,23,456.78."""
    if amount == 0:
        return "0.00"
    neg = amount < 0
    amount = abs(amount)
    integer_part = int(amount)
    decimal_part = f"{amount - integer_part:.2f}"[1:]  # .XX

    s = str(integer_part)
    if len(s) <= 3:
        formatted = s
    else:
        last3 = s[-3:]
        rest = s[:-3]
        groups = []
        while rest:
            groups.append(rest[-2:])
            rest = rest[:-2]
        groups.reverse()
        formatted = ",".join(groups) + "," + last3

    result = formatted + decimal_part
    return f"-{result}" if neg else result


def _safe(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def _dedupe_ids(values: list[str]) -> list[str]:
    seen = set()
    out: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            out.append(value)
    return out


def _build_stage1_html(stats: dict[str, Any]) -> str:
    """Build Stage 1 results HTML section."""
    return f"""
    <table style="border-collapse:collapse;width:100%;margin:12px 0;">
      <tr style="background:#f8f9fa;">
        <td style="padding:8px 12px;border:1px solid #dee2e6;font-weight:600;">Total Searched</td>
        <td style="padding:8px 12px;border:1px solid #dee2e6;">{stats.get('total_searched', 0):,}</td>
      </tr>
      <tr>
        <td style="padding:8px 12px;border:1px solid #dee2e6;font-weight:600;">Matched (Success)</td>
        <td style="padding:8px 12px;border:1px solid #dee2e6;color:#28a745;">{stats.get('success_count', 0):,} (INR {_fmt_inr(stats.get('total_success_amount', 0))})</td>
      </tr>
      <tr style="background:#f8f9fa;">
        <td style="padding:8px 12px;border:1px solid #dee2e6;font-weight:600;">Matched (Failed)</td>
        <td style="padding:8px 12px;border:1px solid #dee2e6;color:#dc3545;">{stats.get('failed_count', 0):,} (INR {_fmt_inr(stats.get('total_failed_amount', 0))})</td>
      </tr>
      <tr>
        <td style="padding:8px 12px;border:1px solid #dee2e6;font-weight:600;">Reversals</td>
        <td style="padding:8px 12px;border:1px solid #dee2e6;color:#6f42c1;">{stats.get('reversal_count', 0):,} (INR {_fmt_inr(stats.get('total_reversal_amount', 0))})</td>
      </tr>
      <tr style="background:#f8f9fa;">
        <td style="padding:8px 12px;border:1px solid #dee2e6;font-weight:600;">Not in Bridge</td>
        <td style="padding:8px 12px;border:1px solid #dee2e6;">{stats.get('not_in_bridge', 0):,}</td>
      </tr>
      <tr>
        <td style="padding:8px 12px;border:1px solid #dee2e6;font-weight:600;">Not in Statement</td>
        <td style="padding:8px 12px;border:1px solid #dee2e6;">{stats.get('not_in_statement', 0):,}</td>
      </tr>
    </table>
    """


def _build_stage2_html(stats: dict[str, Any]) -> str:
    """Build Stage 2 LMS verification HTML section."""
    if not stats:
        return "<p style='color:#6c757d;'>LMS verification not yet available.</p>"

    return f"""
    <table style="border-collapse:collapse;width:100%;margin:12px 0;">
      <tr style="background:#f8f9fa;">
        <td style="padding:8px 12px;border:1px solid #dee2e6;font-weight:600;">Total Verified</td>
        <td style="padding:8px 12px;border:1px solid #dee2e6;">{stats.get('total', 0):,}</td>
      </tr>
      <tr>
        <td style="padding:8px 12px;border:1px solid #dee2e6;font-weight:600;">LMS Verified</td>
        <td style="padding:8px 12px;border:1px solid #dee2e6;color:#28a745;">{stats.get('LMS_VERIFIED', 0):,}</td>
      </tr>
      <tr style="background:#f8f9fa;">
        <td style="padding:8px 12px;border:1px solid #dee2e6;font-weight:600;">Amount Mismatch</td>
        <td style="padding:8px 12px;border:1px solid #dee2e6;color:#dc3545;">{stats.get('LMS_AMOUNT_MISMATCH', 0):,}</td>
      </tr>
      <tr>
        <td style="padding:8px 12px;border:1px solid #dee2e6;font-weight:600;">Bank ID Mismatch</td>
        <td style="padding:8px 12px;border:1px solid #dee2e6;color:#dc3545;">{stats.get('LMS_BANKID_MISMATCH', 0):,}</td>
      </tr>
      <tr style="background:#f8f9fa;">
        <td style="padding:8px 12px;border:1px solid #dee2e6;font-weight:600;">Status Mismatch</td>
        <td style="padding:8px 12px;border:1px solid #dee2e6;color:#dc3545;">{stats.get('LMS_STATUS_MISMATCH', 0):,}</td>
      </tr>
      <tr>
        <td style="padding:8px 12px;border:1px solid #dee2e6;font-weight:600;">Not Found in LMS</td>
        <td style="padding:8px 12px;border:1px solid #dee2e6;">{stats.get('LMS_NOT_FOUND', 0):,}</td>
      </tr>
      <tr style="background:#f8f9fa;">
        <td style="padding:8px 12px;border:1px solid #dee2e6;font-weight:600;">TDS Only</td>
        <td style="padding:8px 12px;border:1px solid #dee2e6;">{stats.get('LMS_TDS_ONLY', 0):,}</td>
      </tr>
      <tr>
        <td style="padding:8px 12px;border:1px solid #dee2e6;font-weight:600;">Bank Not in LMS</td>
        <td style="padding:8px 12px;border:1px solid #dee2e6;">{stats.get('BANK_NOT_IN_LMS', 0):,}</td>
      </tr>
    </table>
    """


def _build_audit_payload(session_id: str, preview_limit: int = 250) -> dict[str, Any]:
    """Build deterministic transaction-level audit payload for email."""
    conn = _conn()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute(
            """SELECT date, lms_source_id
            FROM scheduled_reconciliations
            WHERE session_id = %s
            ORDER BY date DESC
            LIMIT 1""",
            (session_id,),
        )
        schedule = cur.fetchone() or {}
        lms_source_id = schedule.get("lms_source_id")

        cur.execute(
            """SELECT id, transaction_id, bank_id, status, debit_amount, credit_amount
            FROM reconciliation_results
            WHERE session_id = %s
              AND status IN ('MATCHED_SUCCESS', 'MATCHED_FAILED', 'REVERSAL', 'NOT_IN_STATEMENT')
            ORDER BY id""",
            (session_id,),
        )
        stage1_rows = cur.fetchall()

        lms_bank_map: dict[str, dict[str, Any]] = {}
        tds_set: set[str] = set()
        if lms_source_id:
            cur.execute(
                """SELECT trans_id, amount, payment_ref_no, txn_status
                FROM lms_entries
                WHERE data_source_id = %s AND LOWER(TRIM(withdraw_type)) = 'bank'
                ORDER BY id""",
                (str(lms_source_id),),
            )
            for row in cur.fetchall():
                tid = (row.get("trans_id") or "").strip()
                if tid:
                    lms_bank_map[tid] = dict(row)

            cur.execute(
                """SELECT DISTINCT trans_id
                FROM lms_entries
                WHERE data_source_id = %s
                  AND LOWER(TRIM(withdraw_type)) IN ('tds', 'gift')""",
                (str(lms_source_id),),
            )
            tds_set = {
                (row.get("trans_id") or "").strip()
                for row in cur.fetchall()
                if (row.get("trans_id") or "").strip()
            }

        detail_rows: list[dict[str, Any]] = []
        stage2_counter: Counter[str] = Counter()
        not_in_lms_ids: list[str] = []
        not_in_bank_statement_ids: list[str] = []
        total_amount_mismatch = 0.0
        amount_mismatch_count = 0

        for result in stage1_rows:
            txn_id = (result.get("transaction_id") or "").strip()
            bank_id = (result.get("bank_id") or "").strip()
            stage1_status = result.get("status") or ""
            debit = float(result.get("debit_amount") or 0.0)
            credit = float(result.get("credit_amount") or 0.0)

            if stage1_status == "MATCHED_SUCCESS":
                bank_amount = debit
                bank_amount_type = "debit"
            elif stage1_status in ("MATCHED_FAILED", "REVERSAL"):
                bank_amount = credit
                bank_amount_type = "credit"
            else:
                bank_amount = 0.0
                bank_amount_type = "n/a"

            stage2_status = "LMS_NOT_CHECKED"
            lms_amount = None
            lms_query_status = None
            mismatch_details = None

            if stage1_status == "NOT_IN_STATEMENT":
                stage2_status = "NOT_IN_BANK_STATEMENT"
                not_in_bank_statement_ids.append(txn_id)
            elif txn_id and txn_id in lms_bank_map:
                lms = lms_bank_map[txn_id]
                lms_amount = float(lms.get("amount") or 0.0)
                lms_ref = (lms.get("payment_ref_no") or "").strip().upper()
                lms_query_status = (lms.get("txn_status") or "").strip() or None
                bank_id_upper = bank_id.upper()

                mismatches: list[str] = []
                if abs(bank_amount - lms_amount) > 0.01:
                    mismatch = abs(bank_amount - lms_amount)
                    total_amount_mismatch += mismatch
                    amount_mismatch_count += 1
                    mismatches.append(f"Amount mismatch: bank={bank_amount:.2f}, lms={lms_amount:.2f}")

                if bank_id_upper and lms_ref and bank_id_upper != lms_ref:
                    mismatches.append(f"Bank ID mismatch: bank_id={bank_id_upper}, lms_ref={lms_ref}")

                if stage1_status == "MATCHED_SUCCESS" and lms_query_status and lms_query_status != "Processed":
                    mismatches.append(f"Status mismatch: bank=SUCCESS, lms_status={lms_query_status}")

                if not mismatches:
                    stage2_status = "LMS_VERIFIED"
                elif any("Amount mismatch" in m for m in mismatches):
                    stage2_status = "LMS_AMOUNT_MISMATCH"
                elif any("Bank ID mismatch" in m for m in mismatches):
                    stage2_status = "LMS_BANKID_MISMATCH"
                else:
                    stage2_status = "LMS_STATUS_MISMATCH"

                mismatch_details = "; ".join(mismatches) if mismatches else None
            elif txn_id and txn_id in tds_set:
                stage2_status = "LMS_TDS_ONLY"
                mismatch_details = "Only TDS/Gift record exists in LMS"
            else:
                stage2_status = "LMS_NOT_FOUND"
                if txn_id:
                    not_in_lms_ids.append(txn_id)

            stage2_counter[stage2_status] += 1
            detail_rows.append(
                {
                    "transaction_id": txn_id,
                    "bank_id": bank_id or "-",
                    "bank_amount_type": bank_amount_type,
                    "bank_amount": bank_amount,
                    "lms_amount": lms_amount,
                    "lms_query_status": lms_query_status or "-",
                    "stage2_status": stage2_status,
                    "mismatch_details": mismatch_details or "-",
                }
            )

        return {
            "schedule_date": str(schedule.get("date") or ""),
            "rows_total": len(detail_rows),
            "rows_preview": detail_rows[:preview_limit],
            "preview_limit": preview_limit,
            "stage2_counts": dict(stage2_counter),
            "not_in_lms_ids": _dedupe_ids(not_in_lms_ids),
            "not_in_bank_statement_ids": _dedupe_ids(not_in_bank_statement_ids),
            "total_amount_mismatch": total_amount_mismatch,
            "amount_mismatch_count": amount_mismatch_count,
        }
    finally:
        conn.close()


def _format_id_list_html(ids: list[str], limit: int = 120) -> str:
    if not ids:
        return "<p style='color:#6c757d;'>None</p>"
    shown = ids[:limit]
    hidden = max(0, len(ids) - len(shown))
    chips = " ".join(
        f"<code style='display:inline-block;margin:2px 6px 2px 0;padding:2px 6px;background:#f8f9fa;border:1px solid #dee2e6;border-radius:4px;'>{_safe(i)}</code>"
        for i in shown
    )
    more = f"<p style='color:#6c757d;font-size:12px;'>...and {hidden:,} more</p>" if hidden else ""
    return chips + more


def _build_audit_html(audit: dict[str, Any], session_id: str) -> str:
    web_app = getattr(get_settings(), "WEB_APP_URL", "https://bank-recon-web.fly.dev").rstrip("/")
    results_url = f"{web_app}/results/{session_id}"

    rows_total = int(audit.get("rows_total", 0))
    preview = audit.get("rows_preview") or []
    preview_limit = int(audit.get("preview_limit", len(preview)))
    truncated = rows_total > len(preview)
    stage2_counts = audit.get("stage2_counts") or {}
    not_in_lms_ids = audit.get("not_in_lms_ids") or []
    not_in_bank_statement_ids = audit.get("not_in_bank_statement_ids") or []
    total_amount_mismatch = float(audit.get("total_amount_mismatch") or 0.0)
    amount_mismatch_count = int(audit.get("amount_mismatch_count") or 0)

    rows_html = "".join(
        f"""
        <tr>
          <td style="padding:6px 8px;border:1px solid #dee2e6;">{_safe(r['transaction_id'])}</td>
          <td style="padding:6px 8px;border:1px solid #dee2e6;">{_safe(r['bank_amount_type'])}</td>
          <td style="padding:6px 8px;border:1px solid #dee2e6;text-align:right;">{_fmt_inr(float(r['bank_amount'] or 0.0))}</td>
          <td style="padding:6px 8px;border:1px solid #dee2e6;text-align:right;">{_fmt_inr(float(r['lms_amount'])) if r['lms_amount'] is not None else '-'}</td>
          <td style="padding:6px 8px;border:1px solid #dee2e6;">{_safe(r['lms_query_status'])}</td>
          <td style="padding:6px 8px;border:1px solid #dee2e6;">{_safe(r['stage2_status'])}</td>
          <td style="padding:6px 8px;border:1px solid #dee2e6;">{_safe(r['mismatch_details'])}</td>
        </tr>
        """
        for r in preview
    )

    stage2_rows = "".join(
        f"""
        <tr>
          <td style="padding:6px 8px;border:1px solid #dee2e6;">{_safe(status)}</td>
          <td style="padding:6px 8px;border:1px solid #dee2e6;text-align:right;">{count:,}</td>
        </tr>
        """
        for status, count in sorted(stage2_counts.items(), key=lambda x: x[0])
    )

    preview_note = (
        f"<p style='color:#6c757d;font-size:12px;'>Showing first {preview_limit:,} rows out of {rows_total:,}. "
        f"Use dashboard for full drilldown: <a href='{_safe(results_url)}'>{_safe(results_url)}</a></p>"
        if truncated
        else ""
    )

    return f"""
    <h2 style="color:#333;margin-top:24px;">Detailed Audit Report</h2>
    <table style="border-collapse:collapse;width:100%;margin:12px 0;">
      <tr style="background:#f8f9fa;">
        <td style="padding:8px 12px;border:1px solid #dee2e6;font-weight:600;">Rows Audited</td>
        <td style="padding:8px 12px;border:1px solid #dee2e6;">{rows_total:,}</td>
      </tr>
      <tr>
        <td style="padding:8px 12px;border:1px solid #dee2e6;font-weight:600;">Amount Mismatch Count</td>
        <td style="padding:8px 12px;border:1px solid #dee2e6;color:#dc3545;">{amount_mismatch_count:,}</td>
      </tr>
      <tr style="background:#f8f9fa;">
        <td style="padding:8px 12px;border:1px solid #dee2e6;font-weight:600;">Total Amount Mismatch</td>
        <td style="padding:8px 12px;border:1px solid #dee2e6;color:#dc3545;">INR {_fmt_inr(total_amount_mismatch)}</td>
      </tr>
      <tr>
        <td style="padding:8px 12px;border:1px solid #dee2e6;font-weight:600;">Transaction IDs Not in LMS</td>
        <td style="padding:8px 12px;border:1px solid #dee2e6;">{len(not_in_lms_ids):,}</td>
      </tr>
      <tr style="background:#f8f9fa;">
        <td style="padding:8px 12px;border:1px solid #dee2e6;font-weight:600;">Transaction IDs Not in Bank Statement</td>
        <td style="padding:8px 12px;border:1px solid #dee2e6;">{len(not_in_bank_statement_ids):,}</td>
      </tr>
    </table>

    <h3 style="color:#333;">LMS Verification Status Breakdown</h3>
    <table style="border-collapse:collapse;width:100%;margin:12px 0;">
      <tr style="background:#f8f9fa;">
        <th style="padding:6px 8px;border:1px solid #dee2e6;text-align:left;">Status</th>
        <th style="padding:6px 8px;border:1px solid #dee2e6;text-align:right;">Count</th>
      </tr>
      {stage2_rows}
    </table>

    <h3 style="color:#333;">Transaction-Level Preview</h3>
    <table style="border-collapse:collapse;width:100%;margin:12px 0;font-size:12px;">
      <tr style="background:#f8f9fa;">
        <th style="padding:6px 8px;border:1px solid #dee2e6;text-align:left;">Transaction ID</th>
        <th style="padding:6px 8px;border:1px solid #dee2e6;text-align:left;">Bank Side</th>
        <th style="padding:6px 8px;border:1px solid #dee2e6;text-align:right;">Bank Amount</th>
        <th style="padding:6px 8px;border:1px solid #dee2e6;text-align:right;">LMS Amount</th>
        <th style="padding:6px 8px;border:1px solid #dee2e6;text-align:left;">LMS Query Status</th>
        <th style="padding:6px 8px;border:1px solid #dee2e6;text-align:left;">Verification Status</th>
        <th style="padding:6px 8px;border:1px solid #dee2e6;text-align:left;">Mismatch Detail</th>
      </tr>
      {rows_html}
    </table>
    {preview_note}

    <h3 style="color:#333;">Transaction IDs Not Available in LMS</h3>
    {_format_id_list_html(not_in_lms_ids)}

    <h3 style="color:#333;">Transaction IDs Not Available in Bank Statement</h3>
    {_format_id_list_html(not_in_bank_statement_ids)}

    <p style="font-size:12px;color:#6c757d;">
      Full details: <a href="{_safe(results_url)}">{_safe(results_url)}</a>
    </p>
    """


def send_reconciliation_notification(
    stage1_stats: dict[str, Any],
    stage2_stats: dict[str, Any] | None = None,
    session_id: str = "",
    recon_date: str = "",
    include_audit_report: bool = False,
):
    """Send summary notification + optional detailed audit report."""
    settings = get_settings()
    recipients = [r.strip() for r in settings.NOTIFICATION_RECIPIENTS.split(",") if r.strip()]
    if not recipients:
        logger.warning("No notification recipients configured")
        return {"sent": [], "failed": []}

    subject = f"Bank Reconciliation Report - {recon_date or 'Today'}"

    stage2_section = ""
    if stage2_stats:
        stage2_section = f"""
        <h2 style="color:#333;margin-top:24px;">Stage 2: LMS Verification</h2>
        {_build_stage2_html(stage2_stats)}
        """

    audit_section = ""
    if include_audit_report and session_id:
        try:
            audit = _build_audit_payload(session_id)
            audit_section = _build_audit_html(audit, session_id)
        except Exception as e:
            logger.exception("Failed to build detailed audit report section: %s", e)
            audit_section = (
                "<h2 style='color:#333;margin-top:24px;'>Detailed Audit Report</h2>"
                "<p style='color:#dc3545;'>Could not generate detailed report section. Check server logs.</p>"
            )

    html_body = f"""
    <html>
    <body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;max-width:900px;margin:0 auto;padding:20px;">
      <h1 style="color:#333;border-bottom:2px solid #4a8eff;padding-bottom:8px;">
        Bank Reconciliation Report
      </h1>
      <p style="color:#6c757d;">Date: {recon_date or 'N/A'} | Session: {session_id[:8] if session_id else 'N/A'}...</p>

      <h2 style="color:#333;">Stage 1: Bank Statement vs Bridge</h2>
      {_build_stage1_html(stage1_stats)}

      {stage2_section}
      {audit_section}

      <hr style="border:none;border-top:1px solid #dee2e6;margin:24px 0;">
      <p style="color:#6c757d;font-size:12px;">
        Automated report from {settings.NOTIFICATION_FROM_NAME}.
      </p>
    </body>
    </html>
    """

    sent: list[str] = []
    failed: list[dict[str, str]] = []
    for recipient in recipients:
        try:
            send_email(recipient, subject, html_body)
            sent.append(recipient)
        except Exception as e:
            logger.error("Failed to send notification to %s: %s", recipient, e)
            failed.append({"recipient": recipient, "error": str(e)})

    return {"sent": sent, "failed": failed}


def send_stale_alert(recon_date: str, missing: list[str]):
    """Send alert that today's reconciliation is overdue."""
    settings = get_settings()
    recipients = [r.strip() for r in settings.NOTIFICATION_RECIPIENTS.split(",") if r.strip()]
    if not recipients:
        return

    subject = f"ALERT: Reconciliation not complete for {recon_date}"
    missing_items = "".join(f"<li>{_safe(m)}</li>" for m in missing)
    html_body = f"""
    <html>
    <body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;max-width:600px;margin:0 auto;padding:20px;">
      <h1 style="color:#dc3545;">Reconciliation Alert</h1>
      <p>The daily reconciliation for <strong>{_safe(recon_date)}</strong> has not been completed.</p>
      <p>Missing sources:</p>
      <ul>{missing_items}</ul>
      <p>Please check the ingestion pipeline or upload files manually.</p>
      <hr style="border:none;border-top:1px solid #dee2e6;margin:24px 0;">
      <p style="color:#6c757d;font-size:12px;">Automated alert from {settings.NOTIFICATION_FROM_NAME}.</p>
    </body>
    </html>
    """

    for recipient in recipients:
        try:
            send_email(recipient, subject, html_body)
        except Exception as e:
            logger.error("Failed to send stale alert to %s: %s", recipient, e)
