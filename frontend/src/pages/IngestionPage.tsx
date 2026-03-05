import { useEffect, useState } from 'react';
import {
  getIngestionLogs,
  getIngestionStats,
} from '../api/endpoints';
import type { IngestionLog, IngestionStats } from '../types';

export default function IngestionPage() {
  const [logs, setLogs] = useState<IngestionLog[]>([]);
  const [stats, setStats] = useState<IngestionStats | null>(null);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [filterType, setFilterType] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const pageSize = 20;

  const loadData = async () => {
    const [logsRes, statsRes] = await Promise.all([
      getIngestionLogs(page, pageSize, filterType || undefined, filterStatus || undefined),
      getIngestionStats(),
    ]);
    setLogs(logsRes.items);
    setTotal(logsRes.total);
    setStats(statsRes);
  };

  useEffect(() => {
    loadData();
  }, [page, filterType, filterStatus]);

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  const statusBadge = (status: string) => {
    const cls =
      status === 'success' ? 'badge-success' :
      status === 'failed' ? 'badge-failed' :
      status === 'skipped' ? 'badge-warning' :
      'badge-info';
    return <span className={`badge ${cls}`}>{status}</span>;
  };

  const typeBadge = (type: string) => {
    const cls =
      type === 'bank_statement' ? 'badge-success' :
      type === 'bridge_file' ? 'badge-info' :
      'badge-warning';
    return <span className={`badge ${cls}`}>{type.replace('_', ' ')}</span>;
  };

  return (
    <>
      <h2>Email Ingestion</h2>

      {/* Stats cards */}
      <div className="stats-grid">
        <div className="card stat-card">
          <div className="value">{stats?.total ?? 0}</div>
          <div className="label">Total Processed</div>
        </div>
        {stats?.by_type && Object.entries(stats.by_type).map(([type, statuses]) => (
          <div key={type} className="card stat-card">
            <div className="value">{Object.values(statuses).reduce((a, b) => a + b, 0)}</div>
            <div className="label">{type.replace('_', ' ')}</div>
          </div>
        ))}
      </div>

      {/* Auto polling status */}
      <div className="card" style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap' }}>
        <span style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>
          Auto mode enabled: inbox is polled every minute and files are ingested automatically.
        </span>
      </div>

      {/* Filters */}
      <div className="filters" style={{ marginTop: '1rem' }}>
        <select value={filterType} onChange={e => { setFilterType(e.target.value); setPage(1); }}>
          <option value="">All Types</option>
          <option value="bank_statement">Bank Statement</option>
          <option value="bridge_file">Bridge File</option>
          <option value="lms_file">LMS File</option>
        </select>
        <select value={filterStatus} onChange={e => { setFilterStatus(e.target.value); setPage(1); }}>
          <option value="">All Statuses</option>
          <option value="success">Success</option>
          <option value="failed">Failed</option>
          <option value="processing">Processing</option>
          <option value="skipped">Skipped</option>
        </select>
      </div>

      {/* Log table */}
      <div className="card">
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Type</th>
                <th>Sender</th>
                <th>Subject</th>
                <th>Attachment</th>
                <th>Status</th>
                <th>Processed</th>
                <th>Error</th>
              </tr>
            </thead>
            <tbody>
              {logs.map(log => (
                <tr key={log.id}>
                  <td>{typeBadge(log.email_type)}</td>
                  <td style={{ maxWidth: '180px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {log.sender}
                  </td>
                  <td style={{ maxWidth: '250px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {log.subject}
                  </td>
                  <td style={{ fontSize: '0.75rem' }}>{log.attachment_filename || '-'}</td>
                  <td>{statusBadge(log.status)}</td>
                  <td style={{ fontSize: '0.75rem', whiteSpace: 'nowrap' }}>
                    {log.processed_at ? new Date(log.processed_at).toLocaleString() : '-'}
                  </td>
                  <td style={{ maxWidth: '200px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontSize: '0.75rem', color: 'var(--danger)' }}>
                    {log.error_message || ''}
                  </td>
                </tr>
              ))}
              {logs.length === 0 && (
                <tr><td colSpan={7} style={{ textAlign: 'center', color: 'var(--text-muted)' }}>No ingestion logs yet. Email polling will create logs automatically.</td></tr>
              )}
            </tbody>
          </table>
        </div>

        {totalPages > 1 && (
          <div className="pagination">
            <button disabled={page <= 1} onClick={() => setPage(p => p - 1)}>Prev</button>
            <span>{page} / {totalPages}</span>
            <button disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}>Next</button>
          </div>
        )}
      </div>
    </>
  );
}
