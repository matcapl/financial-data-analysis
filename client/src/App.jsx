import React from 'react';
import { AppProvider } from './contexts/AppContext';
import FileUpload from './components/FileUpload';
import ReportPreview from './components/ReportPreview';
import './App.css';

function App() {
  return (
    <AppProvider>
      <div className="min-h-screen bg-gray-50 p-6">
        <header className="max-w-6xl mx-auto mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">
            Financial Data Analysis System
          </h1>
          <p className="text-gray-600">
            Upload financial data files and generate comprehensive analysis reports
          </p>
        </header>

        <main className="max-w-6xl mx-auto space-y-8">
          <FileUpload />
          <ReportPreview />
        </main>
      </div>
    </AppProvider>
  );
}

export default App;
