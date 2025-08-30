import React from 'react';

interface StatusMessageProps {
  type: 'success' | 'error' | 'info' | 'warning';
  message: string;
  processingSteps?: string[];
  onClose?: () => void;
}

const StatusMessage: React.FC<StatusMessageProps> = ({ 
  type, 
  message, 
  processingSteps = [], 
  onClose 
}) => {
  if (!message) return null;

  const getMessageClass = (): string => {
    switch (type) {
      case 'success':
        return 'bg-emerald-50 border-emerald-200 text-emerald-800';
      case 'error':
        return 'bg-red-50 border-red-200 text-red-800';
      case 'warning':
        return 'bg-amber-50 border-amber-200 text-amber-800';
      case 'info':
        return 'bg-blue-50 border-blue-200 text-blue-800';
      default:
        return 'bg-gray-50 border-gray-200 text-gray-800';
    }
  };

  const getIcon = (): string => {
    switch (type) {
      case 'success':
        return '✅';
      case 'error':
        return '❌';
      case 'warning':
        return '⚠️';
      case 'info':
        return 'ℹ️';
      default:
        return '📋';
    }
  };

  return (
    <div className={`p-4 border-2 rounded-xl shadow-sm ${getMessageClass()} transition-all duration-300`}>
      <div className="flex items-start">
        <span className="mr-3 text-xl flex-shrink-0">{getIcon()}</span>
        <div className="flex-1 min-w-0">
          <div className="text-sm whitespace-pre-wrap font-medium leading-relaxed">
            {message}
          </div>
          
          {processingSteps.length > 0 && (
            <div className="mt-4 p-3 bg-white/50 rounded-lg">
              <h4 className="font-semibold text-xs uppercase tracking-wide mb-3 opacity-75">
                Processing Steps
              </h4>
              <ul className="space-y-2">
                {processingSteps.map((step, index) => (
                  <li key={index} className="text-sm flex items-start">
                    <span className="mr-3 mt-0.5 w-1.5 h-1.5 bg-current rounded-full flex-shrink-0 opacity-60" />
                    <span className="leading-relaxed">{step}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
        
        {onClose && (
          <button
            onClick={onClose}
            className="ml-3 p-1 text-gray-400 hover:text-gray-600 hover:bg-white/50 rounded-md transition-colors flex-shrink-0"
            aria-label="Close message"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        )}
      </div>
    </div>
  );
};

export default StatusMessage;