import React from 'react';
import { AppProvider } from './contexts/AppContext';
import FileUpload from './components/FileUpload';
import DemoRevenueSummary from './components/DemoRevenueSummary';
import ReportPreview from './components/ReportPreview';
import './App.css';

const App: React.FC = () => {
  return (
    <AppProvider>
      <div className="min-h-screen bg-gradient-to-br from-gray-50 to-blue-50">
        {/* Navigation Header */}
        <nav className="bg-white/80 backdrop-blur-sm border-b border-gray-200 sticky top-0 z-10">
          <div className="max-w-7xl mx-auto px-6 py-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center">
                <div className="w-10 h-10 bg-gradient-to-r from-blue-600 to-purple-600 rounded-xl flex items-center justify-center mr-4">
                  <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                  </svg>
                </div>
                <div>
                  <h1 className="text-2xl font-bold bg-gradient-to-r from-gray-900 to-gray-700 bg-clip-text text-transparent">
                    Financial Data Analysis
                  </h1>
                  <p className="text-sm text-gray-600">
                    AI-powered financial insights platform
                  </p>
                </div>
              </div>
              
              <div className="hidden md:flex items-center space-x-6 text-sm">
                <div className="flex items-center text-gray-600">
                  <div className="w-2 h-2 bg-emerald-500 rounded-full mr-2 animate-pulse" />
                  System Online
                </div>
              </div>
            </div>
          </div>
        </nav>

        {/* Main Content */}
        <main className="max-w-7xl mx-auto px-6 py-8">
          {/* Hero Section */}
          <div className="text-center mb-12">
            <h2 className="text-4xl font-bold text-gray-900 mb-4">
              Transform Your Financial Data
            </h2>
            <p className="text-xl text-gray-600 max-w-3xl mx-auto leading-relaxed">
              Upload Excel, PDF, or CSV files to automatically extract financial metrics, 
              calculate trends, and generate AI-powered analytical questions for deeper insights.
            </p>
          </div>

          {/* Feature Cards */}
          <div className="grid md:grid-cols-3 gap-6 mb-12">
            <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200 text-center">
              <div className="w-12 h-12 bg-blue-100 rounded-xl flex items-center justify-center mx-auto mb-4">
                <svg className="w-6 h-6 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                </svg>
              </div>
              <h3 className="font-semibold text-gray-800 mb-2">Smart Upload</h3>
              <p className="text-sm text-gray-600">Auto-detect and extract data from multiple file formats</p>
            </div>
            
            <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200 text-center">
              <div className="w-12 h-12 bg-emerald-100 rounded-xl flex items-center justify-center mx-auto mb-4">
                <svg className="w-6 h-6 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                </svg>
              </div>
              <h3 className="font-semibold text-gray-800 mb-2">AI Analytics</h3>
              <p className="text-sm text-gray-600">Calculate trends, variances, and financial ratios automatically</p>
            </div>
            
            <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200 text-center">
              <div className="w-12 h-12 bg-purple-100 rounded-xl flex items-center justify-center mx-auto mb-4">
                <svg className="w-6 h-6 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
              </div>
              <h3 className="font-semibold text-gray-800 mb-2">Smart Reports</h3>
              <p className="text-sm text-gray-600">Generate comprehensive PDF reports with insights</p>
            </div>
          </div>

          {/* Main Application Components */}
          <div className="space-y-12">
            <FileUpload />
            <DemoRevenueSummary />
            <ReportPreview />
          </div>
        </main>

        {/* Footer */}
        <footer className="mt-16 border-t border-gray-200 bg-white/50 backdrop-blur-sm">
          <div className="max-w-7xl mx-auto px-6 py-8">
            <div className="text-center text-sm text-gray-500">
              <p>Financial Data Analysis System - Powered by FastAPI & React</p>
              <div className="flex items-center justify-center mt-2 space-x-4">
                <span className="flex items-center">
                  <div className="w-2 h-2 bg-emerald-500 rounded-full mr-2" />
                  TypeScript
                </span>
                <span className="flex items-center">
                  <div className="w-2 h-2 bg-blue-500 rounded-full mr-2" />
                  Tailwind CSS
                </span>
                <span className="flex items-center">
                  <div className="w-2 h-2 bg-purple-500 rounded-full mr-2" />
                  FastAPI
                </span>
              </div>
            </div>
          </div>
        </footer>
      </div>
    </AppProvider>
  );
};

export default App;