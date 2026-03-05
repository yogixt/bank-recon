"""HTML email notification builder + sender for reconciliation results."""

import logging
from typing import Any

from app.config import get_settings
from app.services.agentmail_client import send_email

logger = logging.getLogger(__name__)


def _fmt_inr(amount: float) -> str:
    """Format amount in INR style: 1,23,456.78"""
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


def send_reconciliation_notification(
    stage1_stats: dict[str, Any],
    stage2_stats: dict[str, Any] | None = None,
    session_id: str = "",
    recon_date: str = "",
):
    """Send HTML notification email with reconciliation results."""
    settings = get_settings()
    recipients = [r.strip() for r in settings.NOTIFICATION_RECIPIENTS.split(",") if r.strip()]
    if not recipients:
        logger.warning("No notification recipients configured")
        return

    subject = f"Bank Reconciliation Report - {recon_date or 'Today'}"

    stage2_section = ""
    if stage2_stats:
        stage2_section = f"""
        <h2 style="color:#333;margin-top:24px;">Stage 2: LMS Verification</h2>
        {_build_stage2_html(stage2_stats)}
        """

    html = f"""
    <html>
    <body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;max-width:600px;margin:0 auto;padding:20px;">
      <h1 style="color:#333;border-bottom:2px solid #4a8eff;padding-bottom:8px;">
        Bank Reconciliation Report
      </h1>
      <p style="color:#6c757d;">Date: {recon_date or 'N/A'} | Session: {session_id[:8] if session_id else 'N/A'}...</p>

      <h2 style="color:#333;">Stage 1: Bank Statement vs Bridge</h2>
      {_build_stage1_html(stage1_stats)}

      {stage2_section}

      <hr style="border:none;border-top:1px solid #dee2e6;margin:24px 0;">
      <p style="color:#6c757d;font-size:12px;">
        Automated report from {settings.NOTIFICATION_FROM_NAME}.
        <br>View full details in the dashboard.
      </p>
    </body>
    </html>
    """

    for recipient in recipients:
        try:
            send_email(recipient, subject, html)
        except Exception as e:
            logger.error(f"Failed to send notification to {recipient}: {e}")


def send_stale_alert(recon_date: str, missing: list[str]):
    """Send alert that today's reconciliation is overdue."""
    settings = get_settings()
    recipients = [r.strip() for r in settings.NOTIFICATION_RECIPIENTS.split(",") if r.strip()]
    if not recipients:
        return

    subject = f"ALERT: Reconciliation not complete for {recon_date}"
    missing_items = "".join(f"<li>{m}</li>" for m in missing)
    html = f"""
    <html>
    <body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;max-width:600px;margin:0 auto;padding:20px;">
      <h1 style="color:#dc3545;">Reconciliation Alert</h1>
      <p>The daily reconciliation for <strong>{recon_date}</strong> has not been completed.</p>
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
            send_email(recipient, subject, html)
        except Exception as e:
            logger.error(f"Failed to send stale alert to {recipient}: {e}")
