export interface DataSource {
  id: string;
  name: string;
  source_type: 'bank_statement' | 'bridge_file';
  filename: string;
  status: 'uploading' | 'parsing' | 'ready' | 'failed';
  row_count: number;
  error_message: string | null;
  created_at: string;
}

export interface DataSourceUploadResponse {
  data_source_id: string;
  name: string;
  source_type: string;
  filename: string;
  message: string;
}

export interface Session {
  id: string;
  created_at: string;
  status: string;
  bank_source_id: string | null;
  bridge_source_id: string | null;
  transaction_ids_file: string | null;
  total_searched: number;
  total_found: number;
  success_count: number;
  failed_count: number;
  reversal_count: number;
  not_in_bridge_count: number;
  not_in_statement_count: number;
  total_success_amount: number;
  total_failed_amount: number;
  total_reversal_amount: number;
  processing_time: number | null;
  error_message: string | null;
}

export interface UploadResponse {
  session_id: string;
  file_type: string;
  filename: string;
  message: string;
}

export interface TaskProgress {
  task_id: string;
  progress: number;
  message: string;
  status: string;
}

export interface TaskStatus {
  task_type: string;
  status: string;
  progress: number;
  message: string | null;
}

export interface ReconcileStatusResponse {
  session_id: string;
  session_status: string;
  tasks: TaskStatus[];
}

export interface ResultRow {
  id: number;
  transaction_id: string;
  bank_id: string | null;
  date: string | null;
  debit_amount: number;
  credit_amount: number;
  status: string;
  customer_name: string | null;
  branch: string | null;
  reference_no: string | null;
  description: string | null;
  error_type: string | null;
}

export interface PaginatedResults {
  items: ResultRow[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface Summary {
  session: Session;
  status_counts: Record<string, number>;
}

export interface Anomaly {
  id: number;
  anomaly_type: string;
  severity: string;
  description: string;
  transaction_id: string | null;
  bank_id: string | null;
  amount: number | null;
}
