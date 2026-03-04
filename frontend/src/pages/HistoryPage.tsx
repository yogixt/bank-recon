import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { getHistory } from '../api/endpoints';
import type { Session } from '../types';

export default function HistoryPage() {
  const [sessions, setSessions] = useState<Session[]>([]);
  const navigate = useNavigate();

  useEffect(() => {
    getHistory().then(setSessions);
  }, []);

  return (
    <>
      <h2>Reconciliation History</h2>
      {sessions.length === 0 ? (
        <p style={{ color: 'var(--text-muted)' }}>No reconciliation sessions yet.</p>
      ) : (
        <div className="card">
          {sessions.map((s) => (
            <div
              key={s.id}
              className="history-item"
              onClick={() => navigate(`/results/${s.id}`)}
            >
              <div>
                <div style={{ fontWeight: 500 }}>{(s as any).bank_statement_file || s.transaction_ids_file || 'Untitled'}</div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                  {new Date(s.created_at).toLocaleString()} &middot; {s.total_searched.toLocaleString()} searched
                </div>
              </div>
              <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
                <span className="badge badge-success">{s.success_count} success</span>
                <span className="badge badge-failed">{s.failed_count} failed</span>
                <span className={`badge badge-${s.status === 'completed' ? 'success' : s.status === 'failed' ? 'failed' : 'info'}`}>
                  {s.status}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </>
  );
}
