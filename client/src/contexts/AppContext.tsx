import React, { createContext, useContext, useReducer, useEffect, ReactNode } from 'react';
import { 
  AppState, 
  AppContextType, 
  ServerInfo, 
  Report, 
  UploadResponse, 
  ReportResponse, 
  ApiError,
  DemoRevenueSummary
} from '../types';

const AppContext = createContext<AppContextType | undefined>(undefined);

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:4000';

// Action types
const ACTIONS = {
  SET_LOADING: 'SET_LOADING',
  SET_ERROR: 'SET_ERROR',
  SET_SUCCESS: 'SET_SUCCESS',
  SET_SERVER_INFO: 'SET_SERVER_INFO',
  SET_REPORTS: 'SET_REPORTS',
  SET_COMPANY_ID: 'SET_COMPANY_ID',
  SET_PROCESSING_STEPS: 'SET_PROCESSING_STEPS',
  RESET_MESSAGES: 'RESET_MESSAGES',
  ADD_REPORT: 'ADD_REPORT',
  SET_UPLOAD_PROGRESS: 'SET_UPLOAD_PROGRESS',
  SET_DEMO_SUMMARY: 'SET_DEMO_SUMMARY'
} as const;

type ActionType = 
  | { type: 'SET_LOADING'; payload: { type: keyof AppState['loading']; value: boolean } }
  | { type: 'SET_ERROR'; payload: string | null }
  | { type: 'SET_SUCCESS'; payload: string | null }
  | { type: 'SET_SERVER_INFO'; payload: ServerInfo | null }
  | { type: 'SET_REPORTS'; payload: Report[] }
  | { type: 'SET_COMPANY_ID'; payload: string }
  | { type: 'SET_PROCESSING_STEPS'; payload: string[] }
  | { type: 'RESET_MESSAGES' }
  | { type: 'ADD_REPORT'; payload: Report }
  | { type: 'SET_UPLOAD_PROGRESS'; payload: { step: keyof AppState['uploadProgress']; completed: boolean } }
  | { type: 'SET_DEMO_SUMMARY'; payload: DemoRevenueSummary | null };

// Initial state
const initialState: AppState = {
  loading: {
    upload: false,
    report: false,
    server: false
  },
  error: null,
  success: null,
  serverInfo: null,
  reports: [],
  companyId: '1',
  processingSteps: [],
  uploadProgress: {
    upload: false,
    ingestion: false,
    calculation: false,
    questions: false,
    storage: false
  },
  demoSummary: null
};

// Reducer
function appReducer(state: AppState, action: ActionType): AppState {
  switch (action.type) {
    case ACTIONS.SET_LOADING:
      return {
        ...state,
        loading: {
          ...state.loading,
          [action.payload.type]: action.payload.value
        }
      };
    
    case ACTIONS.SET_ERROR:
      return {
        ...state,
        error: action.payload,
        success: null
      };
    
    case ACTIONS.SET_SUCCESS:
      return {
        ...state,
        success: action.payload,
        error: null
      };
    
    case ACTIONS.SET_SERVER_INFO:
      return {
        ...state,
        serverInfo: action.payload
      };
    
    case ACTIONS.SET_REPORTS:
      return {
        ...state,
        reports: action.payload
      };
    
    case ACTIONS.SET_COMPANY_ID:
      return {
        ...state,
        companyId: action.payload
      };
    
    case ACTIONS.SET_PROCESSING_STEPS:
      return {
        ...state,
        processingSteps: action.payload
      };

    case ACTIONS.SET_DEMO_SUMMARY:
      return {
        ...state,
        demoSummary: action.payload
      };
    
    case ACTIONS.RESET_MESSAGES:
      return {
        ...state,
        error: null,
        success: null,
        processingSteps: []
      };
    
    case ACTIONS.ADD_REPORT:
      return {
        ...state,
        reports: [action.payload, ...state.reports]
      };
    
    case ACTIONS.SET_UPLOAD_PROGRESS:
      return {
        ...state,
        uploadProgress: {
          ...state.uploadProgress,
          [action.payload.step]: action.payload.completed
        }
      };
    
    default:
      return state;
  }
}

