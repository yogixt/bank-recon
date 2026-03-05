"""Gemini AI agent for chat interface over reconciliation data.

Skills:
- Session overview & statistics
- Lookup specific transactions by ID
- Filter by status, branch, customer, date, amount
- Analyze reversals & anomalies
- Top amounts & branch breakdown
- Generate recommendations
"""

import json
import logging
import re
import uuid

import google.generativeai as genai
import psycopg2
from psycopg2.extras import RealDictCursor

from app.config import get_settings

logger = logging.getLogger(__name__)


def _conn():
    return psycopg2.connect(get_settings().SYNC_DATABASE_URL)


def _query(sql: str, params: tuple = ()) -> list[dict]:
    conn = _conn()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(sql, params)
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def _query_one(sql: str, params: tuple = ()) -> dict | None:
    rows = _query(sql, params)
    return rows[0] if rows else None


# ── Skills ──────────────────────────────────────────────────────────────

def skill_session_overview(session_id: str) -> dict:
    """Full session summary with status counts."""
    session = _query_one(
        "SELECT total_searched, total_found, success_count, failed_count, "
        "reversal_count, not_in_bridge_count, not_in_statement_count, "
        "total_success_amount, total_failed_amount, total_reversal_amount, "
        "processing_time, status FROM reconciliation_sessions WHERE id = %s",
        (session_id,),
    )
    status_counts = _query(
        "SELECT status, COUNT(*) as count FROM reconciliation_results "
        "WHERE session_id = %s GROUP BY status ORDER BY count DESC",
        (session_id,),
    )
    return {"session": session, "status_breakdown": status_counts}


def skill_lookup_transaction(session_id: str, transaction_id: str) -> list[dict]:
    """Look up all entries for a specific transaction ID."""
    return _query(
        "SELECT transaction_id, bank_id, date, debit_amount, credit_amount, "
        "status, customer_name, branch, reference_no, description, error_type "
        "FROM reconciliation_results "
        "WHERE session_id = %s AND transaction_id ILIKE %s",
        (session_id, f"%{transaction_id}%"),
    )


def skill_filter_by_status(session_id: str, status: str) -> dict:
    """Get count and sample transactions for a given status."""
    count_row = _query_one(
        "SELECT COUNT(*) as count FROM reconciliation_results "
        "WHERE session_id = %s AND status = %s",
        (session_id, status),
    )
    samples = _query(
        "SELECT transaction_id, bank_id, date, debit_amount, credit_amount, "
        "customer_name, branch, reference_no, description "
        "FROM reconciliation_results "
        "WHERE session_id = %s AND status = %s LIMIT 25",
        (session_id, status),
    )
    return {"status": status, "total_count": count_row["count"] if count_row else 0, "samples": samples}


def skill_filter_by_branch(session_id: str, branch: str) -> dict:
    """Get transactions for a specific branch."""
    rows = _query(
        "SELECT transaction_id, bank_id, date, debit_amount, credit_amount, "
        "status, customer_name, reference_no "
        "FROM reconciliation_results "
        "WHERE session_id = %s AND branch ILIKE %s LIMIT 50",
        (session_id, f"%{branch}%"),
    )
    status_summary = _query(
        "SELECT status, COUNT(*) as count FROM reconciliation_results "
        "WHERE session_id = %s AND branch ILIKE %s GROUP BY status",
        (session_id, f"%{branch}%"),
    )
    return {"branch": branch, "transactions": rows, "status_summary": status_summary}


def skill_filter_by_customer(session_id: str, customer: str) -> dict:
    """Get transactions for a specific customer name."""
    rows = _query(
        "SELECT transaction_id, bank_id, date, debit_amount, credit_amount, "
        "status, branch, reference_no "
        "FROM reconciliation_results "
        "WHERE session_id = %s AND customer_name ILIKE %s LIMIT 50",
        (session_id, f"%{customer}%"),
    )
    return {"customer": customer, "count": len(rows), "transactions": rows}


def skill_amount_analysis(session_id: str) -> dict:
    """Analyze amounts: totals, averages, top debit/credit transactions."""
    totals = _query_one(
        "SELECT SUM(debit_amount) as total_debit, SUM(credit_amount) as total_credit, "
        "AVG(debit_amount) FILTER (WHERE debit_amount > 0) as avg_debit, "
        "AVG(credit_amount) FILTER (WHERE credit_amount > 0) as avg_credit, "
        "MAX(debit_amount) as max_debit, MAX(credit_amount) as max_credit "
        "FROM reconciliation_results WHERE session_id = %s",
        (session_id,),
    )
    top_debits = _query(
        "SELECT transaction_id, bank_id, debit_amount, customer_name, branch, status "
        "FROM reconciliation_results "
        "WHERE session_id = %s AND debit_amount > 0 "
        "ORDER BY debit_amount DESC LIMIT 10",
        (session_id,),
    )
    top_credits = _query(
        "SELECT transaction_id, bank_id, credit_amount, customer_name, branch, status "
        "FROM reconciliation_results "
        "WHERE session_id = %s AND credit_amount > 0 "
        "ORDER BY credit_amount DESC LIMIT 10",
        (session_id,),
    )
    return {"totals": totals, "top_debits": top_debits, "top_credits": top_credits}


