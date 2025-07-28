import React, { useState } from 'react';

function FileUpload({ onUploadSuccess }) {
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);

  const handleFileChange = (event) => {
    setFile(event.target.files[0]);
    setError(null);
  };

  const handleUpload = async () => {
    if (!file) {
      setError('Please select a file');
      return;
    }
    setUploading(true);
    const formData = new FormData();
    formData.append('file', file);
    try {
      const response = await fetch('/api/upload', {
        method: 'POST',
        body: formData,
      });
      const data = await response.json();
      if (response.ok) {
        onUploadSuccess(data);
      } else {
        setError(data.error || 'Upload failed');
      }
    } catch (err) {
      setError('Upload error: ' + err.message);
    }
    setUploading(false);
  };

  const handleGenerateReport = async () => {
    try {
      const response = await fetch('/api/generate-report', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ company_id: 1 }),
      });
      const data = await response.json();
      if (response.ok) {
        onUploadSuccess(data);
      } else {
        setError(data.error || 'Report generation failed');
      }
    } catch (err) {
      setError('Report generation error: ' + err.message);
    }
  };

  return (
    <div className="mb-4">
      <input
        type="file"
        accept=".xlsx,.pdf"
        onChange={handleFileChange}
        className="mb-2 p-2 border rounded"
      />
      <button
        onClick={handleUpload}
        disabled={uploading || !file}
        className="bg-blue-500 text-white p-2 rounded mr-2 disabled:bg-gray-400"
      >
        {uploading ? 'Uploading...' : 'Upload File'}
      </button>
      <button
        onClick={handleGenerateReport}
        className="bg-green-500 text-white p-2 rounded"
      >
        Generate Report
      </button>
      {error && <p className="text-red-500 mt-2">{error}</p>}
    </div>
  );
}

export default FileUpload;