interface AppProviderProps {
  children: ReactNode;
}

// Context Provider
export function AppProvider({ children }: AppProviderProps) {
  const [state, dispatch] = useReducer(appReducer, initialState);

  // Check server health on mount
  useEffect(() => {
    checkServerHealth();
    fetchReports();
  }, []);

  const checkServerHealth = async (): Promise<void> => {
    dispatch({ type: ACTIONS.SET_LOADING, payload: { type: 'server', value: true } });
    
    try {
      const response = await fetch(`${API_URL}/health`);
      if (response.ok) {
        const health = await response.json();
        console.log('✅ Server health check passed:', health);
        
        // Get server info
        const infoResponse = await fetch(`${API_URL}/api/info`);
        if (infoResponse.ok) {
          const info = await infoResponse.json();
          dispatch({ type: ACTIONS.SET_SERVER_INFO, payload: info });
        }
      } else {
        throw new Error(`Server responded with status: ${response.status}`);
      }
    } catch (err) {
      console.warn('⚠️ Server health check failed:', err instanceof Error ? err.message : 'Unknown error');
      dispatch({ 
        type: ACTIONS.SET_ERROR, 
        payload: 'Unable to connect to server. Please ensure the backend is running on port 4000.'
      });
    } finally {
      dispatch({ type: ACTIONS.SET_LOADING, payload: { type: 'server', value: false } });
    }
  };

  const fetchReports = async (): Promise<void> => {
    try {
      const response = await fetch(`${API_URL}/api/reports`);
      if (response.ok) {
        const reports = await response.json();
        dispatch({ type: ACTIONS.SET_REPORTS, payload: reports });
      }
    } catch (err) {
      console.warn('Failed to fetch reports:', err instanceof Error ? err.message : 'Unknown error');
    }
  };

  const uploadFile = async (file: File): Promise<boolean> => {
    if (!file) {
      dispatch({ type: ACTIONS.SET_ERROR, payload: 'Please select a file to upload.' });
      return false;
    }

    if (!state.companyId || parseInt(state.companyId) <= 0) {
      dispatch({ type: ACTIONS.SET_ERROR, payload: 'Please enter a valid company ID.' });
      return false;
    }

    dispatch({ type: ACTIONS.SET_LOADING, payload: { type: 'upload', value: true } });
    dispatch({ type: ACTIONS.RESET_MESSAGES });

    // Reset progress
    Object.keys(state.uploadProgress).forEach(step => {
      dispatch({ 
        type: ACTIONS.SET_UPLOAD_PROGRESS, 
        payload: { step: step as keyof AppState['uploadProgress'], completed: false } 
      });
    });

    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('company_id', state.companyId);

      dispatch({ type: ACTIONS.SET_UPLOAD_PROGRESS, payload: { step: 'upload', completed: true } });
      dispatch({ type: ACTIONS.SET_SUCCESS, payload: 'Uploading file and starting processing pipeline...' });

      const response = await fetch(`${API_URL}/api/upload`, {
        method: 'POST',
        body: formData,
      });

      const result: UploadResponse = await response.json();

      if (!response.ok) {
        throw new Error((result as unknown as ApiError).detail || `Server error: ${response.status}`);
      }

      // Update progress based on successful completion
      ['ingestion', 'calculation', 'questions', 'storage'].forEach(step => {
        dispatch({ 
          type: ACTIONS.SET_UPLOAD_PROGRESS, 
          payload: { step: step as keyof AppState['uploadProgress'], completed: true } 
        });
      });

      dispatch({ type: ACTIONS.SET_SUCCESS, payload: 'File processed successfully! All pipeline steps completed.' });
      dispatch({ type: ACTIONS.SET_PROCESSING_STEPS, payload: result.processing_steps || [] });
      
      // Refresh reports list
      await fetchReports();
      // Refresh demo summary (best-effort)
      await refreshDemoSummary();

      return true;

    } catch (err) {
      console.error('Upload error:', err);
      dispatch({ 
        type: ACTIONS.SET_ERROR, 
        payload: `Upload failed: ${err instanceof Error ? err.message : 'Unknown error'}` 
      });
      return false;
    } finally {
      dispatch({ type: ACTIONS.SET_LOADING, payload: { type: 'upload', value: false } });
    }
  };

  const refreshDemoSummary = async (): Promise<void> => {
    if (!state.companyId || parseInt(state.companyId) <= 0) {
      dispatch({ type: ACTIONS.SET_DEMO_SUMMARY, payload: null });
      return;
    }

    try {
      const response = await fetch(
        `${API_URL}/api/demo/revenue-summary?company_id=${encodeURIComponent(state.companyId)}`
      );

      if (!response.ok) {
        dispatch({ type: ACTIONS.SET_DEMO_SUMMARY, payload: null });
        return;
      }

      const result: DemoRevenueSummary = await response.json();
      dispatch({ type: ACTIONS.SET_DEMO_SUMMARY, payload: result });
    } catch (err) {
      console.warn('Failed to fetch demo summary:', err instanceof Error ? err.message : 'Unknown error');
      dispatch({ type: ACTIONS.SET_DEMO_SUMMARY, payload: null });
    }
  };

  const generateReport = async (): Promise<Report | null> => {
    if (!state.companyId || parseInt(state.companyId) <= 0) {
      dispatch({ type: ACTIONS.SET_ERROR, payload: 'Please enter a valid company ID to generate a report.' });
      return null;
    }

    dispatch({ type: ACTIONS.SET_LOADING, payload: { type: 'report', value: true } });
    dispatch({ type: ACTIONS.RESET_MESSAGES });

    try {
      dispatch({ type: ACTIONS.SET_SUCCESS, payload: 'Generating report... This may take a few moments.' });

      const response = await fetch(`${API_URL}/api/generate-report`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ company_id: parseInt(state.companyId) }),
      });

      const result: ReportResponse = await response.json();

      if (!response.ok) {
        throw new Error((result as unknown as ApiError).detail || `Server error: ${response.status}`);
      }

      dispatch({ type: ACTIONS.SET_SUCCESS, payload: 'Report generated successfully!' });
      dispatch({ type: ACTIONS.SET_PROCESSING_STEPS, payload: result.processing_steps || [] });
      
      // Add new report to list
      const newReport: Report = {
        id: result.report_filename,
        filename: result.report_filename,
        url: `${API_URL}/reports/${result.report_filename}`,
        created: new Date().toISOString(),
        size: 0,
        company_id: result.company_id
      };
      
      dispatch({ type: ACTIONS.ADD_REPORT, payload: newReport });
      
      return newReport;

    } catch (err) {
      console.error('Report generation error:', err);
      let errorMessage = `Report generation failed: ${err instanceof Error ? err.message : 'Unknown error'}`;
      
      if (err instanceof Error && err.message.includes('No financial data found')) {
        errorMessage += '\n\n💡 Please upload and process some financial data first before generating a report.';
      }
      
      dispatch({ type: ACTIONS.SET_ERROR, payload: errorMessage });
      return null;
    } finally {
      dispatch({ type: ACTIONS.SET_LOADING, payload: { type: 'report', value: false } });
    }
  };

  const setCompanyId = (id: string): void => {
    dispatch({ type: ACTIONS.SET_COMPANY_ID, payload: id });
  };

  const clearMessages = (): void => {
    dispatch({ type: ACTIONS.RESET_MESSAGES });
  };

  const value: AppContextType = {
    ...state,
    uploadFile,
    generateReport,
    setCompanyId,
    clearMessages,
    refreshReports: fetchReports,
    refreshDemoSummary,
    checkServerHealth
  };

  return (
    <AppContext.Provider value={value}>
      {children}
    </AppContext.Provider>
  );
}

// Custom hook to use the context
export function useApp(): AppContextType {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error('useApp must be used within an AppProvider');
  }
  return context;
}

export { API_URL };