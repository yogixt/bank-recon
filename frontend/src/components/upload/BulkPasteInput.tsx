import { useState } from 'react';
import { pasteTransactionIds } from '../../api/endpoints';

interface Props {
  sessionId: string | null;
  onPasted: (sessionId: string) => void;
}

export default function BulkPasteInput({ sessionId, onPasted }: Props) {
  const [text, setText] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async () => {
    if (!text.trim()) return;
    setSubmitting(true);
    try {
      const res = await pasteTransactionIds(text, sessionId || undefined);
      onPasted(res.session_id);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="card">
      <h3>Or paste Transaction IDs</h3>
      <textarea
        rows={5}
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Paste transaction IDs, one per line..."
        style={{
          width: '100%',
          padding: '0.75rem',
          background: 'var(--surface)',
          border: '1px solid var(--border)',
          borderRadius: '0.375rem',
          color: 'var(--text)',
          resize: 'vertical',
          fontFamily: 'monospace',
        }}
      />
      <button className="btn btn-primary" onClick={handleSubmit} disabled={submitting || !text.trim()} style={{ marginTop: '0.5rem' }}>
        {submitting ? 'Saving...' : 'Use Pasted IDs'}
      </button>
    </div>
  );
}
