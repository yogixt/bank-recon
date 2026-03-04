import { useEffect, useState } from 'react';
import { getSummary, getAnomalies, getDownloadUrl } from '../../api/endpoints';
import type { Summary, Anomaly } from '../../types';
import TransactionTable from './TransactionTable';

interface Props {
  sessionId: string;
}

export default function ResultsView({ sessionId }: Props) {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [anomalies, setAnomalies] = useState<Anomaly[]>([]);

  useEffect(() => {
    getSummary(sessionId).then(setSummary);
    getAnomalies(sessionId).then(setAnomalies);
  }, [sessionId]);

  if (!summary) return <p>Loading results...</p>;

  const s = summary.session;

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

      <div className="card">
        <h3>Transactions</h3>
        <TransactionTable sessionId={sessionId} />
      </div>
    </>
  );
}
