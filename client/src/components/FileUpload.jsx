import React, { useState } from 'react';
import PropTypes from 'prop-types';
import sanitize from 'sanitize-filename';

const API = process.env.REACT_APP_API_URL || '';

export default function FileUpload() {
  const [file, setFile] = useState(null);
  const [companyId, setCompanyId] = useState('');
  const [status, setStatus] = useState('');

  const handleSubmit = async e => {
    e.preventDefault();
    if (!file || !companyId) {
      setStatus('Please choose a file and company id');
      return;
    }

    const data = new FormData();
    data.append('file', file, sanitize(file.name));
    data.append('company_id', companyId);

    try {
      setStatus('Uploading …');
      const res = await fetch(`${API}/api/upload`, {
        method: 'POST',
        body: data
      });

      if (!res.ok) throw new Error(await res.text());
      setStatus('Upload & processing completed ✅');
    } catch (err) {
      setStatus(`Error: ${err.message}`);
    }
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="flex flex-col gap-4 bg-white p-4 rounded shadow w-80"
    >
      <input
        type="file"
        accept=".pdf,.xlsx,.xls,.csv"
        onChange={e => setFile(e.target.files[0])}
      />
      <input
        type="number"
        placeholder="Company ID"
        value={companyId}
        onChange={e => setCompanyId(e.target.value)}
        className="border p-2 rounded"
      />
      <button
        type="submit"
        className="bg-blue-600 text-white p-2 rounded hover:bg-blue-700"
      >
        Upload
      </button>
      {status && <p className="text-sm text-gray-700">{status}</p>}
    </form>
  );
}

FileUpload.propTypes = {
  apiBase: PropTypes.string
};
