import { useEffect, useState } from 'react';
import { getSummary, getAnomalies, getDownloadUrl, getLmsSummary, getLmsVerification } from '../../api/endpoints';
import type { Summary, Anomaly, LmsVerificationResult } from '../../types';
import TransactionTable from './TransactionTable';

interface Props {
  sessionId: string;
}

type Tab = 'transactions' | 'lms';
type LmsSummary = {
  total: number;
  status_counts: Record<string, number>;
  stage1_matchable_total: number;
};

export default function ResultsView({ sessionId }: Props) {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [anomalies, setAnomalies] = useState<Anomaly[]>([]);
  const [tab, setTab] = useState<Tab>('transactions');
  const [lmsSummary, setLmsSummary] = useState<LmsSummary | null>(null);
  const [lmsResults, setLmsResults] = useState<LmsVerificationResult[]>([]);
  const [lmsPage, setLmsPage] = useState(1);
  const [lmsTotal, setLmsTotal] = useState(0);
  const [lmsFilter, setLmsFilter] = useState('');
  const lmsPageSize = 50;

  useEffect(() => {
    getSummary(sessionId).then(setSummary);
    getAnomalies(sessionId).then(setAnomalies);
    getLmsSummary(sessionId).then(setLmsSummary).catch(() => setLmsSummary(null));
  }, [sessionId]);

  useEffect(() => {
    if (tab !== 'lms') return;
    getLmsSummary(sessionId).then(setLmsSummary).catch(() => setLmsSummary(null));
  }, [sessionId, tab]);

  useEffect(() => {
    if (tab === 'lms') {
      getLmsVerification(sessionId, lmsPage, lmsPageSize, lmsFilter || undefined)
        .then(res => {
          setLmsResults(res.items);
          setLmsTotal(res.total);
        })
        .catch(() => {});
    }
  }, [sessionId, tab, lmsPage, lmsFilter]);

  if (!summary) return <p>Loading results...</p>;

  const s = summary.session;
  const lmsTotalPages = Math.max(1, Math.ceil(lmsTotal / lmsPageSize));

  const lmsStatusBadge = (status: string | null) => {
    if (!status) return '-';
    const cls =
      status === 'LMS_VERIFIED' ? 'badge-success' :
      status.includes('MISMATCH') ? 'badge-failed' :
      'badge-warning';
    return <span className={`badge ${cls}`}>{status}</span>;
  };

  return (
    <>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
        <h2>Reconciliation Results</h2>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <a href={getDownloadUrl(sessionId)} className="btn btn-success" download>Download CSV</a>
          <a href={`/chat/${sessionId}`} className="btn btn-primary">Chat with AI</a>
        </div>
      </div>

      <div className="stats-grid">
        <div className="card stat-card">
          <div className="value">{s.total_searched.toLocaleString()}</div>
          <div className="label">Total Searched</div>
        </div>
        <div className="card stat-card">
          <div className="value" style={{ color: 'var(--success)' }}>{s.success_count.toLocaleString()}</div>
          <div className="label">Success</div>
        </div>
        <div className="card stat-card">
          <div className="value" style={{ color: 'var(--danger)' }}>{s.failed_count.toLocaleString()}</div>
          <div className="label">Failed</div>
        </div>
        <div className="card stat-card">
          <div className="value" style={{ color: 'var(--warning)' }}>{s.reversal_count.toLocaleString()}</div>
          <div className="label">Reversals</div>
        </div>
        <div className="card stat-card">
          <div className="value" style={{ color: 'var(--warning)' }}>{s.not_in_bridge_count.toLocaleString()}</div>
          <div className="label">Not in Bridge</div>
        </div>
        <div className="card stat-card">
          <div className="value" style={{ color: 'var(--warning)' }}>{s.not_in_statement_count.toLocaleString()}</div>
          <div className="label">Not in Statement</div>
        </div>
        <div className="card stat-card">
          <div className="value">{s.processing_time ? `${s.processing_time.toFixed(1)}s` : '-'}</div>
          <div className="label">Processing Time</div>
        </div>
      </div>

      {anomalies.length > 0 && (
        <div className="card" style={{ marginBottom: '1.5rem' }}>
          <h3>Anomalies Detected ({anomalies.length})</h3>
          {anomalies.map((a) => (
            <div key={a.id} className="anomaly-item">
              <span className={`badge badge-${a.severity === 'high' ? 'failed' : a.severity === 'medium' ? 'warning' : 'info'}`}>
                {a.severity}
              </span>
              <div>
                <div style={{ fontSize: '0.875rem' }}>{a.description}</div>
                {a.transaction_id && (
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                    TXN: {a.transaction_id} {a.bank_id ? `| Bank: ${a.bank_id}` : ''}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Tab bar */}
      <div style={{ display: 'flex', gap: '0', marginBottom: '1rem', borderBottom: '1px solid var(--border)' }}>
        <button
          className={`btn ${tab === 'transactions' ? 'btn-primary' : 'btn-outline'}`}
          style={{ borderRadius: '0.5rem 0.5rem 0 0', borderBottom: 'none' }}
          onClick={() => setTab('transactions')}
        >
          Transactions
        </button>
        <button
          className={`btn ${tab === 'lms' ? 'btn-primary' : 'btn-outline'}`}
          style={{ borderRadius: '0.5rem 0.5rem 0 0', borderBottom: 'none' }}
          onClick={() => setTab('lms')}
        >
          LMS Verification {lmsSummary && lmsSummary.total > 0 ? `(${lmsSummary.total.toLocaleString()})` : ''}
        </button>
      </div>

      {tab === 'transactions' && (
        <div className="card">
          <h3>Transactions</h3>
          <TransactionTable sessionId={sessionId} />
        </div>
      )}

      {tab === 'lms' && (
        <div className="card">
          <h3>LMS Verification Results</h3>

          {lmsSummary && lmsSummary.total > 0 ? (
            <>
              {/* LMS stats */}
              <div className="stats-grid" style={{ marginBottom: '1rem' }}>
                {Object.entries(lmsSummary.status_counts).map(([status, count]) => (
                  <div key={status} className="card stat-card" style={{ padding: '0.75rem' }}>
                    <div className="value" style={{ fontSize: '1.25rem' }}>{count.toLocaleString()}</div>
                    <div className="label">{status.replace(/_/g, ' ')}</div>
                  </div>
                ))}
              </div>

              {/* Filter */}
              <div className="filters">
                <select value={lmsFilter} onChange={e => { setLmsFilter(e.target.value); setLmsPage(1); }}>
                  <option value="">All Statuses</option>
                  <option value="LMS_VERIFIED">LMS Verified</option>
                  <option value="LMS_AMOUNT_MISMATCH">Amount Mismatch</option>
                  <option value="LMS_BANKID_MISMATCH">Bank ID Mismatch</option>
                  <option value="LMS_STATUS_MISMATCH">Status Mismatch</option>
                  <option value="LMS_NOT_FOUND">Not Found</option>
                  <option value="LMS_TDS_ONLY">TDS Only</option>
                  <option value="BANK_NOT_IN_LMS">Bank Not in LMS</option>
                </select>
              </div>

              {/* LMS table */}
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Transaction ID</th>
                      <th>Bank ID</th>
                      <th>Stage 1</th>
                      <th>Stage 2</th>
                      <th>Bank Amount</th>
                      <th>LMS Amount</th>
                      <th>LMS Ref</th>
                      <th>Bene Name</th>
                      <th>Mismatch</th>
                    </tr>
                  </thead>
                  <tbody>
                    {lmsResults.map(r => (
                      <tr key={r.id}>
                        <td style={{ fontSize: '0.75rem', fontFamily: 'monospace' }}>{r.transaction_id}</td>
                        <td style={{ fontSize: '0.75rem', fontFamily: 'monospace' }}>{r.bank_id || '-'}</td>
                        <td>{r.stage1_status ? <span className="badge badge-info">{r.stage1_status}</span> : '-'}</td>
                        <td>{lmsStatusBadge(r.stage2_status)}</td>
                        <td>{r.bank_amount != null ? r.bank_amount.toLocaleString() : '-'}</td>
                        <td>{r.lms_amount != null ? r.lms_amount.toLocaleString() : '-'}</td>
                        <td style={{ fontSize: '0.75rem', fontFamily: 'monospace' }}>{r.lms_payment_ref || '-'}</td>
                        <td style={{ fontSize: '0.75rem' }}>{r.lms_bene_name || '-'}</td>
                        <td style={{ fontSize: '0.6875rem', color: 'var(--danger)', maxWidth: '200px', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                          {r.mismatch_details || ''}
                        </td>
                      </tr>
                    ))}
                    {lmsResults.length === 0 && (
                      <tr><td colSpan={9} style={{ textAlign: 'center', color: 'var(--text-muted)' }}>No LMS verification results</td></tr>
                    )}
                  </tbody>
                </table>
              </div>

              {lmsTotalPages > 1 && (
                <div className="pagination">
                  <button disabled={lmsPage <= 1} onClick={() => setLmsPage(p => p - 1)}>Prev</button>
                  <span>{lmsPage} / {lmsTotalPages}</span>
                  <button disabled={lmsPage >= lmsTotalPages} onClick={() => setLmsPage(p => p + 1)}>Next</button>
                </div>
              )}
            </>
          ) : (
            <p style={{ color: 'var(--text-muted)', padding: '1rem 0' }}>
              {lmsSummary?.stage1_matchable_total === 0
                ? 'No Stage 1 matched transactions are available for LMS comparison in this session.'
                : 'No LMS verification data yet. LMS verification may still be running or no ready LMS source was available for this run.'}
            </p>
          )}
        </div>
      )}
    </>
  );
}
