import React from 'react';
import FileUpload from './components/FileUpload';
import ReportPreview from './components/ReportPreview';
import './App.css';

function App() {
  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <h1 className="text-2xl font-bold text-gray-800 mb-6">
        Financial-Data Analysis
      </h1>

      <FileUpload />

      <div className="mt-10">
        <ReportPreview />
      </div>
    </div>
  );
}

export default App;
