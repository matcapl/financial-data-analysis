import React, { useState } from 'react';
import { useApp } from '../contexts/AppContext';
import LoadingSpinner from './LoadingSpinner';
import ProgressIndicator from './ProgressIndicator';
import StatusMessage from './StatusMessage';

const FileUpload = () => {
  const {
    companyId,
    loading,
    error,
    success,
    processingSteps,
    uploadProgress,
    serverInfo,
    uploadFile,
    generateReport,
    setCompanyId,
    clearMessages
  } = useApp();

  const [selectedFile, setSelectedFile] = useState(null);

  const handleFileChange = (e) => {
    const file = e.target.files[0];
    
    if (!file) {
      setSelectedFile(null);
      clearMessages();
      return;
    }

    // Validate file type
    const allowedTypes = ['.xlsx', '.pdf', '.csv'];
    const fileExtension = file.name.toLowerCase().substring(file.name.lastIndexOf('.'));
    
    if (!allowedTypes.includes(fileExtension)) {
      setSelectedFile(null);
      clearMessages();
      return;
    }

    // Validate file size (10MB limit)
    const maxSize = 10 * 1024 * 1024; // 10MB
    if (file.size > maxSize) {
      setSelectedFile(null);
      clearMessages();
      return;
    }

    setSelectedFile(file);
    clearMessages();
  };

  const handleCompanyIdChange = (e) => {
    const value = e.target.value;
    
    // Validate company ID (must be positive integer)
    if (value === '' || (/^\d+$/.test(value) && parseInt(value) > 0)) {
      setCompanyId(value);
    }
  };

  const handleUpload = async () => {
    if (!selectedFile) return;
    
    const success = await uploadFile(selectedFile);
    if (success) {
      setSelectedFile(null);
      const fileInput = document.getElementById('file-input');
      if (fileInput) fileInput.value = '';
    }
  };

  const handleGenerateReport = async () => {
    await generateReport();
  };

  return (
    <div className="bg-white shadow-lg rounded-lg p-6">
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-gray-800 mb-4">Upload Financial Data</h2>
        
        {/* Server Status */}
        {loading.server ? (
          <LoadingSpinner size="sm" text="Checking server status..." />
        ) : serverInfo ? (
          <div className="mb-4 p-3 bg-green-50 border border-green-200 rounded-lg">
            <div className="flex items-center">
              <span className="text-green-500 mr-2">🟢</span>
              <span className="text-sm text-green-700">
                Server connected ({serverInfo.server} v{serverInfo.version})
              </span>
            </div>
          </div>
        ) : error && (
          <StatusMessage type="error" message={error} onClose={clearMessages} />
        )}

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Upload Section */}
          <div className="space-y-4">
            <h3 className="text-lg font-semibold text-gray-800">File Upload</h3>
            
            {/* Company ID Input */}
            <div>
              <label htmlFor="company-id" className="block text-sm font-medium text-gray-700 mb-2">
                Company ID
              </label>
              <input
                id="company-id"
                type="number"
                min="1"
                value={companyId}
                onChange={handleCompanyIdChange}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="Enter company ID"
                disabled={loading.upload}
              />
            </div>

            {/* File Input */}
            <div>
              <label htmlFor="file-input" className="block text-sm font-medium text-gray-700 mb-2">
                Select Financial Data File
              </label>
              <input
                id="file-input"
                type="file"
                accept=".xlsx,.pdf,.csv"
                onChange={handleFileChange}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                disabled={loading.upload}
              />
              {selectedFile && (
                <div className="mt-2 p-2 bg-blue-50 rounded border border-blue-200">
                  <div className="text-sm text-blue-700">
                    <span className="font-medium">{selectedFile.name}</span>
                    <span className="ml-2">({(selectedFile.size / 1024 / 1024).toFixed(2)} MB)</span>
                  </div>
                </div>
              )}
            </div>

            {/* Upload Button */}
            <button
              onClick={handleUpload}
              disabled={loading.upload || !selectedFile || !companyId}
              className="w-full bg-blue-600 text-white py-3 px-4 rounded-md hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors font-medium"
            >
              {loading.upload ? (
                <div className="flex items-center justify-center">
                  <LoadingSpinner size="sm" text="" />
                  <span className="ml-2">Processing...</span>
                </div>
              ) : (
                'Upload and Process'
              )}
            </button>

            <div className="text-xs text-gray-500 space-y-1">
              <p>• Supported formats: Excel (.xlsx), PDF (.pdf), CSV (.csv)</p>
              <p>• Maximum file size: 10MB</p>
              <p>• Processing includes data extraction, validation, and metric calculations</p>
            </div>
          </div>

          {/* Report Generation Section */}
          <div className="space-y-4">
            <h3 className="text-lg font-semibold text-gray-800">Generate Reports</h3>
            
            <p className="text-sm text-gray-600">
              Generate comprehensive financial analysis reports with metrics, insights, and analytical questions.
            </p>

            <button
              onClick={handleGenerateReport}
              disabled={loading.report || !companyId}
              className="w-full bg-green-600 text-white py-3 px-4 rounded-md hover:bg-green-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors font-medium"
            >
              {loading.report ? (
                <div className="flex items-center justify-center">
                  <LoadingSpinner size="sm" text="" />
                  <span className="ml-2">Generating Report...</span>
                </div>
              ) : (
                'Generate Financial Report'
              )}
            </button>

            <div className="text-xs text-gray-500 space-y-1">
              <p>• Reports include all uploaded financial data for the company</p>
              <p>• Automatically calculates trends and variance metrics</p>
              <p>• Generates analytical questions for deeper insights</p>
            </div>
          </div>
        </div>
      </div>

      {/* Progress Indicator */}
      {(loading.upload || Object.values(uploadProgress).some(Boolean)) && (
        <div className="mb-6">
          <ProgressIndicator 
            steps={uploadProgress}
            currentStep={loading.upload ? 'upload' : null}
            loading={loading.upload}
          />
        </div>
      )}

      {/* Status Messages */}
      {success && (
        <StatusMessage 
          type="success" 
          message={success} 
          processingSteps={processingSteps}
          onClose={clearMessages}
        />
      )}

      {error && !loading.server && (
        <StatusMessage 
          type="error" 
          message={error}
          onClose={clearMessages}
        />
      )}
    </div>
  );
};

export default FileUpload;