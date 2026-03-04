import { useEffect, useState, useCallback } from 'react';
import { getTransactions } from '../../api/endpoints';
import type { TransactionFilters } from '../../api/endpoints';
import type { PaginatedResults, ResultRow } from '../../types';

interface Props {
  sessionId: string;
}

const STATUS_BADGE: Record<string, string> = {
  MATCHED_SUCCESS: 'badge-success',
  MATCHED_FAILED: 'badge-failed',
  NOT_IN_BRIDGE: 'badge-warning',
  NOT_IN_STATEMENT: 'badge-warning',
  FUZZY_MATCH: 'badge-info',
  DUPLICATE: 'badge-failed',
  REVERSAL: 'badge-warning',
};

const fmt = (n: number | null | undefined) =>
  n ? n.toLocaleString(undefined, { minimumFractionDigits: 2 }) : '-';

export default function TransactionTable({ sessionId }: Props) {
  const [data, setData] = useState<PaginatedResults | null>(null);
  const [page, setPage] = useState(1);
  const [expandedId, setExpandedId] = useState<number | null>(null);

  // Filters
  const [statusFilter, setStatusFilter] = useState('');
  const [search, setSearch] = useState('');
  const [branch, setBranch] = useState('');
  const [customerName, setCustomerName] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [minAmount, setMinAmount] = useState('');
  const [maxAmount, setMaxAmount] = useState('');

  const filters: TransactionFilters = {
    status: statusFilter || undefined,
    search: search || undefined,
    branch: branch || undefined,
    customer_name: customerName || undefined,
    date_from: dateFrom || undefined,
    date_to: dateTo || undefined,
    min_amount: minAmount || undefined,
    max_amount: maxAmount || undefined,
  };

  useEffect(() => {
    getTransactions(sessionId, page, 50, filters).then(setData);
  }, [sessionId, page, statusFilter, search, branch, customerName, dateFrom, dateTo, minAmount, maxAmount]);

  const resetPage = useCallback(() => setPage(1), []);

  const clearFilters = () => {
    setStatusFilter('');
    setSearch('');
    setBranch('');
    setCustomerName('');
    setDateFrom('');
    setDateTo('');
    setMinAmount('');
    setMaxAmount('');
    setPage(1);
  };

  const hasFilters = statusFilter || search || branch || customerName || dateFrom || dateTo || minAmount || maxAmount;

  if (!data) return <p>Loading...</p>;

  return (
    <>
      {/* Row 1: Status + Search + Count */}
      <div className="filters">
        <select value={statusFilter} onChange={(e) => { setStatusFilter(e.target.value); resetPage(); }}>
          <option value="">All Statuses</option>
          <option value="MATCHED_SUCCESS">Success</option>
          <option value="MATCHED_FAILED">Failed</option>
          <option value="NOT_IN_BRIDGE">Not in Bridge</option>
          <option value="NOT_IN_STATEMENT">Not in Statement</option>
          <option value="FUZZY_MATCH">Fuzzy Match</option>
          <option value="REVERSAL">Reversal</option>
        </select>
        <input
          placeholder="Search Transaction / Bank ID..."
          value={search}
          onChange={(e) => { setSearch(e.target.value); resetPage(); }}
        />
        <input
          placeholder="Branch..."
          value={branch}
          onChange={(e) => { setBranch(e.target.value); resetPage(); }}
        />
        <input
          placeholder="Customer name..."
          value={customerName}
          onChange={(e) => { setCustomerName(e.target.value); resetPage(); }}
        />
      </div>

      {/* Row 2: Date range + Amount range + Clear */}
      <div className="filters">
        <input
          type="date"
          title="Date from"
          value={dateFrom}
          onChange={(e) => { setDateFrom(e.target.value); resetPage(); }}
        />
        <input
          type="date"
          title="Date to"
          value={dateTo}
          onChange={(e) => { setDateTo(e.target.value); resetPage(); }}
        />
        <input
          type="number"
          placeholder="Min amount"
          value={minAmount}
          onChange={(e) => { setMinAmount(e.target.value); resetPage(); }}
          style={{ width: '120px' }}
        />
        <input
          type="number"
          placeholder="Max amount"
          value={maxAmount}
          onChange={(e) => { setMaxAmount(e.target.value); resetPage(); }}
          style={{ width: '120px' }}
        />
        {hasFilters && (
          <button className="btn" onClick={clearFilters} style={{ background: 'var(--border)', fontSize: '0.8rem' }}>
            Clear filters
          </button>
        )}
        <span style={{ color: 'var(--text-muted)', fontSize: '0.875rem', alignSelf: 'center', marginLeft: 'auto' }}>
          {data.total.toLocaleString()} results
        </span>
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Transaction ID</th>
              <th>Bank ID</th>
              <th>Date</th>
              <th>Debit</th>
              <th>Credit</th>
              <th>Status</th>
              <th>Customer</th>
              <th>Branch</th>
              <th>Reference No</th>
            </tr>
          </thead>
          <tbody>
            {data.items.map((r) => (
              <tr
                key={r.id}
                onClick={() => setExpandedId(expandedId === r.id ? null : r.id)}
                style={{ cursor: 'pointer' }}
              >
                <td style={{ fontFamily: 'monospace', fontSize: '0.8rem' }}>{r.transaction_id}</td>
                <td style={{ fontFamily: 'monospace', fontSize: '0.8rem' }}>{r.bank_id || 'N/A'}</td>
                <td>{r.date || '-'}</td>
                <td>{fmt(r.debit_amount)}</td>
                <td>{fmt(r.credit_amount)}</td>
                <td><span className={`badge ${STATUS_BADGE[r.status] || 'badge-info'}`}>{r.status}</span></td>
                <td>{r.customer_name || '-'}</td>
                <td>{r.branch || '-'}</td>
                <td style={{ fontSize: '0.8rem' }}>{r.reference_no || '-'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Expanded detail row */}
      {expandedId && (() => {
        const r = data.items.find((i) => i.id === expandedId);
        if (!r) return null;
        return (
          <div className="card" style={{ marginTop: '0.5rem', fontSize: '0.875rem' }}>
            <h3 style={{ marginBottom: '0.5rem' }}>Transaction Detail</h3>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '0.5rem 1.5rem' }}>
              <div><strong>Transaction ID:</strong> <code>{r.transaction_id}</code></div>
              <div><strong>Bank ID:</strong> <code>{r.bank_id || 'N/A'}</code></div>
              <div><strong>Date:</strong> {r.date || '-'}</div>
              <div><strong>Debit:</strong> {fmt(r.debit_amount)}</div>
              <div><strong>Credit:</strong> {fmt(r.credit_amount)}</div>
              <div><strong>Status:</strong> <span className={`badge ${STATUS_BADGE[r.status] || 'badge-info'}`}>{r.status}</span></div>
              <div><strong>Customer:</strong> {r.customer_name || '-'}</div>
              <div><strong>Branch:</strong> {r.branch || '-'}</div>
              <div><strong>Reference No:</strong> {r.reference_no || '-'}</div>
              <div style={{ gridColumn: '1 / -1' }}><strong>Description:</strong> {r.description || '-'}</div>
              {r.error_type && (
                <div style={{ gridColumn: '1 / -1', color: 'var(--danger)' }}><strong>Error:</strong> {r.error_type}</div>
              )}
            </div>
          </div>
        );
      })()}

      <div className="pagination">
        <button onClick={() => setPage(1)} disabled={page === 1}>First</button>
        <button onClick={() => setPage(page - 1)} disabled={page === 1}>Prev</button>
        <span>Page {data.page} of {data.total_pages}</span>
        <button onClick={() => setPage(page + 1)} disabled={page >= data.total_pages}>Next</button>
        <button onClick={() => setPage(data.total_pages)} disabled={page >= data.total_pages}>Last</button>
      </div>
    </>
  );
}
