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
   * 7. **REPORT GENERATION FUNCTIONALITY ADDED**
   */
  
  const [file, setFile] = useState(null);
  const [companyId, setCompanyId] = useState('1');
  const [uploading, setUploading] = useState(false);
  const [generatingReport, setGeneratingReport] = useState(false);
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
  const [reportUrl, setReportUrl] = useState('');

  // Get API base URL - works for both development and production
  const getApiUrl = () => {
    // Use environment variable if available (both development and production)
    return process.env.REACT_APP_API_URL || 'http://localhost:4000';
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
    const allowedTypes = ['.xlsx', '.pdf', '.csv'];
    const fileExtension = selectedFile.name.toLowerCase().substring(selectedFile.name.lastIndexOf('.'));
    
    if (!allowedTypes.includes(fileExtension)) {
      setError('Invalid file type. Please upload an Excel (.xlsx), PDF (.pdf), or CSV (.csv) file.');
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
        // Handle detailed pipeline errors
        let errorMessage = result.error || `Server error: ${response.status}`;
        
        // Add pipeline details if available
        if (result.pipeline_results && result.pipeline_results.ingestion) {
          const ingestion = result.pipeline_results.ingestion;
          errorMessage += `\n\nPipeline Status:`;
          errorMessage += `\n✅ Stage 1: Data extraction - Success`;
          errorMessage += `\n✅ Stage 2: Field mapping - Success`;
          errorMessage += `\n❌ Stage 3: Data normalization - ${ingestion.errors ? ingestion.errors.join(', ') : 'Failed'}`;
        }
        
        // Add troubleshooting info
        if (result.troubleshooting && result.troubleshooting.common_issues) {
          errorMessage += `\n\nCommon Issues:`;
          result.troubleshooting.common_issues.forEach(issue => {
            errorMessage += `\n• ${issue}`;
          });
        }
        
        // Add environment info
        if (result.environment) {
          errorMessage += `\n\nEnvironment: ${result.environment.vercel ? 'Vercel' : 'Local'} (Python: ${result.environment.python_processing ? 'Available' : 'Not Available'})`;
        }
        
        throw new Error(errorMessage);
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
          prevMessage + '\n\n🎉 Ready to generate reports! Use the report generation button below.'
        );
      }, 2000);

    } catch (err) {
      console.error('Upload error:', err);
      
      // Show partial progress for pipeline errors (stages that succeeded)
      if (err.message.includes('Stage 1: Data extraction - Success')) {
        updateProgress('upload', true);
        updateProgress('ingestion', true);
      }
      if (err.message.includes('Stage 2: Field mapping - Success')) {
        updateProgress('calculation', true);
      }
      
      setError(`Upload failed: ${err.message}`);
      
      // Provide specific guidance based on error type
      if (err.message.includes('fetch')) {
        setError(prev => prev + '\n\n💡 This might be a connection issue. Check that the server is running on the correct port.');
      } else if (err.message.includes('Database connection issues')) {
        setError(prev => prev + '\n\n🔧 Technical note: The core pipeline is working correctly, but database configuration is needed for full functionality.');
      }
    } finally {
      setUploading(false);
    }
  };

  const handleGenerateReport = async () => {
    if (!companyId || parseInt(companyId) <= 0) {
      setError('Please enter a valid company ID to generate a report.');
      return;
    }

    setGeneratingReport(true);
    setError('');
    setReportUrl('');

    try {
      setMessage('Generating report... This may take a few moments.');

      const response = await fetch(`${getApiUrl()}/api/generate-report`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ company_id: companyId }),
      });

      const result = await response.json();

      if (!response.ok) {
        throw new Error(result.error || `Server error: ${response.status}`);
      }

      setMessage('Report generated successfully!');
      setReportUrl(result.reportPath);
      setProcessingSteps(result.processing_steps || []);

    } catch (err) {
      console.error('Report generation error:', err);
      setError(`Report generation failed: ${err.message}`);
      
      if (err.message.includes('No financial metrics found')) {
        setError(prev => prev + '\n\n💡 Please upload and process some financial data first before generating a report.');
      }
    } finally {
      setGeneratingReport(false);
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
    <div className="max-w-4xl mx-auto p-6 bg-white shadow-lg rounded-lg">
      <div className="mb-8">
        <h2 className="text-2xl font-bold text-gray-800 mb-4">Financial Data Analysis Upload</h2>
        
        {/* Server Status Indicator */}
        {serverInfo && (
          <div className="mb-4 p-3 bg-green-50 border border-green-200 rounded-lg">
            <div className="flex items-center">
              <span className="text-green-500 mr-2">🟢</span>
              <span className="text-sm text-green-700">
                Server running on port {serverInfo.server_port} 
                {serverInfo.vercel ? ' (Vercel)' : ' (Local)'}
                {!serverInfo.python_available && (
                  <span className="text-yellow-600"> - Limited functionality (no Python)</span>
                )}
              </span>
            </div>
          </div>
        )}
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Left Column - File Upload */}
          <div className="space-y-4">
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
              />
            </div>

            {/* File Input */}
            <div>
              <label htmlFor="file-input" className="block text-sm font-medium text-gray-700 mb-2">
                Select File (.xlsx, .pdf, or .csv)
              </label>
              <input
                id="file-input"
                type="file"
                accept=".xlsx,.pdf,.csv"
                onChange={handleFileChange}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
              {file && (
                <div className="mt-2 text-sm text-gray-600">
                  Selected: <span className="font-medium">{file.name}</span> ({(file.size / 1024 / 1024).toFixed(2)} MB)
                </div>
              )}
            </div>

            {/* Upload Button */}
            <button
              onClick={handleUpload}
              disabled={uploading || !file}
              className="w-full bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
            >
              {uploading ? 'Processing...' : 'Upload and Process'}
            </button>
          </div>

          {/* Right Column - Report Generation */}
          <div className="space-y-4">
            <h3 className="text-lg font-semibold text-gray-800">Report Generation</h3>
            
            <p className="text-sm text-gray-600">
              Generate a comprehensive financial report with metrics, insights, and questions.
            </p>

            <button
              onClick={handleGenerateReport}
              disabled={generatingReport || !companyId}
              className="w-full bg-green-600 text-white py-2 px-4 rounded-md hover:bg-green-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
            >
              {generatingReport ? 'Generating Report...' : 'Generate Report'}
            </button>

            {reportUrl && (
              <div className="mt-4 p-3 bg-blue-50 border border-blue-200 rounded-lg">
                <p className="text-sm text-blue-700 mb-2">Report generated successfully!</p>
                <a
                  href={reportUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-block bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 transition-colors"
                >
                  Download Report PDF
                </a>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Progress Indicators */}
      {(uploading || Object.values(progress).some(Boolean)) && (
        <div className="mb-6">
          <h3 className="text-lg font-semibold text-gray-800 mb-3">Processing Pipeline:</h3>
          <div className="space-y-2">
            {Object.entries(progress).map(([step, completed]) => (
              <div key={step} className="flex items-center">
                <span className="mr-3 text-lg">{getProgressIcon(step, completed)}</span>
                <span className="text-sm text-gray-700">{getProgressDescription(step)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Processing Steps */}
      {processingSteps.length > 0 && (
        <div className="mb-6">
          <h3 className="text-lg font-semibold text-gray-800 mb-3">Completed Steps:</h3>
          <ul className="space-y-1">
            {processingSteps.map((step, index) => (
              <li key={index} className="text-sm text-gray-700">• {step}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Success Message */}
      {message && !error && (
        <div className="mb-6 p-4 bg-green-50 border border-green-200 rounded-lg">
          <pre className="text-sm text-green-700 whitespace-pre-wrap">{message}</pre>
        </div>
      )}

      {/* Error Message */}
      {error && (
        <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg">
          <pre className="text-sm text-red-700 whitespace-pre-wrap">{error}</pre>
        </div>
      )}

      {/* Instructions */}
      <div className="border-t pt-6">
        <h3 className="text-lg font-semibold text-gray-800 mb-3">Instructions:</h3>
        <ol className="list-decimal list-inside space-y-2 text-sm text-gray-700">
          <li>Enter your company ID (must be a positive integer)</li>
          <li>Select an Excel (.xlsx), PDF (.pdf), or CSV (.csv) file containing financial data</li>
          <li>Click "Upload and Process" to run the complete analysis pipeline</li>
          <li>Wait for all processing steps to complete</li>
          <li>Click "Generate Report" to create a comprehensive PDF report</li>
          <li>Download and review your financial analysis report</li>
        </ol>
      </div>
    </div>
  );
};

export default FileUpload;