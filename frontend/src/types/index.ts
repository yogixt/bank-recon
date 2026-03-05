export interface DataSource {
  id: string;
  name: string;
  source_type: 'bank_statement' | 'bridge_file' | 'lms_file';
  filename: string;
  status: 'uploading' | 'parsing' | 'ready' | 'failed';
  row_count: number;
  error_message: string | null;
  data_date_from: string | null;
  data_date_to: string | null;
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

export interface IngestionLog {
  id: number;
  gmail_message_id: string;
  email_type: string;
  sender: string | null;
  subject: string | null;
  received_at: string | null;
  processed_at: string | null;
  attachment_filename: string | null;
  data_source_id: string | null;
  status: string;
  error_message: string | null;
}

export interface PaginatedIngestionLogs {
  items: IngestionLog[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface IngestionStats {
  by_type: Record<string, Record<string, number>>;
  total: number;
}

export interface Schedule {
  id: string;
  date: string;
  bank_source_id: string | null;
  bridge_source_id: string | null;
  lms_source_id: string | null;
  bank_data_date_from: string | null;
  bank_data_date_to: string | null;
  bridge_data_date_from: string | null;
  bridge_data_date_to: string | null;
  lms_data_date_from: string | null;
  lms_data_date_to: string | null;
  session_id: string | null;
  status: string;
  bank_ingested_at: string | null;
  bridge_ingested_at: string | null;
  lms_ingested_at: string | null;
  triggered_at: string | null;
  completed_at: string | null;
  error_message: string | null;
  created_at: string;
}

export interface ScheduleList {
  items: Schedule[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface LmsVerificationResult {
  id: number;
  session_id: string;
  transaction_id: string | null;
  bank_id: string | null;
  lms_trans_id: string | null;
  stage1_status: string | null;
  stage2_status: string | null;
  bank_amount: number | null;
  lms_amount: number | null;
  lms_payment_ref: string | null;
  lms_txn_status: string | null;
  lms_utr_no: string | null;
  lms_bene_name: string | null;
  mismatch_details: string | null;
  verified_at: string | null;
}
