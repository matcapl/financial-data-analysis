import React from 'react';

const ProgressIndicator = ({ steps, currentStep, loading }) => {
  const stepDescriptions = {
    upload: 'File Upload',
    ingestion: 'Data Extraction', 
    calculation: 'Metric Calculations',
    questions: 'Question Generation',
    storage: 'Processing Complete'
  };

  const getStepIcon = (step, stepKey) => {
    if (step) return '✅';
    if (loading && stepKey === currentStep) return '🔄';
    return '○';
  };

  const getStepClass = (step, stepKey) => {
    if (step) return 'text-green-600';
    if (loading && stepKey === currentStep) return 'text-blue-600 animate-pulse';
    return 'text-gray-400';
  };

  return (
    <div className="bg-gray-50 rounded-lg p-4">
      <h3 className="text-lg font-semibold text-gray-800 mb-3">Processing Pipeline:</h3>
      <div className="space-y-2">
        {Object.entries(steps).map(([stepKey, completed]) => (
          <div key={stepKey} className={`flex items-center ${getStepClass(completed, stepKey)}`}>
            <span className="mr-3 text-lg">{getStepIcon(completed, stepKey)}</span>
            <span className="text-sm font-medium">{stepDescriptions[stepKey]}</span>
          </div>
        ))}
      </div>
    </div>
  );
};

export default ProgressIndicator;