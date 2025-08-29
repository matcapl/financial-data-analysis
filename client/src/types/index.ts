export interface ServerInfo {
  server: string;
  version: string;
  status: string;
  timestamp: string;
  environment?: string;
  python_version?: string;
  database_connected?: boolean;
}

export interface LoadingState {
  upload: boolean;
  report: boolean;
  server: boolean;
}

export interface UploadProgress {
  upload: boolean;
  ingestion: boolean;
  calculation: boolean;
  questions: boolean;
  storage: boolean;
}

export interface Report {
  id: string;
  filename: string;
  url: string;
  created: string;
  size: number;
  company_id?: number;
}

export interface ProcessingStep {
  step: string;
  status: 'completed' | 'in_progress' | 'pending' | 'failed';
  message?: string;
}

export interface AppState {
  loading: LoadingState;
  error: string | null;
  success: string | null;
  serverInfo: ServerInfo | null;
  reports: Report[];
  companyId: string;
  processingSteps: string[];
  uploadProgress: UploadProgress;
}

export interface AppContextType extends AppState {
  uploadFile: (file: File) => Promise<boolean>;
  generateReport: () => Promise<Report | null>;
  setCompanyId: (id: string) => void;
  clearMessages: () => void;
  refreshReports: () => Promise<void>;
  checkServerHealth: () => Promise<void>;
}

export interface UploadResponse {
  message: string;
  filename: string;
  company_id?: number;
  processing_steps?: string[];
  file_path?: string;
}

export interface ReportResponse {
  message: string;
  company_id: number;
  report_filename: string;
  report_path?: string;
  processing_steps?: string[];
}

export interface ApiError {
  detail: string;
  message?: string;
}