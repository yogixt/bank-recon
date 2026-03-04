import { useRef, useState } from 'react';

interface Props {
  label: string;
  accept: string;
  hint: string;
  uploading: boolean;
  done: boolean;
  error: string | null;
  onFile: (file: File) => void;
}

export default function FileUploadCard({ label, accept, hint, uploading, done, error, onFile }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) onFile(file);
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) onFile(file);
  };

  return (
    <div className="card">
      <h3>{label}</h3>
      <div
        className={`file-drop ${dragging ? 'dragging' : ''} ${done ? 'done' : ''}`}
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
      >
        <input ref={inputRef} type="file" accept={accept} onChange={handleChange} />
        {uploading && <p>Uploading...</p>}
        {done && <p style={{ color: 'var(--success)' }}>Uploaded</p>}
        {!uploading && !done && <p>{hint}</p>}
        {error && <p style={{ color: 'var(--danger)' }}>{error}</p>}
      </div>
    </div>
  );
}
