import React, { useState, useEffect } from 'react';

const FileUpload = () => {
  /**
   * Enhanced FileUpload Component - CRITICAL FIXES APPLIED
   * 
   * Key improvements:
   * 1. Environment-aware API URL configuration
   * 2. Better error handling and user feedback
   * 3. File validation before upload
   * 4. Progress indicators for each processing step
   * 5. Company ID input validation
   * 6. Automatic server health check
   */
  
  const [file, setFile] = useState(null);
  const [companyId, setCompanyId] = useState('1');
  const [uploading, setUploading] = useState(false);
  const [serverInfo, setServerInfo] = useState(null);
  const [progress, setProgress] = useState({
    upload: false,
    ingestion: false,
    calculation: false,
    questions: false,
    storage: false
  });
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [processingSteps, setProcessingSteps] = useState([]);

  // Get API base URL - works for both development and production
  const getApiUrl = () => {
    // In development with proxy, use relative URLs
    if (process.env.NODE_ENV === 'development') {
      return '';
    }
    // In production, use environment variable or default
    return process.env.REACT_APP_API_URL || '';
  };

  // Check server health on component mount
  useEffect(() => {
    const checkServerHealth = async () => {
      try {
        const response = await fetch(`${getApiUrl()}/health`);
        if (response.ok) {
          const health = await response.json();
          console.log('✅ Server health check passed:', health);
        }
        
        // Get server info
        const infoResponse = await fetch(`${getApiUrl()}/api/info`);
        if (infoResponse.ok) {
          const info = await infoResponse.json();
          setServerInfo(info);
          console.log('📊 Server info:', info);
        }
      } catch (err) {
        console.warn('⚠️ Server health check failed:', err.message);
        setError('Unable to connect to server. Please ensure the backend is running on the correct port.');
      }
    };

    checkServerHealth();
  }, []);

  const handleFileChange = (e) => {
    const selectedFile = e.target.files[0];
    
    if (!selectedFile) {
      setFile(null);
      setError('');
      return;
    }

    // Validate file type
    const allowedTypes = ['.xlsx', '.pdf'];
    const fileExtension = selectedFile.name.toLowerCase().substring(selectedFile.name.lastIndexOf('.'));
    
    if (!allowedTypes.includes(fileExtension)) {
      setError('Invalid file type. Please upload an Excel (.xlsx) or PDF (.pdf) file.');
      setFile(null);
      return;
    }

    // Validate file size (10MB limit)
    const maxSize = 10 * 1024 * 1024; // 10MB
    if (selectedFile.size > maxSize) {
      setError('File too large. Please upload a file smaller than 10MB.');
      setFile(null);
      return;
    }

    setFile(selectedFile);
    setError('');
    setMessage('');
    setProcessingSteps([]);
    resetProgress();
  };

  const handleCompanyIdChange = (e) => {
    const value = e.target.value;
    
    // Validate company ID (must be positive integer)
    if (value === '' || (/^\d+$/.test(value) && parseInt(value) > 0)) {
      setCompanyId(value);
      setError('');
    } else {
      setError('Company ID must be a positive integer.');
    }
  };

  const resetProgress = () => {
    setProgress({
      upload: false,
      ingestion: false,
      calculation: false,
      questions: false,
      storage: false
    });
  };

  const updateProgress = (step, status = true) => {
    setProgress(prev => ({
      ...prev,
      [step]: status
    }));
  };

  const handleUpload = async () => {
    if (!file) {
      setError('Please select a file to upload.');
      return;
    }

    if (!companyId || parseInt(companyId) <= 0) {
      setError('Please enter a valid company ID.');
      return;
    }

    setUploading(true);
    setError('');
    setMessage('');
    setProcessingSteps([]);
    resetProgress();

    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('company_id', companyId);

      updateProgress('upload', true);
      setMessage('Uploading file and starting processing pipeline...');

      const response = await fetch(`${getApiUrl()}/api/upload`, {
        method: 'POST',
        body: formData,
      });

      const result = await response.json();

      if (!response.ok) {
        throw new Error(result.error || `Server error: ${response.status}`);
      }

      // Update progress based on successful completion
      updateProgress('ingestion', true);
      updateProgress('calculation', true);
      updateProgress('questions', true);
      updateProgress('storage', true);

      setMessage('File processed successfully! All pipeline steps completed.');
      setProcessingSteps(result.processing_steps || []);
      
      // Clear file selection after successful upload
      setFile(null);
      const fileInput = document.getElementById('file-input');
      if (fileInput) fileInput.value = '';

      // Show next steps
      setTimeout(() => {
        setMessage(prevMessage => 
          prevMessage + '\n\n🎉 Ready to generate reports! Use the report generation feature below.'
        );
      }, 2000);

    } catch (err) {
      console.error('Upload error:', err);
      setError(`Upload failed: ${err.message}`);
      
      // Provide specific guidance based on error type
      if (err.message.includes('fetch')) {
        setError(prev => prev + '\n\n💡 This might be a connection issue. Check that the server is running on the correct port.');
      }
      
      // Reset progress on error
      resetProgress();
    } finally {
      setUploading(false);
    }
  };

  const getProgressIcon = (step, completed) => {
    if (completed) {
      return '✅';
    } else if (uploading) {
      return '⏳';
    } else {
      return '○';
    }
  };

  const getProgressDescription = (step) => {
    const descriptions = {
      upload: 'File Upload',
      ingestion: 'Data Extraction',
      calculation: 'Metric Calculations',
      questions: 'Question Generation',
      storage: 'Cloud Storage'
    };
    return descriptions[step] || step;
  };

  return (
    <div className="max-w-4xl mx-auto p-6 bg-white rounded-lg shadow-lg">
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-gray-800 mb-2">
          Financial Data Analysis Upload
        </h2>
        
        {/* Server Status Indicator */}
        {serverInfo && (
          <div className="mb-4 p-3 bg-blue-50 border border-blue-200 rounded-md">
            <div className="flex items-center space-x-2">
              <span className="text-green-600">🟢</span>
              <span className="text-sm text-gray-700">
                Server running on port {serverInfo.server_port} 
                {serverInfo.vercel ? ' (Vercel)' : ' (Local)'}
                {!serverInfo.python_available && (
                  <span className="text-orange-600"> - Limited functionality (no Python)</span>
                )}
              </span>
            </div>
          </div>
        )}
      </div>

      <div className="space-y-6">
        {/* Company ID Input */}
        <div>
          <label htmlFor="company-id" className="block text-sm font-medium text-gray-700 mb-2">
            Company ID
          </label>
          <input
            id="company-id"
            type="text"
            value={companyId}
            onChange={handleCompanyIdChange}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            placeholder="Enter company ID (positive integer)"
          />
        </div>

        {/* File Input */}
        <div>
          <label htmlFor="file-input" className="block text-sm font-medium text-gray-700 mb-2">
            Select File (.xlsx or .pdf)
          </label>
          <input
            id="file-input"
            type="file"
            accept=".xlsx,.pdf"
            onChange={handleFileChange}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
          {file && (
            <p className="mt-2 text-sm text-gray-600">
              Selected: {file.name} ({(file.size / 1024 / 1024).toFixed(2)} MB)
            </p>
          )}
        </div>

        {/* Upload Button */}
        <button
          onClick={handleUpload}
          disabled={uploading || !file}
          className={`w-full py-3 px-4 rounded-md font-medium transition-colors ${
            uploading || !file
              ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
              : 'bg-blue-600 text-white hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500'
          }`}
        >
          {uploading ? 'Processing Pipeline...' : 'Upload and Process'}
        </button>

        {/* Progress Indicators */}
        {(uploading || Object.values(progress).some(Boolean)) && (
          <div className="bg-gray-50 p-4 rounded-md">
            <h3 className="text-lg font-medium text-gray-800 mb-3">Processing Pipeline:</h3>
            <div className="space-y-2">
              {Object.entries(progress).map(([step, completed]) => (
                <div key={step} className="flex items-center space-x-3">
                  <span className="text-lg">{getProgressIcon(step, completed)}</span>
                  <span className={`text-sm ${completed ? 'text-green-700' : 'text-gray-600'}`}>
                    {getProgressDescription(step)}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Processing Steps */}
        {processingSteps.length > 0 && (
          <div className="bg-green-50 p-4 rounded-md">
            <h3 className="text-lg font-medium text-green-800 mb-3">Completed Steps:</h3>
            <ul className="space-y-1">
              {processingSteps.map((step, index) => (
                <li key={index} className="text-sm text-green-700">
                  • {step}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Success Message */}
        {message && !error && (
          <div className="bg-green-100 border border-green-400 text-green-700 px-4 py-3 rounded-md">
            <pre className="whitespace-pre-wrap text-sm">{message}</pre>
          </div>
        )}

        {/* Error Message */}
        {error && (
          <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded-md">
            <pre className="whitespace-pre-wrap text-sm">{error}</pre>
          </div>
        )}

        {/* Instructions */}
        <div className="bg-gray-50 p-4 rounded-md">
          <h3 className="text-lg font-medium text-gray-800 mb-3">Instructions:</h3>
          <ol className="list-decimal list-inside space-y-1 text-sm text-gray-700">
            <li>Enter your company ID (must be a positive integer)</li>
            <li>Select an Excel (.xlsx) or PDF (.pdf) file containing financial data</li>
            <li>Click "Upload and Process" to run the complete analysis pipeline</li>
            <li>Wait for all processing steps to complete</li>
            <li>Generate reports using the report generation feature</li>
          </ol>
        </div>
      </div>
    </div>
  );
};

export default FileUpload;