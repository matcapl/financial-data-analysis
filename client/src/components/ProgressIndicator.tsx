import React from 'react';
import { UploadProgress } from '../types';

interface ProgressIndicatorProps {
  steps: UploadProgress;
  currentStep?: keyof UploadProgress | null;
  loading?: boolean;
}

const ProgressIndicator: React.FC<ProgressIndicatorProps> = ({ 
  steps, 
  currentStep, 
  loading 
}) => {
  const stepDescriptions: Record<keyof UploadProgress, string> = {
    upload: 'File Upload',
    ingestion: 'Data Extraction', 
    calculation: 'Metric Calculations',
    questions: 'Question Generation',
    storage: 'Processing Complete'
  };

  const getStepIcon = (completed: boolean, stepKey: keyof UploadProgress): React.ReactNode => {
    if (completed) {
      return (
        <div className="w-6 h-6 bg-emerald-100 rounded-full flex items-center justify-center">
          <svg className="w-4 h-4 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
        </div>
      );
    }
    
    if (loading && stepKey === currentStep) {
      return (
        <div className="w-6 h-6 bg-blue-100 rounded-full flex items-center justify-center">
          <div className="w-3 h-3 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
        </div>
      );
    }
    
    return (
      <div className="w-6 h-6 bg-gray-100 rounded-full flex items-center justify-center">
        <div className="w-2 h-2 bg-gray-400 rounded-full" />
      </div>
    );
  };

  const getStepClass = (completed: boolean, stepKey: keyof UploadProgress): string => {
    if (completed) return 'text-emerald-700 bg-emerald-50';
    if (loading && stepKey === currentStep) return 'text-blue-700 bg-blue-50';
    return 'text-gray-500 bg-gray-50';
  };

  const getConnectorClass = (completed: boolean): string => {
    return completed ? 'bg-emerald-200' : 'bg-gray-200';
  };

  const stepEntries = Object.entries(steps) as [keyof UploadProgress, boolean][];

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
      <h3 className="text-lg font-semibold text-gray-800 mb-5 flex items-center">
        <svg className="w-5 h-5 mr-2 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v10a2 2 0 002 2h8a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
        </svg>
        Processing Pipeline
      </h3>
      
      <div className="relative">
        {stepEntries.map(([stepKey, completed], index) => (
          <div key={stepKey} className="relative">
            <div className={`flex items-center p-3 rounded-lg transition-all duration-300 ${getStepClass(completed, stepKey)}`}>
              <div className="flex items-center flex-1">
                {getStepIcon(completed, stepKey)}
                <div className="ml-4">
                  <span className="font-medium text-sm">
                    {stepDescriptions[stepKey]}
                  </span>
                  {loading && stepKey === currentStep && (
                    <div className="text-xs text-blue-600 mt-1 animate-pulse">
                      In progress...
                    </div>
                  )}
                </div>
              </div>
              
              {completed && (
                <div className="text-xs text-emerald-600 font-medium">
                  Complete
                </div>
              )}
            </div>
            
            {/* Connector line between steps */}
            {index < stepEntries.length - 1 && (
              <div className="flex justify-center py-1">
                <div className={`w-0.5 h-3 transition-colors duration-300 ${getConnectorClass(completed)}`} />
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};

export default ProgressIndicator;