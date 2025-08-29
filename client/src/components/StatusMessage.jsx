import React from 'react';

const StatusMessage = ({ type, message, processingSteps = [], onClose }) => {
  if (!message) return null;

  const getMessageClass = () => {
    switch (type) {
      case 'success':
        return 'bg-green-50 border-green-200 text-green-700';
      case 'error':
        return 'bg-red-50 border-red-200 text-red-700';
      case 'info':
        return 'bg-blue-50 border-blue-200 text-blue-700';
      default:
        return 'bg-gray-50 border-gray-200 text-gray-700';
    }
  };

  const getIcon = () => {
    switch (type) {
      case 'success':
        return '✅';
      case 'error':
        return '❌';
      case 'info':
        return 'ℹ️';
      default:
        return '📋';
    }
  };

  return (
    <div className={`p-4 border rounded-lg ${getMessageClass()}`}>
      <div className="flex items-start">
        <span className="mr-3 text-lg flex-shrink-0">{getIcon()}</span>
        <div className="flex-1">
          <pre className="text-sm whitespace-pre-wrap font-sans">{message}</pre>
          
          {processingSteps.length > 0 && (
            <div className="mt-3">
              <h4 className="font-semibold mb-2">Processing Steps:</h4>
              <ul className="space-y-1">
                {processingSteps.map((step, index) => (
                  <li key={index} className="text-sm flex items-center">
                    <span className="mr-2">•</span>
                    {step}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
        
        {onClose && (
          <button
            onClick={onClose}
            className="ml-3 text-gray-400 hover:text-gray-600 flex-shrink-0"
            aria-label="Close message"
          >
            ✕
          </button>
        )}
      </div>
    </div>
  );
};

export default StatusMessage;