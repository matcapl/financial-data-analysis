import React from 'react';

function ReportPreview({ reportPath }) {
  return (
    <div className="mt-4">
      <h2 className="text-2xl font-bold mb-2">Report Generated</h2>
      <p>Download your report: <a href={reportPath} download className="text-blue-500 underline">Financial Report</a></p>
      <iframe src={reportPath} width="100%" height="500px" className="mt-2 border" />
    </div>
  );
}

export default ReportPreview;