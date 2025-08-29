import React from 'react';
import { useApp } from '../contexts/AppContext';
import LoadingSpinner from './LoadingSpinner';

const ReportPreview = () => {
  const { reports, refreshReports } = useApp();

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const formatFileSize = (bytes) => {
    if (bytes === 0) return 'Unknown size';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  if (!reports || reports.length === 0) {
    return (
      <div className="bg-white shadow-lg rounded-lg p-6">
        <div className="text-center py-8">
          <div className="text-gray-400 text-6xl mb-4">📊</div>
          <h2 className="text-xl font-semibold text-gray-600 mb-2">No Reports Yet</h2>
          <p className="text-gray-500 mb-4">
            Upload financial data and generate reports to see them here
          </p>
          <button
            onClick={refreshReports}
            className="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 transition-colors"
          >
            Refresh Reports
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white shadow-lg rounded-lg p-6">
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-2xl font-bold text-gray-800">Generated Reports</h2>
        <button
          onClick={refreshReports}
          className="bg-gray-100 text-gray-700 px-3 py-1 rounded-md hover:bg-gray-200 transition-colors text-sm"
        >
          🔄 Refresh
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {reports.map((report) => (
          <div key={report.id} className="border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow">
            <div className="flex items-start justify-between mb-2">
              <div className="flex-1">
                <h3 className="font-medium text-gray-900 truncate" title={report.filename}>
                  {report.filename}
                </h3>
                <p className="text-xs text-gray-500 mt-1">
                  Created: {formatDate(report.created)}
                </p>
                {report.size > 0 && (
                  <p className="text-xs text-gray-500">
                    Size: {formatFileSize(report.size)}
                  </p>
                )}
              </div>
              <div className="text-green-500 text-xl ml-2">📄</div>
            </div>
            
            <div className="mt-3">
              <a
                href={report.url}
                target="_blank"
                rel="noopener noreferrer"
                className="w-full bg-blue-600 text-white py-2 px-3 rounded-md hover:bg-blue-700 transition-colors text-sm font-medium text-center block"
              >
                📥 Download PDF
              </a>
            </div>
          </div>
        ))}
      </div>

      {reports.length > 0 && (
        <div className="mt-6 p-3 bg-blue-50 border border-blue-200 rounded-lg">
          <p className="text-sm text-blue-700">
            💡 <strong>Tip:</strong> Reports include financial metrics, trend analysis, and automatically generated questions for deeper insights.
          </p>
        </div>
      )}
    </div>
  );
};

export default ReportPreview;
