import client from './client';
import type {
  DataSource,
  DataSourceUploadResponse,
  UploadResponse,
  ReconcileStatusResponse,
  PaginatedResults,
  Summary,
  Anomaly,
  Session,
} from '../types';

// -- Storage (permanent data sources) --

export async function uploadStorageBankStatement(file: File, name: string): Promise<DataSourceUploadResponse> {
  const form = new FormData();
  form.append('file', file);
  form.append('name', name);
  const { data } = await client.post('/storage/bank-statement', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data;
}

export async function uploadStorageBridgeFile(file: File, name: string): Promise<DataSourceUploadResponse> {
  const form = new FormData();
  form.append('file', file);
  form.append('name', name);
  const { data } = await client.post('/storage/bridge-file', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data;
}

export async function listDataSources(): Promise<DataSource[]> {
  const { data } = await client.get('/storage');
  return data;
}

export async function getDataSource(id: string): Promise<DataSource> {
  const { data } = await client.get(`/storage/${id}`);
  return data;
}

export async function deleteDataSource(id: string): Promise<void> {
  await client.delete(`/storage/${id}`);
}

// -- Upload (transaction IDs only, per session) --

export async function uploadTransactionIds(file: File, sessionId?: string): Promise<UploadResponse> {
  const form = new FormData();
  form.append('file', file);
  if (sessionId) form.append('session_id', sessionId);
  const { data } = await client.post('/upload/transaction-ids', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data;
}

export async function pasteTransactionIds(text: string, sessionId?: string): Promise<UploadResponse> {
  const params = new URLSearchParams();
  params.append('text', text);
  if (sessionId) params.append('session_id', sessionId);
  const { data } = await client.post(`/upload/paste?${params.toString()}`);
  return data;
}

// -- Reconciliation --

export async function startReconciliation(
  sessionId: string,
  bankSourceId: string,
  bridgeSourceId: string,
) {
  const { data } = await client.post('/reconcile', {
    session_id: sessionId,
    bank_source_id: bankSourceId,
    bridge_source_id: bridgeSourceId,
  });
  return data;
}

export async function getReconcileStatus(sessionId: string): Promise<ReconcileStatusResponse> {
  const { data } = await client.get(`/reconcile/status/${sessionId}`);
  return data;
}

// -- Results --

export async function getSummary(sessionId: string): Promise<Summary> {
  const { data } = await client.get(`/results/${sessionId}/summary`);
  return data;
}

export interface TransactionFilters {
  status?: string;
  search?: string;
  branch?: string;
  customer_name?: string;
  date_from?: string;
  date_to?: string;
  min_amount?: string;
  max_amount?: string;
}

export async function getTransactions(
  sessionId: string,
  page: number,
  pageSize: number,
  filters: TransactionFilters = {},
): Promise<PaginatedResults> {
  const params: Record<string, string> = { page: String(page), page_size: String(pageSize) };
  for (const [k, v] of Object.entries(filters)) {
    if (v) params[k] = v;
  }
  const { data } = await client.get(`/results/${sessionId}/transactions`, { params });
  return data;
}

export async function getAnomalies(sessionId: string): Promise<Anomaly[]> {
  const { data } = await client.get(`/results/${sessionId}/anomalies`);
  return data;
}

export async function sendAuditReport(sessionId: string) {
  const { data } = await client.post(`/results/${sessionId}/send-audit-report`);
  return data;
}

// -- History --

export async function getHistory(): Promise<Session[]> {
  const { data } = await client.get('/history');
  return data;
}

export async function getSession(sessionId: string): Promise<Session> {
  const { data } = await client.get(`/history/${sessionId}`);
  return data;
}

// -- Chat --

export async function chatWithAI(sessionId: string, message: string): Promise<string> {
  const { data } = await client.post('/chat', { session_id: sessionId, message });
  return data.response;
}

export function getDownloadUrl(sessionId: string): string {
  const base = import.meta.env.VITE_API_URL || '';
  return `${base}/api/results/${sessionId}/download`;
}

// -- Ingestion --

export async function getIngestionLogs(
  page: number = 1,
  pageSize: number = 50,
  emailType?: string,
  status?: string,
) {
  const params: Record<string, string> = { page: String(page), page_size: String(pageSize) };
  if (emailType) params.email_type = emailType;
  if (status) params.status = status;
  const { data } = await client.get('/ingestion/logs', { params });
  return data;
}

export async function getIngestionStats() {
  const { data } = await client.get('/ingestion/stats');
  return data;
}

export async function pollBankStatement() {
  const { data } = await client.post('/ingestion/poll/bank-statement');
  return data;
}

export async function pollBridgeFile() {
  const { data } = await client.post('/ingestion/poll/bridge-file');
  return data;
}

export async function pollLmsFile() {
  const { data } = await client.post('/ingestion/poll/lms-file');
  return data;
}

// -- Schedules --

export async function getSchedules(page: number = 1, pageSize: number = 30) {
  const { data } = await client.get('/schedules', { params: { page, page_size: pageSize } });
  return data;
}

export async function getTodaySchedule() {
  const { data } = await client.get('/schedules/today');
  return data;
}

export async function triggerSchedule(scheduleId: string) {
  const { data } = await client.post(`/schedules/${scheduleId}/trigger`);
  return data;
}

// -- LMS Verification --

export async function getLmsVerification(
  sessionId: string,
  page: number = 1,
  pageSize: number = 50,
  stage2Status?: string,
  search?: string,
) {
  const params: Record<string, string> = { page: String(page), page_size: String(pageSize) };
  if (stage2Status) params.stage2_status = stage2Status;
  if (search) params.search = search;
  const { data } = await client.get(`/results/${sessionId}/lms-verification`, { params });
  return data;
}

export async function getLmsSummary(sessionId: string) {
  const { data } = await client.get(`/results/${sessionId}/lms-summary`);
  return data;
}