def skill_branch_breakdown(session_id: str) -> list[dict]:
    """Breakdown of transactions by branch with counts and amounts."""
    return _query(
        "SELECT branch, COUNT(*) as count, "
        "SUM(debit_amount) as total_debit, SUM(credit_amount) as total_credit, "
        "COUNT(*) FILTER (WHERE status = 'MATCHED_SUCCESS') as success, "
        "COUNT(*) FILTER (WHERE status = 'MATCHED_FAILED') as failed, "
        "COUNT(*) FILTER (WHERE status = 'REVERSAL') as reversals "
        "FROM reconciliation_results "
        "WHERE session_id = %s AND branch IS NOT NULL "
        "GROUP BY branch ORDER BY count DESC LIMIT 30",
        (session_id,),
    )


def skill_reversal_analysis(session_id: str) -> dict:
    """Analyze all reversal transactions."""
    reversals = _query(
        "SELECT transaction_id, bank_id, date, debit_amount, credit_amount, "
        "customer_name, branch, reference_no "
        "FROM reconciliation_results "
        "WHERE session_id = %s AND status = 'REVERSAL' LIMIT 50",
        (session_id,),
    )
    total = _query_one(
        "SELECT COUNT(*) as count, SUM(debit_amount) as total_debit, "
        "SUM(credit_amount) as total_credit "
        "FROM reconciliation_results "
        "WHERE session_id = %s AND status = 'REVERSAL'",
        (session_id,),
    )
    return {"total": total, "reversals": reversals}


def skill_anomaly_details(session_id: str) -> list[dict]:
    """Get all anomalies with full details."""
    return _query(
        "SELECT anomaly_type, severity, description, transaction_id, bank_id, amount "
        "FROM anomalies WHERE session_id = %s ORDER BY severity DESC, id",
        (session_id,),
    )


def skill_date_analysis(session_id: str) -> dict:
    """Analyze transactions by date — counts and amounts per date."""
    by_date = _query(
        "SELECT date, COUNT(*) as count, "
        "SUM(debit_amount) as total_debit, SUM(credit_amount) as total_credit, "
        "COUNT(*) FILTER (WHERE status = 'MATCHED_SUCCESS') as success, "
        "COUNT(*) FILTER (WHERE status = 'MATCHED_FAILED') as failed "
        "FROM reconciliation_results "
        "WHERE session_id = %s AND date IS NOT NULL "
        "GROUP BY date ORDER BY date LIMIT 60",
        (session_id,),
    )
    return {"by_date": by_date}


def skill_error_summary(session_id: str) -> dict:
    """Summarize transactions with errors (NOT_IN_BRIDGE, NOT_IN_STATEMENT)."""
    not_in_bridge = _query(
        "SELECT transaction_id, error_type "
        "FROM reconciliation_results "
        "WHERE session_id = %s AND status = 'NOT_IN_BRIDGE' LIMIT 30",
        (session_id,),
    )
    not_in_statement = _query(
        "SELECT transaction_id, bank_id, error_type "
        "FROM reconciliation_results "
        "WHERE session_id = %s AND status = 'NOT_IN_STATEMENT' LIMIT 30",
        (session_id,),
    )
    return {"not_in_bridge": not_in_bridge, "not_in_statement": not_in_statement}


# ── Skill registry ─────────────────────────────────────────────────────

