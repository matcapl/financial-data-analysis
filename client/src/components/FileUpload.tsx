import React, { useState } from 'react';
import { useApp } from '../contexts/AppContext';
import LoadingSpinner from './LoadingSpinner';
import ProgressIndicator from './ProgressIndicator';
import StatusMessage from './StatusMessage';

const FileUpload: React.FC = () => {
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

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [dragOver, setDragOver] = useState<boolean>(false);

  const allowedTypes = ['.xlsx', '.pdf', '.csv'];
  const maxSize = 12 * 1024 * 1024; // 12MB

  const validateFile = (file: File): string | null => {
    const fileExtension = file.name.toLowerCase().substring(file.name.lastIndexOf('.'));
    
    if (!allowedTypes.includes(fileExtension)) {
      return `Invalid file type. Please upload ${allowedTypes.join(', ')} files only.`;
    }

    if (file.size > maxSize) {
      return `File size too large. Maximum size is ${(maxSize / 1024 / 1024).toFixed(0)}MB.`;
    }

    return null;
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>): void => {
    const file = e.target.files?.[0];
    
    if (!file) {
      setSelectedFile(null);
      clearMessages();
      return;
    }

    const error = validateFile(file);
    if (error) {
      setSelectedFile(null);
      clearMessages();
      return;
    }

    setSelectedFile(file);
    clearMessages();
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>): void => {
    e.preventDefault();
    setDragOver(false);
    
    const file = e.dataTransfer.files[0];
    if (!file) return;

    const error = validateFile(file);
    if (error) {
      clearMessages();
      return;
    }

    setSelectedFile(file);
    clearMessages();
  };

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>): void => {
    e.preventDefault();
    e.stopPropagation();
    setDragOver(true);
  };

  const handleDragLeave = (e: React.DragEvent<HTMLDivElement>): void => {
    e.preventDefault();
    e.stopPropagation();
    // Only set dragOver to false if we're leaving the drop zone itself
    if (!e.currentTarget.contains(e.relatedTarget as Node)) {
      setDragOver(false);
    }
  };

  const handleDragEnter = (e: React.DragEvent<HTMLDivElement>): void => {
    e.preventDefault();
    e.stopPropagation();
    setDragOver(true);
  };

  const handleCompanyIdChange = (e: React.ChangeEvent<HTMLInputElement>): void => {
    const value = e.target.value;
    
    // Validate company ID (must be positive integer)
    if (value === '' || (/^\d+$/.test(value) && parseInt(value) > 0)) {
      setCompanyId(value);
    }
  };

  const handleUpload = async (): Promise<void> => {
    if (!selectedFile) return;
    
    const success = await uploadFile(selectedFile);
    if (success) {
      setSelectedFile(null);
      const fileInput = document.getElementById('file-input') as HTMLInputElement;
      if (fileInput) fileInput.value = '';
    }
  };

  const handleGenerateReport = async (): Promise<void> => {
    await generateReport();
  };

  const formatFileSize = (bytes: number): string => {
    const mb = bytes / 1024 / 1024;
    return mb < 1 ? `${(bytes / 1024).toFixed(1)} KB` : `${mb.toFixed(2)} MB`;
  };

  return (
    <div className="bg-white shadow-xl rounded-2xl border border-gray-100 overflow-hidden">
      {/* Header */}
      <div className="bg-gradient-to-r from-blue-600 to-purple-600 p-6">
        <h2 className="text-2xl font-bold text-white mb-2 flex items-center">
          <svg className="w-7 h-7 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
          </svg>
          Upload Financial Data
        </h2>
        <p className="text-blue-100">
          Upload financial data files and generate comprehensive analysis reports
        </p>
      </div>

      <div className="p-6">
        {/* Server Status */}
        {loading.server ? (
          <LoadingSpinner size="sm" text="Checking server status..." />
        ) : serverInfo ? (
          <div className="mb-6 p-4 bg-emerald-50 border border-emerald-200 rounded-xl">
            <div className="flex items-center">
              <div className="w-3 h-3 bg-emerald-500 rounded-full mr-3 animate-pulse" />
              <span className="text-sm text-emerald-700 font-medium">
                Server connected ({serverInfo.server} v{serverInfo.version})
              </span>
            </div>
          </div>
        ) : error && (
          <div className="mb-6">
            <StatusMessage type="error" message={error} onClose={clearMessages} />
          </div>
        )}

        <div className="grid grid-cols-1 xl:grid-cols-2 gap-8">
          {/* Upload Section */}
          <div className="space-y-6">
            <div className="flex items-center mb-4">
              <svg className="w-6 h-6 text-blue-600 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              <h3 className="text-lg font-semibold text-gray-800">File Upload</h3>
            </div>
            
            {/* Company ID Input */}
            <div>
              <label htmlFor="company-id" className="block text-sm font-semibold text-gray-700 mb-3">
                Company ID
              </label>
              <input
                id="company-id"
                type="number"
                min="1"
                value={companyId}
                onChange={handleCompanyIdChange}
                className="w-full px-4 py-3 border-2 border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-all duration-200 font-medium"
                placeholder="Enter company ID (e.g., 1)"
                disabled={loading.upload}
              />
            </div>

            {/* File Drop Zone */}
            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-3">
                Financial Data File
              </label>
              
              <div
                className={`relative border-2 border-dashed rounded-2xl p-12 transition-all duration-300 ${
                  dragOver 
                    ? 'border-blue-500 bg-blue-100 scale-105 shadow-lg' 
                    : selectedFile 
                      ? 'border-emerald-300 bg-emerald-50' 
                      : 'border-gray-300 bg-gray-50 hover:border-blue-300 hover:bg-blue-25'
                } ${loading.upload ? 'pointer-events-none opacity-50' : 'cursor-pointer'}`}
                onDrop={handleDrop}
                onDragOver={handleDragOver}
                onDragEnter={handleDragEnter}
                onDragLeave={handleDragLeave}
              >
                <input
                  id="file-input"
                  type="file"
                  accept=".xlsx,.pdf,.csv"
                  onChange={handleFileChange}
                  className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                  disabled={loading.upload}
                />
                
                <div className="text-center">
                  {/* Dynamic Icon based on state */}
                  {dragOver ? (
                    <div className="mx-auto h-16 w-16 bg-blue-100 rounded-2xl flex items-center justify-center mb-6 animate-bounce-subtle">
                      <svg className="h-8 w-8 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                      </svg>
                    </div>
                  ) : selectedFile ? (
                    <div className="mx-auto h-16 w-16 bg-emerald-100 rounded-2xl flex items-center justify-center mb-6">
                      <svg className="h-8 w-8 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                    </div>
                  ) : (
                    <div className="mx-auto h-16 w-16 bg-gray-100 rounded-2xl flex items-center justify-center mb-6 group-hover:bg-blue-100 transition-colors">
                      <svg className="h-8 w-8 text-gray-400 group-hover:text-blue-500 transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                      </svg>
                    </div>
                  )}
                  
                  {/* Dynamic Text based on state */}
                  {dragOver ? (
                    <div>
                      <div className="text-lg font-semibold text-blue-700 mb-2">
                        🎯 Drop your file here!
                      </div>
                      <p className="text-sm text-blue-600">
                        Release to upload your financial data file
                      </p>
                    </div>
                  ) : selectedFile ? (
                    <div>
                      <div className="text-lg font-semibold text-emerald-700 mb-2">
                        ✅ File Ready to Upload
                      </div>
                      <p className="text-sm text-emerald-600">
                        Click "Upload and Process" below to continue
                      </p>
                    </div>
                  ) : (
                    <div>
                      <div className="text-lg font-semibold text-gray-700 mb-2">
                        📁 Upload Your Financial Data
                      </div>
                      <div className="text-sm text-gray-600 mb-4">
                        <span className="font-semibold text-blue-600 hover:text-blue-700">Click to browse files</span>
                        <span className="text-gray-400 mx-2">•</span>
                        <span className="font-medium">Drag & drop files here</span>
                      </div>
                      <div className="inline-flex items-center space-x-6 text-xs text-gray-500">
                        <div className="flex items-center">
                          <div className="w-8 h-6 bg-green-500 rounded-sm mr-2 flex items-center justify-center">
                            <span className="text-white text-xs font-bold">XLS</span>
                          </div>
                          Excel
                        </div>
                        <div className="flex items-center">
                          <div className="w-8 h-6 bg-red-500 rounded-sm mr-2 flex items-center justify-center">
                            <span className="text-white text-xs font-bold">PDF</span>
                          </div>
                          PDF
                        </div>
                        <div className="flex items-center">
                          <div className="w-8 h-6 bg-blue-500 rounded-sm mr-2 flex items-center justify-center">
                            <span className="text-white text-xs font-bold">CSV</span>
                          </div>
                          CSV
                        </div>
                      </div>
                    </div>
                  )}
                  
                  <div className="mt-4 text-xs text-gray-500">
                    Maximum file size: 12MB
                  </div>
                </div>
              </div>
              
              {selectedFile && (
                <div className="mt-4 p-4 bg-blue-50 border-2 border-blue-200 rounded-xl">
                  <div className="flex items-center">
                    <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center mr-3">
                      <svg className="w-6 h-6 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                      </svg>
                    </div>
                    <div className="flex-1">
                      <div className="font-semibold text-blue-800">{selectedFile.name}</div>
                      <div className="text-sm text-blue-600">{formatFileSize(selectedFile.size)}</div>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Upload Button */}
            <button
              onClick={handleUpload}
              disabled={loading.upload || !selectedFile || !companyId}
              className="w-full bg-gradient-to-r from-blue-600 to-blue-700 text-white py-4 px-6 rounded-xl hover:from-blue-700 hover:to-blue-800 disabled:from-gray-400 disabled:to-gray-500 disabled:cursor-not-allowed transition-all duration-200 font-semibold shadow-lg hover:shadow-xl transform hover:scale-[1.02] active:scale-[0.98]"
            >
              {loading.upload ? (
                <div className="flex items-center justify-center">
                  <LoadingSpinner size="sm" text="" />
                  <span className="ml-3">Processing Pipeline...</span>
                </div>
              ) : (
                <div className="flex items-center justify-center">
                  <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                  </svg>
                  Upload and Process
                </div>
              )}
            </button>
          </div>

          {/* Report Generation Section */}
          <div className="space-y-6">
            <div className="flex items-center mb-4">
              <svg className="w-6 h-6 text-emerald-600 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              <h3 className="text-lg font-semibold text-gray-800">Generate Reports</h3>
            </div>
            
            <div className="p-6 bg-gradient-to-br from-emerald-50 to-blue-50 rounded-xl border-2 border-emerald-100">
              <p className="text-sm text-gray-700 mb-6 leading-relaxed">
                Generate comprehensive financial analysis reports with metrics, insights, and analytical questions based on your uploaded data.
              </p>

              <div className="space-y-4">
                <div className="grid grid-cols-3 gap-3 text-xs">
                  <div className="text-center p-3 bg-white rounded-lg border">
                    <div className="font-semibold text-gray-800">📊</div>
                    <div className="text-gray-600 mt-1">Metrics & KPIs</div>
                  </div>
                  <div className="text-center p-3 bg-white rounded-lg border">
                    <div className="font-semibold text-gray-800">📈</div>
                    <div className="text-gray-600 mt-1">Trend Analysis</div>
                  </div>
                  <div className="text-center p-3 bg-white rounded-lg border">
                    <div className="font-semibold text-gray-800">❓</div>
                    <div className="text-gray-600 mt-1">AI Questions</div>
                  </div>
                </div>

                <button
                  onClick={handleGenerateReport}
                  disabled={loading.report || !companyId}
                  className="w-full bg-gradient-to-r from-emerald-600 to-emerald-700 text-white py-4 px-6 rounded-xl hover:from-emerald-700 hover:to-emerald-800 disabled:from-gray-400 disabled:to-gray-500 disabled:cursor-not-allowed transition-all duration-200 font-semibold shadow-lg hover:shadow-xl transform hover:scale-[1.02] active:scale-[0.98]"
                >
                  {loading.report ? (
                    <div className="flex items-center justify-center">
                      <LoadingSpinner size="sm" text="" />
                      <span className="ml-3">Generating Report...</span>
                    </div>
                  ) : (
                    <div className="flex items-center justify-center">
                      <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                      </svg>
                      Generate Financial Report
                    </div>
                  )}
                </button>
              </div>
            </div>

            <div className="text-xs text-gray-500 space-y-1 bg-gray-50 p-4 rounded-lg">
              <div className="font-medium text-gray-700 mb-2">File Requirements:</div>
              <p>• Formats: Excel (.xlsx), PDF (.pdf), CSV (.csv)</p>
              <p>• Maximum size: 12MB</p>
              <p>• Contains financial data with recognizable headers</p>
            </div>
          </div>
        </div>
      </div>

      {/* Progress Indicator */}
      {(loading.upload || Object.values(uploadProgress).some(Boolean)) && (
        <div className="px-6 pb-6">
          <ProgressIndicator 
            steps={uploadProgress}
            currentStep={loading.upload ? 'upload' : null}
            loading={loading.upload}
          />
        </div>
      )}

      {/* Status Messages */}
      {success && (
        <div className="px-6 pb-6">
          <StatusMessage 
            type="success" 
            message={success} 
            processingSteps={processingSteps}
            onClose={clearMessages}
          />
        </div>
      )}

      {error && !loading.server && (
        <div className="px-6 pb-6">
          <StatusMessage 
            type="error" 
            message={error}
            onClose={clearMessages}
          />
        </div>
      )}
    </div>
  );
};

export default FileUpload;