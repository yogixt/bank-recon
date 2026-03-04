import type { TaskProgress } from '../../types';

interface Props {
  progress: TaskProgress | null;
}

export default function UploadProgress({ progress }: Props) {
  if (!progress) return null;

  return (
    <div className="card">
      <h3>Processing</h3>
      <div className="progress-bar">
        <div className="progress-bar-fill" style={{ width: `${progress.progress}%` }} />
      </div>
      <p style={{ fontSize: '0.875rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
        {progress.message} ({progress.progress}%)
      </p>
    </div>
  );
}