SKILLS = {
    "session_overview": {
        "fn": skill_session_overview,
        "args": ["session_id"],
        "desc": "Get full session summary, status counts, and totals",
    },
    "lookup_transaction": {
        "fn": skill_lookup_transaction,
        "args": ["session_id", "transaction_id"],
        "desc": "Look up a specific transaction by ID (supports partial match)",
    },
    "filter_by_status": {
        "fn": skill_filter_by_status,
        "args": ["session_id", "status"],
        "desc": "Get count and sample transactions for a status (MATCHED_SUCCESS, MATCHED_FAILED, REVERSAL, NOT_IN_BRIDGE, NOT_IN_STATEMENT)",
    },
    "filter_by_branch": {
        "fn": skill_filter_by_branch,
        "args": ["session_id", "branch"],
        "desc": "Get transactions and status breakdown for a branch",
    },
    "filter_by_customer": {
        "fn": skill_filter_by_customer,
        "args": ["session_id", "customer"],
        "desc": "Look up transactions by customer name",
    },
    "amount_analysis": {
        "fn": skill_amount_analysis,
        "args": ["session_id"],
        "desc": "Analyze amounts: totals, averages, top debits/credits",
    },
    "branch_breakdown": {
        "fn": skill_branch_breakdown,
        "args": ["session_id"],
        "desc": "Breakdown of transactions by branch with counts and amounts",
    },
    "reversal_analysis": {
        "fn": skill_reversal_analysis,
        "args": ["session_id"],
        "desc": "Analyze all reversal transactions in detail",
    },
    "anomaly_details": {
        "fn": skill_anomaly_details,
        "args": ["session_id"],
        "desc": "Get all detected anomalies with full details",
    },
    "date_analysis": {
        "fn": skill_date_analysis,
        "args": ["session_id"],
        "desc": "Analyze transactions grouped by date",
    },
    "error_summary": {
        "fn": skill_error_summary,
        "args": ["session_id"],
        "desc": "Summarize missing transactions (not in bridge / not in statement)",
    },
}


# ── Agent ───────────────────────────────────────────────────────────────

