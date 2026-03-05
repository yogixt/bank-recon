import { useEffect, useState } from 'react';
import { getSchedules, getTodaySchedule, triggerSchedule } from '../api/endpoints';
import type { Schedule } from '../types';

export default function SchedulesPage() {
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [todaySchedule, setTodaySchedule] = useState<(Schedule & { exists: boolean }) | null>(null);
  const [triggering, setTriggering] = useState<string | null>(null);

  const loadData = async () => {
    const [schedulesRes, todayRes] = await Promise.all([
      getSchedules(),
      getTodaySchedule(),
    ]);
    setSchedules(schedulesRes.items);
    setTodaySchedule(todayRes);
  };

  useEffect(() => {
    loadData();
  }, []);

  const canTrigger = (s: Schedule) =>
    s.status === 'waiting_sources' &&
    !!s.bank_source_id &&
    !!s.bridge_source_id &&
    !!s.lms_source_id;

  const handleTrigger = async (scheduleId: string) => {
    setTriggering(scheduleId);
    try {
      await triggerSchedule(scheduleId);
      setTimeout(loadData, 2000);
    } finally {
      setTriggering(null);
    }
  };

  const statusBadge = (status: string) => {
    const cls =
      status === 'completed' ? 'badge-success' :
      status === 'failed' ? 'badge-failed' :
      status === 'running' ? 'badge-info' :
      'badge-warning';
    return <span className={`badge ${cls}`}>{status}</span>;
  };

  const formatRange = (from: string | null, to: string | null) => {
    if (!from && !to) return 'date n/a';
    if (from && to && from === to) return from;
    if (from && to) return `${from} to ${to}`;
    return from || to || 'date n/a';
  };

  const sourceCheck = (
    id: string | null,
    timestamp: string | null,
    dataFrom: string | null,
    dataTo: string | null,
  ) => {
    if (!id) return <span style={{ color: 'var(--text-muted)' }}>-</span>;
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.1rem' }}>
        <span style={{ color: 'var(--success)', fontSize: '0.75rem' }}>
          {timestamp ? new Date(timestamp).toLocaleTimeString() : 'Ready'}
        </span>
        <span style={{ color: 'var(--text-muted)', fontSize: '0.6875rem', whiteSpace: 'nowrap' }}>
          {formatRange(dataFrom, dataTo)}
        </span>
      </div>
    );
  };

  return (
    <>
      <h2>Scheduled Reconciliations</h2>

      {/* Today's status card */}
      {todaySchedule && (
        <div className="card" style={{ marginBottom: '1.5rem', borderLeft: '3px solid var(--primary)' }}>
          <h3>Today's Status</h3>
          {!todaySchedule.exists ? (
            <p style={{ color: 'var(--text-muted)' }}>No schedule created yet. Files have not been received today.</p>
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '1rem' }}>
              <div>
                <div style={{ fontSize: '0.6875rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>Status</div>
                <div style={{ marginTop: '0.25rem' }}>{statusBadge(todaySchedule.status)}</div>
              </div>
              <div>
                <div style={{ fontSize: '0.6875rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>Bank Statement</div>
                <div style={{ marginTop: '0.25rem' }}>
                  {sourceCheck(
                    todaySchedule.bank_source_id,
                    todaySchedule.bank_ingested_at,
                    todaySchedule.bank_data_date_from,
                    todaySchedule.bank_data_date_to,
                  )}
                </div>
              </div>
              <div>
                <div style={{ fontSize: '0.6875rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>Bridge File</div>
                <div style={{ marginTop: '0.25rem' }}>
                  {sourceCheck(
                    todaySchedule.bridge_source_id,
                    todaySchedule.bridge_ingested_at,
                    todaySchedule.bridge_data_date_from,
                    todaySchedule.bridge_data_date_to,
                  )}
                </div>
              </div>
              <div>
                <div style={{ fontSize: '0.6875rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>LMS File</div>
                <div style={{ marginTop: '0.25rem' }}>
                  {sourceCheck(
                    todaySchedule.lms_source_id,
                    todaySchedule.lms_ingested_at,
                    todaySchedule.lms_data_date_from,
                    todaySchedule.lms_data_date_to,
                  )}
                </div>
              </div>
              {todaySchedule.exists && canTrigger(todaySchedule) && (
                <div style={{ display: 'flex', alignItems: 'end' }}>
                  <button
                    className="btn btn-primary"
                    onClick={() => handleTrigger(todaySchedule.id)}
                    disabled={triggering === todaySchedule.id}
                  >
                    {triggering === todaySchedule.id ? 'Triggering...' : 'Trigger Now'}
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Schedule history table */}
      <div className="card">
        <h3>Schedule History</h3>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Date</th>
                <th>Status</th>
                <th>Bank</th>
                <th>Bridge</th>
                <th>LMS</th>
                <th>Triggered</th>
                <th>Completed</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {schedules.map(s => (
                <tr key={s.id}>
                  <td style={{ fontWeight: 600, whiteSpace: 'nowrap' }}>{s.date}</td>
                  <td>{statusBadge(s.status)}</td>
                  <td>{sourceCheck(s.bank_source_id, s.bank_ingested_at, s.bank_data_date_from, s.bank_data_date_to)}</td>
                  <td>{sourceCheck(s.bridge_source_id, s.bridge_ingested_at, s.bridge_data_date_from, s.bridge_data_date_to)}</td>
                  <td>{sourceCheck(s.lms_source_id, s.lms_ingested_at, s.lms_data_date_from, s.lms_data_date_to)}</td>
                  <td style={{ fontSize: '0.75rem', whiteSpace: 'nowrap' }}>
                    {s.triggered_at ? new Date(s.triggered_at).toLocaleTimeString() : '-'}
                  </td>
                  <td style={{ fontSize: '0.75rem', whiteSpace: 'nowrap' }}>
                    {s.completed_at ? new Date(s.completed_at).toLocaleTimeString() : '-'}
                  </td>
                  <td>
                    {canTrigger(s) && (
                      <button
                        className="btn btn-outline"
                        style={{ fontSize: '0.6875rem', padding: '0.25rem 0.5rem' }}
                        onClick={() => handleTrigger(s.id)}
                        disabled={triggering === s.id}
                      >
                        {triggering === s.id ? 'Triggering...' : 'Trigger'}
                      </button>
                    )}
                    {s.session_id && (
                      <a
                        href={`/results/${s.session_id}`}
                        className="btn btn-outline"
                        style={{ fontSize: '0.6875rem', padding: '0.25rem 0.5rem', marginLeft: '0.25rem' }}
                      >
                        Results
                      </a>
                    )}
                  </td>
                </tr>
              ))}
              {schedules.length === 0 && (
                <tr><td colSpan={8} style={{ textAlign: 'center', color: 'var(--text-muted)' }}>No schedules yet</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}
