import React, { useEffect, useState } from 'react';

const API = process.env.REACT_APP_API_URL || '';

export default function ReportPreview() {
  const [reports, setReports] = useState([]);

  useEffect(() => {
    async function load() {
      try {
        const res = await fetch(`${API}/api/reports`);
        if (!res.ok) return;
        setReports(await res.json());
      } catch {
        /* ignore — server may not be running yet */
      }
    }
    load();
  }, []);

  if (!reports.length) return null;

  return (
    <div>
      <h2 className="text-xl font-semibold mb-3">Recent Reports</h2>
      <ul className="list-disc pl-5 space-y-1">
        {reports.map(r => (
          <li key={r.id}>
            <a
              href={r.url}
              className="text-blue-600 hover:underline"
              target="_blank"
              rel="noopener noreferrer"
            >
              {r.filename}
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}
