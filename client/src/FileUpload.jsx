import React, { useState } from 'react';

    const FileUpload = () => {
      const [file, setFile] = useState(null);
      const [fileType, setFileType] = useState('csv');
      const [companyId, setCompanyId] = useState('1');
      const [message, setMessage] = useState('');
      const [error, setError] = useState('');

      const handleFileChange = (e) => {
        setFile(e.target.files[0]);
      };

      const handleUpload = async (e) => {
        e.preventDefault();
        if (!file) {
          setError('Please select a file');
          return;
        }

        try {
          const reader = new FileReader();
          reader.readAsDataURL(file);
          reader.onload = async () => {
            const base64File = reader.result.split(',')[1];
            const response = await fetch('http://localhost:3001/api/upload', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                file: base64File,
                fileType: fileType,
                companyId: companyId,
              }),
            });
            if (!response.ok) {
              throw new Error(await response.text());
            }
            const data = await response.json();
            setMessage(data.message);
            setError('');
            console.log('Upload success:', data);
          };
          reader.onerror = () => {
            setError('Failed to read file');
          };
        } catch (err) {
          setError('Upload error: ' + err.message);
          setMessage('');
          console.error('Upload error:', err);
        }
      };

      const handleGenerateReport = async () => {
        try {
          const response = await fetch('http://localhost:3001/api/generate-report', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ companyId: companyId }),
          });
          if (!response.ok) {
            throw new Error(await response.text());
          }
          const data = await response.json();
          setMessage('Report generated: ' + data.reportUrl);
          setError('');
          console.log('Report success:', data);
        } catch (err) {
          setError('Report generation error: ' + err.message);
          setMessage('');
          console.error('Report error:', err);
        }
      };

      return (
        <div>
          <h2>File Upload</h2>
          <form onSubmit={handleUpload}>
            <input type="file" onChange={handleFileChange} accept=".csv,.pdf" />
            <select value={fileType} onChange={(e) => setFileType(e.target.value)}>
              <option value="csv">CSV</option>
              <option value="pdf">PDF</option>
            </select>
            <input
              type="text"
              value={companyId}
              onChange={(e) => setCompanyId(e.target.value)}
              placeholder="Company ID"
            />
            <button type="submit">Upload File</button>
          </form>
          <button onClick={handleGenerateReport}>Generate Report</button>
          {message && <p style={{ color: 'green' }}>{message}</p>}
          {error && <p style={{ color: 'red' }}>{error}</p>}
        </div>
      );
    };

    export default FileUpload;