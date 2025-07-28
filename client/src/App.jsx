import React, { useState } from 'react';
import FileUpload from './components/FileUpload';
import ReportPreview from './components/ReportPreview';
import './App.css';

function App() {
  const [reportPath, setReportPath] = useState(null);

  const handleUploadSuccess = (response) => {
    setReportPath(response.reportPath);
  };

  return (
    <div className="container mx-auto p-4">
      <h1 className="text-3xl font-bold mb-4">Financial Data Analysis</h1>
      <FileUpload onUploadSuccess={handleUploadSuccess} />
      {reportPath && <ReportPreview reportPath={reportPath} />}
    </div>
  );
}

export default App;