# Bank Reconciliation System v5.0 — System Overview

**Prepared by:** Engineering Team, Unomok (KM Unotag Pvt Ltd)
**Date:** 5th March 2026
**Status:** Live & Running

---

## 1. What Problem Does This Solve?

Every day, Unomok processes thousands of cash withdrawals for loyalty program users (electricians, retailers) via HDFC IMPS bank transfers. We need to verify:

- Did the bank actually send the money?
- Does the amount match what our system says?
- Are there any missing, duplicate, or suspicious transactions?

**Before this system:** Someone manually compared Excel files side by side. With ~2,000 bank transactions and ~44,000 LMS records daily, this took hours and was error-prone.

**Now:** The system does it automatically in seconds — zero human effort on a normal day.

---

## 2. The Three Files We Reconcile

Think of it like a three-way handshake. Each file comes from a different source, and they must all agree.

### File 1: HDFC Bank Statement

| Detail | Value |
|--------|-------|
| **What it is** | Official record from HDFC bank of every debit/credit on our account |
| **Format** | Excel file (.xls) |
| **Sent by** | HDFC Bank (automated email) |
| **Volume** | ~2,000 rows per day |
| **Key field** | A hash code buried inside the description column (we call it `bank_id`) |

**Example row:**
```
Date: 01/01/2026
Description: IMPS - 600109428484 - GURJEET SINGH - F93B93EC65E20975 - UTIB0003505
Debit: 575.00
```
The hash `F93B93EC65E20975` is the `bank_id` — it uniquely identifies this transfer.

### File 2: Bridge File

| Detail | Value |
|--------|-------|
| **What it is** | A mapping file that links our internal transaction ID to the bank's hash code |
| **Format** | Plain text file (.txt) |
| **Sent by** | Internal team |
| **Purpose** | This is the "bridge" between our system and the bank |

**Example content:**
```
R20260101032908ABCDEF1234567890    ← our transaction ID
F93B93EC65E20975                   ← bank's hash (bank_id)
R20260101045612XYZDEF9876543210    ← next transaction ID
A1B2C3D4E5F60789                   ← its bank_id
```

### File 3: LMS File (Loyalty Management System)