class GeminiAgent:
    def __init__(self):
        settings = get_settings()
        self.model_name = "gemini-2.0-flash"
        self.model = None

        if not settings.GEMINI_API_KEY:
            logger.warning("GEMINI_API_KEY not configured; using deterministic fallback for chat responses")
            return

        genai.configure(api_key=settings.GEMINI_API_KEY)
        self.model = genai.GenerativeModel(self.model_name)

    @staticmethod
    def _is_quota_or_rate_limit_error(exc: Exception) -> bool:
        msg = str(exc).lower()
        signals = [
            "429",
            "quota exceeded",
            "resource_exhausted",
            "rate limit",
            "too many requests",
            "retry in",
        ]
        return any(s in msg for s in signals)

    def _pick_skills_heuristic(self, user_message: str) -> list[dict]:
        """Fallback skill router when LLM routing is unavailable."""
        text = (user_message or "").lower()
        calls: list[dict] = []

        def add(skill: str, **kwargs):
            call = {"skill": skill, **kwargs}
            if call not in calls:
                calls.append(call)

        if "overview" in text or "summary" in text or "status" in text or "report" in text:
            add("session_overview")

        if "failed" in text:
            add("filter_by_status", status="MATCHED_FAILED")
        if "success" in text:
            add("filter_by_status", status="MATCHED_SUCCESS")
        if "reversal" in text:
            add("reversal_analysis")
        if "branch" in text:
            add("branch_breakdown")
        if "anomal" in text:
            add("anomaly_details")
        if "amount" in text or "debit" in text or "credit" in text:
            add("amount_analysis")
        if "date" in text or "day" in text:
            add("date_analysis")
        if "not in bridge" in text or "not in statement" in text or "missing" in text:
            add("error_summary")

        txn_match = re.search(r"\b[A-Z0-9]{6,}\b", user_message.upper())
        if txn_match and ("transaction" in text or "txn" in text or "id" in text):
            add("lookup_transaction", transaction_id=txn_match.group(0))

        if not calls:
            add("session_overview")

        return calls

    def _build_fallback_response(self, user_message: str, skill_data: dict, reason: str) -> str:
        """Generate a deterministic response from SQL skill outputs."""
        lines = [f"{reason}. Showing direct data summary instead."]

        overview = skill_data.get("session_overview", {}) if isinstance(skill_data, dict) else {}
        session = overview.get("session", {}) if isinstance(overview, dict) else {}
        if isinstance(session, dict) and session:
            lines.extend([
                "",
                "Session overview:",
                f"- Status: {session.get('status', 'unknown')}",
                f"- Total searched: {session.get('total_searched', 0)}",
                f"- Total found: {session.get('total_found', 0)}",
                f"- Success: {session.get('success_count', 0)}",
                f"- Failed: {session.get('failed_count', 0)}",
                f"- Reversals: {session.get('reversal_count', 0)}",
            ])

        status_data = skill_data.get("filter_by_status") if isinstance(skill_data, dict) else None
        if isinstance(status_data, dict):
            lines.extend([
                "",
                f"Requested status ({status_data.get('status', 'n/a')}): {status_data.get('total_count', 0)} records",
            ])
            samples = status_data.get("samples") or []
            if samples:
                sample_ids = [str(s.get("transaction_id")) for s in samples[:5] if s.get("transaction_id")]
                if sample_ids:
                    lines.append(f"- Sample transaction IDs: {', '.join(sample_ids)}")

        lookup_data = skill_data.get("lookup_transaction") if isinstance(skill_data, dict) else None
        if isinstance(lookup_data, list):
            lines.extend([
                "",
                f"Transaction lookup matches: {len(lookup_data)}",
            ])
            if lookup_data:
                preview = [str(r.get("transaction_id")) for r in lookup_data[:5] if r.get("transaction_id")]
                if preview:
                    lines.append(f"- Matches: {', '.join(preview)}")

        anomalies = skill_data.get("anomaly_details") if isinstance(skill_data, dict) else None
        if isinstance(anomalies, list) and anomalies:
            lines.extend([
                "",
                f"Anomalies detected: {len(anomalies)}",
            ])

        if len(lines) == 1:
            lines.extend([
                "",
                "I could not build a targeted summary from this query. Try asking for:",
                "- session overview",
                "- failed transactions",
                "- reversal analysis",
                "- branch breakdown",
            ])

        return "\n".join(lines)

    def _pick_skills(self, user_message: str) -> list[dict]:
        """Use the LLM to decide which skills to call based on the user message."""
        if not self.model:
            return self._pick_skills_heuristic(user_message)

        skill_list = "\n".join(
            f"- {name}: {info['desc']} (args: {', '.join(info['args'])})"
            for name, info in SKILLS.items()
        )

        prompt = f"""You are a skill router for a bank reconciliation AI assistant.
Given the user's question, pick which skills to call to gather the data needed to answer.

Available skills:
{skill_list}

User question: {user_message}

Reply with ONLY a JSON array of objects, each with "skill" and any extra args beyond session_id.
Examples:
- User asks "show me an overview" → [{{"skill": "session_overview"}}]
- User asks "find transaction ABC123" → [{{"skill": "lookup_transaction", "transaction_id": "ABC123"}}]
- User asks "show failed transactions" → [{{"skill": "filter_by_status", "status": "MATCHED_FAILED"}}]
- User asks "which branches have issues?" → [{{"skill": "branch_breakdown"}}, {{"skill": "error_summary"}}]
- User asks "analyze reversals and amounts" → [{{"skill": "reversal_analysis"}}, {{"skill": "amount_analysis"}}]

Always include session_overview if the question is general.
Return ONLY valid JSON, no markdown fences."""

        try:
            resp = self.model.generate_content(
                prompt,
                generation_config={"temperature": 0, "max_output_tokens": 512},
            )
            parsed = json.loads(resp.text.strip())
            if isinstance(parsed, list):
                return parsed
        except Exception:
            logger.warning("Gemini skill routing failed; using heuristic router")

        return self._pick_skills_heuristic(user_message)

    def _execute_skills(self, session_id: str, skill_calls: list[dict]) -> dict:
        """Execute the selected skills and collect results."""
        results = {}
        for call in skill_calls:
            name = call.get("skill", "")
            if name not in SKILLS:
                continue
            skill = SKILLS[name]
            kwargs = {"session_id": session_id}
            for arg in skill["args"]:
                if arg != "session_id" and arg in call:
                    kwargs[arg] = call[arg]
            try:
                results[name] = skill["fn"](**kwargs)
            except Exception as e:
                results[name] = {"error": str(e)}
        return results

    def chat(self, session_id: uuid.UUID, user_message: str) -> str:
        sid = str(session_id)

        # Step 1: Pick skills
        skill_calls = self._pick_skills(user_message)

        # Step 2: Execute skills to gather data
        skill_data = self._execute_skills(sid, skill_calls)

        # Step 3: Generate response with full context
        data_json = json.dumps(skill_data, indent=2, default=str)

        prompt = f"""You are an expert bank reconciliation analyst AI assistant.
You have access to real data from the reconciliation session.

DATA FROM SKILLS:
{data_json}

USER QUESTION: {user_message}

Instructions:
- Answer the question accurately using the data above
- Include specific numbers, transaction IDs, and amounts when relevant
- Format currency amounts nicely (e.g., ₹1,23,456.00)
- Use bullet points and clear structure for readability
- If you spot patterns or issues, highlight them
- If the data doesn't contain enough info to answer, say so clearly
- Keep the response professional but conversational
- Do not make up data — only use what's provided above"""

        if not self.model:
            return self._build_fallback_response(
                user_message=user_message,
                skill_data=skill_data,
                reason="Gemini model is unavailable",
            )

        try:
            response = self.model.generate_content(
                prompt,
                generation_config={"temperature": 0.3, "max_output_tokens": 4096},
            )
            return response.text.strip()
        except Exception as e:
            if self._is_quota_or_rate_limit_error(e):
                logger.warning("Gemini quota/rate limit hit; serving fallback response")
                return self._build_fallback_response(
                    user_message=user_message,
                    skill_data=skill_data,
                    reason="Gemini API quota/rate limit reached",
                )

            logger.exception("Gemini chat generation failed")
            return self._build_fallback_response(
                user_message=user_message,
                skill_data=skill_data,
                reason="Gemini response generation failed",
            )
