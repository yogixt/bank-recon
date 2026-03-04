import { useState } from 'react';
import { uploadTransactionIds } from '../api/endpoints';

type FileType = 'transaction_ids';

interface UploadState {
  [key: string]: { filename: string; uploading: boolean; done: boolean; error: string | null };
}

export function useFileUpload() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [uploads, setUploads] = useState<UploadState>({});

  const upload = async (file: File, fileType: FileType) => {
    setUploads((prev) => ({
      ...prev,
      [fileType]: { filename: file.name, uploading: true, done: false, error: null },
    }));

    try {
      const res = await uploadTransactionIds(file, sessionId || undefined);
      if (!sessionId) setSessionId(res.session_id);

      setUploads((prev) => ({
        ...prev,
        [fileType]: { filename: file.name, uploading: false, done: true, error: null },
      }));
    } catch (err: any) {
      setUploads((prev) => ({
        ...prev,
        [fileType]: {
          filename: file.name,
          uploading: false,
          done: false,
          error: err?.response?.data?.detail || err.message,
        },
      }));
    }
  };

  const markTransactionIdsDone = (newSessionId: string) => {
    setSessionId(newSessionId);
    setUploads((prev) => ({
      ...prev,
      transaction_ids: { filename: 'pasted_ids', uploading: false, done: true, error: null },
    }));
  };

  const allUploaded = !!uploads.transaction_ids?.done;

  return { sessionId, setSessionId, uploads, upload, allUploaded, markTransactionIdsDone };
}
