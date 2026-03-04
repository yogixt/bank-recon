import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import FileUploadCard from '../components/upload/FileUploadCard';
import BulkPasteInput from '../components/upload/BulkPasteInput';
import ProcessingStatus from '../components/reconciliation/ProcessingStatus';
import { useFileUpload } from '../hooks/useFileUpload';
import { useWebSocket } from '../hooks/useWebSocket';
import { listDataSources, startReconciliation, getReconcileStatus } from '../api/endpoints';
import type { DataSource, TaskStatus } from '../types';

export default function HomePage() {
  const navigate = useNavigate();
  const { sessionId, uploads, upload, allUploaded, markTransactionIdsDone } = useFileUpload();
  const [processing, setProcessing] = useState(false);
  const [tasks, setTasks] = useState<TaskStatus[]>([]);
  const progress = useWebSocket(processing ? sessionId : null);
  const pollRef = useRef<number | null>(null);

  // Data source selection
  const [dataSources, setDataSources] = useState<DataSource[]>([]);
  const [bankSourceId, setBankSourceId] = useState('');
  const [bridgeSourceId, setBridgeSourceId] = useState('');

  useEffect(() => {
    listDataSources().then(setDataSources);
  }, []);

  const bankSources = dataSources.filter((ds) => ds.source_type === 'bank_statement' && ds.status === 'ready');
  const bridgeSources = dataSources.filter((ds) => ds.source_type === 'bridge_file' && ds.status === 'ready');

  const canReconcile = bankSourceId && bridgeSourceId && allUploaded && sessionId;

  const handleReconcile = async () => {
    if (!sessionId || !bankSourceId || !bridgeSourceId) return;
    setProcessing(true);
    await startReconciliation(sessionId, bankSourceId, bridgeSourceId);

    // Poll for status
    pollRef.current = window.setInterval(async () => {
      const status = await getReconcileStatus(sessionId);
      setTasks(status.tasks);

      if (status.session_status === 'completed' || status.session_status === 'failed') {
        if (pollRef.current) clearInterval(pollRef.current);
        if (status.session_status === 'completed') {
          navigate(`/results/${sessionId}`);
        }
      }
    }, 2000);
  };

  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  const selectStyle: React.CSSProperties = {
    width: '100%',
    padding: '0.625rem 0.75rem',
    border: '1px solid var(--border)',
    background: 'var(--surface)',
    color: 'var(--text)',
    borderRadius: '0.375rem',
    fontSize: '0.875rem',
  };

  return (
    <>
      <h2>Reconciliation</h2>

      {!processing ? (
        <>
          {/* Data source selection */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1.5rem' }}>
            <div className="card">
              <h3>Bank Statement</h3>
              {bankSources.length === 0 ? (
                <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>
                  No bank statements available. <a href="/storage">Upload one first.</a>
                </p>
              ) : (
                <select
                  value={bankSourceId}
                  onChange={(e) => setBankSourceId(e.target.value)}
                  style={selectStyle}
                >
                  <option value="">Select bank statement...</option>
                  {bankSources.map((ds) => (
                    <option key={ds.id} value={ds.id}>
                      {ds.name} ({ds.row_count.toLocaleString()} rows)
                    </option>
                  ))}
                </select>
              )}
            </div>

            <div className="card">
              <h3>Bridge File</h3>
              {bridgeSources.length === 0 ? (
                <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>
                  No bridge files available. <a href="/storage">Upload one first.</a>
                </p>
              ) : (
                <select
                  value={bridgeSourceId}
                  onChange={(e) => setBridgeSourceId(e.target.value)}
                  style={selectStyle}
                >
                  <option value="">Select bridge file...</option>
                  {bridgeSources.map((ds) => (
                    <option key={ds.id} value={ds.id}>
                      {ds.name} ({ds.row_count.toLocaleString()} rows)
                    </option>
                  ))}
                </select>
              )}
            </div>
          </div>

          {/* Transaction IDs upload */}
          <div className="upload-grid" style={{ gridTemplateColumns: '1fr' }}>
            <FileUploadCard
              label="Transaction IDs"
              accept=".txt,.csv"
              hint="Drop transaction IDs file"
              uploading={uploads.transaction_ids?.uploading || false}
              done={uploads.transaction_ids?.done || false}
              error={uploads.transaction_ids?.error || null}
              onFile={(f) => upload(f, 'transaction_ids')}
            />
          </div>

          <BulkPasteInput sessionId={sessionId} onPasted={markTransactionIdsDone} />

          <div style={{ marginTop: '1.5rem', textAlign: 'center' }}>
            <button className="btn btn-primary" disabled={!canReconcile} onClick={handleReconcile}>
              Start Reconciliation
            </button>
          </div>
        </>
      ) : (
        <ProcessingStatus tasks={tasks} />
      )}
    </>
  );
}
