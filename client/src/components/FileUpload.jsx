import React, { useState } from 'react';

const FileUpload = () => {
    /**
     * Enhanced FileUpload Component - Phase 1 Critical Fix
     * 
     * Key improvements:
     * 1. Add progress tracking for pipeline steps
     * 2. Better error handling and user feedback
     * 3. File validation before upload
     * 4. Progress indicators for each processing step
     * 5. Company ID input validation
     */
    
    const [file, setFile] = useState(null);
    const [companyId, setCompanyId] = useState('1');
    const [uploading, setUploading] = useState(false);
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

            const response = await fetch('/api/upload', {
                method: 'POST',
                body: formData,
            });

            const result = await response.json();

            if (!response.ok) {
                throw new Error(result.error || 'Upload failed');
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
            document.getElementById('file-input').value = '';

        } catch (err) {
            console.error('Upload error:', err);
            setError(`Upload failed: ${err.message}`);
            
            // Reset progress on error
            resetProgress();
        } finally {
            setUploading(false);
        }
    };

    const getProgressIcon = (step, completed) => {
        if (completed) {
            return <span className="text-green-500">✓</span>;
        } else if (uploading) {
            return <span className="text-blue-500">⏳</span>;
        } else {
            return <span className="text-gray-400">○</span>;
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
        <div className="max-w-2xl mx-auto p-6 bg-white rounded-lg shadow-lg">
            <h2 className="text-2xl font-bold mb-6 text-gray-800">
                Financial Data Analysis Upload
            </h2>

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
                        className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                        placeholder="Enter company ID (e.g., 1)"
                        disabled={uploading}
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
                        onChange={handleFileChange}
                        accept=".xlsx,.pdf"
                        className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                        disabled={uploading}
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
                    disabled={!file || uploading || !companyId}
                    className={`w-full py-3 px-4 rounded-md font-medium transition-colors ${
                        !file || uploading || !companyId
                            ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                            : 'bg-blue-600 text-white hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500'
                    }`}
                >
                    {uploading ? 'Processing...' : 'Upload and Process'}
                </button>

                {/* Progress Indicators */}
                {(uploading || Object.values(progress).some(Boolean)) && (
                    <div className="bg-gray-50 p-4 rounded-md">
                        <h3 className="text-sm font-medium text-gray-700 mb-3">Processing Pipeline:</h3>
                        <div className="space-y-2">
                            {Object.entries(progress).map(([step, completed]) => (
                                <div key={step} className="flex items-center space-x-3">
                                    {getProgressIcon(step, completed)}
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
                        <h3 className="text-sm font-medium text-green-700 mb-2">Completed Steps:</h3>
                        <ul className="text-sm text-green-600 space-y-1">
                            {processingSteps.map((step, index) => (
                                <li key={index}>{step}</li>
                            ))}
                        </ul>
                    </div>
                )}

                {/* Success Message */}
                {message && !error && (
                    <div className="bg-green-50 border border-green-200 rounded-md p-4">
                        <p className="text-green-700">{message}</p>
                    </div>
                )}

                {/* Error Message */}
                {error && (
                    <div className="bg-red-50 border border-red-200 rounded-md p-4">
                        <p className="text-red-700">{error}</p>
                    </div>
                )}

                {/* Instructions */}
                <div className="bg-blue-50 p-4 rounded-md">
                    <h3 className="text-sm font-medium text-blue-700 mb-2">Instructions:</h3>
                    <ul className="text-sm text-blue-600 space-y-1">
                        <li>1. Enter your company ID (must be a positive integer)</li>
                        <li>2. Select an Excel (.xlsx) or PDF (.pdf) file containing financial data</li>
                        <li>3. Click "Upload and Process" to run the complete analysis pipeline</li>
                        <li>4. Wait for all processing steps to complete</li>
                        <li>5. Generate reports using the report generation feature</li>
                    </ul>
                </div>
            </div>
        </div>
    );
};

export default FileUpload;