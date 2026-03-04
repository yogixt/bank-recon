import { useState, useEffect, useRef } from 'react';
import {
  uploadStorageBankStatement,
  uploadStorageBridgeFile,
  listDataSources,
  deleteDataSource,
  getDataSource,
} from '../api/endpoints';
import type { DataSource } from '../types';

export default function StoragePage() {
  const [sources, setSources] = useState<DataSource[]>([]);
  const [loading, setLoading] = useState(true);

  // Upload state
  const [bankFile, setBankFile] = useState<File | null>(null);
  const [bankName, setBankName] = useState('');
  const [bankUploading, setBankUploading] = useState(false);

  const [bridgeFile, setBridgeFile] = useState<File | null>(null);
  const [bridgeName, setBridgeName] = useState('');
  const [bridgeUploading, setBridgeUploading] = useState(false);

  const pollRef = useRef<number | null>(null);

  const fetchSources = async () => {
    const data = await listDataSources();
    setSources(data);
    setLoading(false);
  };

  useEffect(() => {
    fetchSources();
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  // Poll for parsing data sources to finish
  useEffect(() => {
    const hasParsing = sources.some((s) => s.status === 'parsing' || s.status === 'uploading');
    if (hasParsing && !pollRef.current) {
      pollRef.current = window.setInterval(fetchSources, 3000);
    } else if (!hasParsing && pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, [sources]);

  const handleUploadBank = async () => {
    if (!bankFile || !bankName.trim()) return;
    setBankUploading(true);
    try {
      await uploadStorageBankStatement(bankFile, bankName.trim());
      setBankFile(null);
      setBankName('');
      await fetchSources();
    } finally {
      setBankUploading(false);
    }
  };

  const handleUploadBridge = async () => {
    if (!bridgeFile || !bridgeName.trim()) return;
    setBridgeUploading(true);
    try {
      await uploadStorageBridgeFile(bridgeFile, bridgeName.trim());
      setBridgeFile(null);
      setBridgeName('');
      await fetchSources();
    } finally {
      setBridgeUploading(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Delete this data source and all its parsed data?')) return;
    await deleteDataSource(id);
    await fetchSources();
  };

  const statusBadge = (status: string) => {
    switch (status) {
      case 'ready':
        return <span className="badge badge-success">Ready</span>;
      case 'parsing':
        return <span className="badge badge-info">Parsing...</span>;
      case 'uploading':
        return <span className="badge badge-info">Uploading...</span>;
      case 'failed':
        return <span className="badge badge-failed">Failed</span>;
      default:
        return <span className="badge">{status}</span>;
    }
  };

  return (
    <>
      <h2>Data Source Storage</h2>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '2rem' }}>
        {/* Bank statement upload */}
        <div className="card">
          <h3>Upload Bank Statement</h3>
          <input
            type="text"
            placeholder="Label (e.g. Dec 2024 - Feb 2026 Statement)"
            value={bankName}
            onChange={(e) => setBankName(e.target.value)}
            style={{
              width: '100%',
              padding: '0.5rem 0.75rem',
              marginBottom: '0.75rem',
              border: '1px solid var(--border)',
              background: 'var(--bg)',
              color: 'var(--text)',
              borderRadius: '0.375rem',
              fontSize: '0.875rem',
            }}
          />
          <input
            type="file"
            accept=".xlsx,.xls"
            onChange={(e) => setBankFile(e.target.files?.[0] || null)}
            style={{ marginBottom: '0.75rem', fontSize: '0.875rem' }}
          />
          <button
            className="btn btn-primary"
            disabled={!bankFile || !bankName.trim() || bankUploading}
            onClick={handleUploadBank}
          >
            {bankUploading ? 'Uploading...' : 'Upload Bank Statement'}
          </button>
        </div>

        {/* Bridge file upload */}
        <div className="card">
          <h3>Upload Bridge File</h3>
          <input
            type="text"
            placeholder="Label (e.g. Q1 2026 Bridge Mappings)"
            value={bridgeName}
            onChange={(e) => setBridgeName(e.target.value)}
            style={{
              width: '100%',
              padding: '0.5rem 0.75rem',
              marginBottom: '0.75rem',
              border: '1px solid var(--border)',
              background: 'var(--bg)',
              color: 'var(--text)',
              borderRadius: '0.375rem',
              fontSize: '0.875rem',
            }}
          />
          <input
            type="file"
            accept=".txt,.csv"
            onChange={(e) => setBridgeFile(e.target.files?.[0] || null)}
            style={{ marginBottom: '0.75rem', fontSize: '0.875rem' }}
          />
          <button
            className="btn btn-primary"
            disabled={!bridgeFile || !bridgeName.trim() || bridgeUploading}
            onClick={handleUploadBridge}
          >
            {bridgeUploading ? 'Uploading...' : 'Upload Bridge File'}
          </button>
        </div>
      </div>

      <h3 style={{ marginBottom: '1rem' }}>Stored Data Sources</h3>

      {loading ? (
        <p style={{ color: 'var(--text-muted)' }}>Loading...</p>
      ) : sources.length === 0 ? (
        <p style={{ color: 'var(--text-muted)' }}>No data sources uploaded yet.</p>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Type</th>
                <th>File</th>
                <th>Status</th>
                <th>Rows</th>
                <th>Uploaded</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {sources.map((ds) => (
                <tr key={ds.id}>
                  <td>{ds.name}</td>
                  <td>{ds.source_type === 'bank_statement' ? 'Bank Statement' : 'Bridge File'}</td>
                  <td style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>{ds.filename}</td>
                  <td>
                    {statusBadge(ds.status)}
                    {ds.error_message && (
                      <span style={{ fontSize: '0.75rem', color: 'var(--danger)', marginLeft: '0.5rem' }}>
                        {ds.error_message}
                      </span>
                    )}
                  </td>
                  <td>{ds.row_count.toLocaleString()}</td>
                  <td style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                    {new Date(ds.created_at).toLocaleDateString()}
                  </td>
                  <td>
                    <button className="btn btn-danger" style={{ padding: '0.25rem 0.5rem', fontSize: '0.75rem' }} onClick={() => handleDelete(ds.id)}>
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
