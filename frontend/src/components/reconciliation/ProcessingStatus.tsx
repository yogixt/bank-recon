import type { TaskStatus } from '../../types';

interface Props {
  tasks: TaskStatus[];
}

const TASK_LABELS: Record<string, string> = {
  parse_bank: 'Bank Statement',
  parse_bridge: 'Bridge File',
  parse_transactions: 'Transaction IDs',
  reconciliation: 'Reconciliation',
  ai_analysis: 'AI Analysis',
};

export default function ProcessingStatus({ tasks }: Props) {
  return (
    <div className="card">
      <h3>Processing Status</h3>
      {tasks.map((t) => (
        <div key={t.task_type} style={{ marginBottom: '0.75rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.875rem' }}>
            <span>{TASK_LABELS[t.task_type] || t.task_type}</span>
            <span className={`badge badge-${t.status === 'completed' ? 'success' : t.status === 'failed' ? 'failed' : 'info'}`}>
              {t.status}
            </span>
          </div>
          <div className="progress-bar">
            <div
              className="progress-bar-fill"
              style={{
                width: `${t.progress}%`,
                background: t.status === 'failed' ? 'var(--danger)' : t.status === 'completed' ? 'var(--success)' : undefined,
              }}
            />
          </div>
          {t.message && <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{t.message}</p>}
        </div>
      ))}
    </div>
  );
}