| Detail | Value |
|--------|-------|
| **What it is** | Export from our loyalty platform — every withdrawal, TDS deduction, and gift reward |
| **Format** | Excel file (.xlsx) |
| **Sent by** | Employee or auto-export |
| **Volume** | ~44,000 rows (spans multiple days) |
| **Key field** | `TransID` (same as bridge file's transaction ID) and embedded JSON with payment details |

**Four types of rows:**

| Type | Count | What It Is |
|------|-------|------------|
| **Bank** | 35,925 | Actual money transfer. Contains JSON with payment hash, UTR, amount |
| **TDS** | 7,116 | Tax deducted at source. References a Bank row. Not a transfer. |
| **Gift** | 827 | Gift reward. No bank transfer involved. |
| **bank** | 1 | Typo. Treated same as Bank. |

A Bank row's description contains embedded JSON like:
```json
{
  "PAYMENTREFNO": "F93B93EC65E20975",   ← same hash as bank_id
  "TXN_STATUS": "Processed",
  "OD_AMOUNT": "575",                    ← must match bank debit
  "UTR_NO": "600109428484",
  "BENE_NAME": "GURJEET SINGH"
}
```

---

## 3. How the Matching Works

### Stage 1: Bank Statement vs Bridge File

**Question answered:** "For every transaction in our system, did the bank actually process it?"

```
Our Transaction ID ──→ Bridge File ──→ Bank Hash ──→ Bank Statement
     (R202601...)        lookup        (F93B93...)      lookup

     "Does the bank have a record for this transaction?"
```

**Step by step:**

1. Load the bridge file into memory: `{transaction_id → bank_id}`
2. For each transaction ID, look up the bank_id
3. Search the bank statement for that bank_id
4. Check what happened:

| Result | Meaning | Example |
|--------|---------|---------|
| **MATCHED_SUCCESS** | Bank debited the amount (money sent to user) | Debit = 575.00 |
| **MATCHED_FAILED** | Bank credited back (transfer failed/returned) | Credit = 575.00 |
| **REVERSAL** | Both debit AND credit exist (sent then returned) | Debit = 575, Credit = 575 |
| **NOT_IN_BRIDGE** | Transaction ID not found in bridge file | Bridge file missing this txn |
| **NOT_IN_STATEMENT** | Bridge has the mapping but bank has no record | Bank didn't process it |

### Stage 2: Stage 1 Results vs LMS File

**Question answered:** "Does our LMS system agree with what the bank did?"

This is a cross-verification. For every transaction that Stage 1 found in the bank, we check the LMS file to make sure all three sources agree.

```
Stage 1 Result (transaction_id) ──→ LMS File (TransID)

     "Does the LMS record match the bank record?"
```

**Three checks for each matched transaction:**

| Check | What We Compare | Why |
|-------|----------------|-----|
| **Amount** | Bank debit amount vs LMS amount | Catch if wrong amount was sent |
| **Payment Hash** | bank_id vs LMS PAYMENTREFNO | Catch if linked to wrong transfer |
| **Status** | Bank says SUCCESS → LMS must say "Processed" | Catch status inconsistencies |

**Stage 2 outcomes:**

| Result | Meaning |
|--------|---------|
| **LMS_VERIFIED** | All 3 checks pass. Everything matches perfectly. |
| **LMS_AMOUNT_MISMATCH** | Transaction found but amounts differ. Needs investigation. |
| **LMS_BANKID_MISMATCH** | Transaction found but payment hash differs. Wrong linkage. |
| **LMS_STATUS_MISMATCH** | Bank says success but LMS doesn't say "Processed" (or vice versa). |
| **LMS_NOT_FOUND** | Transaction not in LMS at all. Missing from our system. |
| **LMS_TDS_ONLY** | Only a TDS/Gift record exists. No actual bank transfer row. |

---

## 4. Automation — How It Runs Without Human Intervention

### Email Polling (Every 15 Minutes)

The system monitors an email inbox (`bijay@agentmail.to`) using the AgentMail API.

```
Every 15 minutes:
  ┌──→ Check inbox for new emails
  │      ├── Sender contains "hdfcbank" + subject has "Account Statement"?
  │      │     → Download attachment → Parse as Bank Statement
  │      ├── Subject contains "Bridge File"?
  │      │     → Download attachment → Parse as Bridge File
  │      └── Has .xlsx attachment?
  │            → Download attachment → Parse as LMS File
  │
  │    Each email is logged and never processed twice (dedup by message ID)
  └──────────────────────────────────────────────────────────────────────
```

### Auto-Trigger

```
Bank Statement arrives → parsed ✓
Bridge File arrives    → parsed ✓
                              ↓
              Both ready? → YES → Auto-run Stage 1
                                        ↓
                              LMS also ready? → YES → Run Stage 2
                                              → NO  → Stage 2 runs later
                                                       when LMS arrives
```

**Key point:** LMS file often arrives later (it spans multiple days and is sometimes sent manually). The system handles this gracefully — if Stage 1 is already done and LMS arrives later, it automatically runs Stage 2 on its own.

### Daily Stale Check (4:30 AM IST)

If by the next morning the reconciliation hasn't completed, an alert email is sent listing what's missing:
- "Bank statement not received"
- "Bridge file not received"
- "Reconciliation not triggered"

---

## 5. Notification Emails

After reconciliation completes, an HTML email report is sent to `bijay@unomok.com` with:

**Stage 1 Summary:**
```
Total Searched:     1,847
Matched (Success):  1,702  (INR 8,45,750.00)
Matched (Failed):      89  (INR 44,500.00)
Reversals:             12  (INR 6,000.00)
Not in Bridge:         31
Not in Statement:      13
```

**Stage 2 Summary (if LMS available):**
```
Total Verified:     1,803
LMS Verified:       1,785
Amount Mismatch:        3
Bank ID Mismatch:       0
Status Mismatch:        2
Not Found in LMS:      11
TDS Only:               2
```

---

## 6. Dashboard (Web Interface)

Accessible at `http://localhost:5173` with five pages:

### Reconcile Page
Manual workflow for ad-hoc reconciliation. Select bank statement, bridge file, upload transaction IDs, click "Start."

### Storage Page
Upload and manage permanent data sources (bank statements and bridge files). Shows parsing status and row counts.

### Ingestion Page
- Stats cards: total emails processed by type
- Manual poll buttons: trigger immediate check for bank/bridge/LMS emails
- Log table: every email processed with status (success/failed/skipped), filterable by type and status

### Schedules Page
- Today's status card: shows which files have arrived (bank/bridge/LMS) with timestamps
- Manual trigger button: force reconciliation if auto-trigger didn't fire
- Schedule history table: past days with completion status

### Results Page (per session)
- Summary stats: searched, matched, failed, reversals, processing time
- Anomalies: flagged suspicious items (duplicates, amount outliers)
- **Transactions tab:** Stage 1 results with filters (status, search, date range, amount range), CSV export
- **LMS Verification tab:** Stage 2 results with status breakdown and filters

---

## 7. Anomaly Detection

Beyond simple matching, the system flags suspicious patterns:

| Anomaly | What It Catches |
|---------|----------------|
| **Duplicate Bank IDs** | Same bank hash linked to multiple transactions (potential fraud) |
| **Amount Outliers** | Transactions with amounts >3 standard deviations from mean |
| **Orphan Bridge Entries** | Bridge file references a bank_id not in the statement |
| **Duplicate Transaction IDs** | Same transaction appears more than once |
| **Mismatched Status** | Entry has both debit AND credit (unusual pattern) |

---

## 8. Technical Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Frontend  │     │   FastAPI    │     │  PostgreSQL  │
│  React+Vite │────→│   Backend    │────→│   Database   │
│  port 5173  │     │  port 8000   │     │  port 5432   │
└─────────────┘     └──────┬───────┘     └─────────────┘
                           │
                    ┌──────┴───────┐
                    │    Redis     │
                    │  port 6379   │
                    └──────┬───────┘
                           │
                ┌──────────┴──────────┐
                │                     │
          ┌─────┴─────┐        ┌─────┴─────┐
          │  Celery    │        │  Celery    │
          │  Worker    │        │  Beat      │
          │ (tasks)    │        │ (scheduler)│
          └───────────┘        └───────────┘
```

| Component | Role |
|-----------|------|
| **PostgreSQL** | Stores everything — bank entries, bridge mappings, LMS entries, results, logs |
| **Redis** | Message queue for Celery tasks + real-time progress updates |
| **FastAPI** | REST API serving the frontend + WebSocket for live progress |
| **Celery Worker** | Executes heavy tasks: parsing files, running reconciliation |
| **Celery Beat** | Scheduler: triggers email polls every 15 min, stale check at 4:30 AM |
| **React Frontend** | Dashboard for monitoring, manual operations, viewing results |

### External Service

| Service | Purpose |
|---------|---------|
| **AgentMail** | Email inbox API. Polls `bijay@agentmail.to` for incoming files. Sends notification emails. API key auth — no OAuth complexity. |

---

## 9. Performance

| Metric | Value |
|--------|-------|
| Bank statement parsing (2K rows) | ~2 seconds |
| Bridge file parsing | <1 second |
| LMS file parsing (44K rows) | ~8-10 seconds |
| Stage 1 reconciliation | ~1-3 seconds |
| Stage 2 LMS verification | ~1-2 seconds |
| **Total end-to-end** | **~15-20 seconds** |

**How it's fast:**
- PostgreSQL `COPY` protocol for bulk inserts (5-10x faster than individual INSERTs)
- Batch SQL lookups (1,000 IDs per query using `ANY()` operator)
- Streaming file parsing (10,000 rows at a time, never loads full file in memory)

---

## 10. Data Flow Summary

```
Day starts
    │
    ▼
Emails arrive at bijay@agentmail.to
    │
    ├── 9:00 AM: HDFC bank statement arrives
    │     → Parsed → 2,000 bank entries stored
    │     → Schedule updated: bank ✓
    │
    ├── 9:15 AM: Bridge file arrives
    │     → Parsed → 1,847 mappings stored
    │     → Schedule updated: bridge ✓
    │     → Both ready! Auto-trigger fires
    │           │
    │           ▼
    │     Stage 1 runs (2 seconds)
    │       → 1,702 success, 89 failed, 12 reversals
    │       → Results stored
    │       → Anomalies detected
    │       → Email notification sent
    │
    ├── 11:30 AM: LMS file arrives (late, as usual)
    │     → Parsed → 44,000 entries stored
    │     → Stage 1 already done, so Stage 2 runs independently
    │           │
    │           ▼
    │     Stage 2 runs (1 second)
    │       → 1,785 verified, 3 mismatches found
    │       → Email notification sent
    │
    └── Done. Dashboard shows full results.
         Bijay reviews any mismatches.
```

---

## 11. What Happens When Things Go Wrong

| Scenario | System Behavior |
|----------|----------------|
| Email doesn't arrive | Stale check at 4:30 AM sends alert |
| File parsing fails | Task marked as failed, error logged, DataSource status = "failed" |
| Reconciliation fails | Session marked as failed, error stored, can retry manually |
| Duplicate email received | Skipped automatically (dedup by message ID) |
| LMS has malformed JSON | Logged and skipped — other rows still processed |
| AgentMail API key invalid | Poll task logs warning and skips (non-blocking) |
| Network issue during poll | Task retried by Celery automatically |

---

## 12. Security

- AgentMail uses API key authentication (stored in `.env`, never in code)
- Database credentials in environment variables
- All services run in Docker containers on private network
- Only API (port 8000) and frontend (port 5173) are exposed
- No secrets committed to git

---

## 13. Current Status

| Item | Status |
|------|--------|
| Backend API | Running |
| Celery Worker | Running |
| Celery Beat (scheduler) | Running |
| Frontend Dashboard | Running |
| AgentMail Integration | Live and tested |
| Email Polling | Active (every 15 min) |
| Auto-Reconciliation | Enabled |
| Stale Alerts | Enabled (4:30 AM IST) |

**Access:**
- Dashboard: http://localhost:5173
- API: http://localhost:8000/api/health
- AgentMail Inbox: bijay@agentmail.to
