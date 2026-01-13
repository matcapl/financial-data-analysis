import React, { useEffect } from 'react';
import { useApp } from '../contexts/AppContext';

const fmtPct = (value: number | null | undefined): string => {
  if (value === null || value === undefined) return '—';
  const sign = value > 0 ? '+' : '';
  return `${sign}${value.toFixed(1)}%`;
};

const fmtNumber = (value: number | null | undefined): string => {
  if (value === null || value === undefined) return '—';
  return value.toLocaleString(undefined, { maximumFractionDigits: 0 });
};

export const DemoRevenueSummary: React.FC = () => {
  const { companyId, demoSummary, refreshDemoSummary, loading } = useApp();

  useEffect(() => {
    // Best-effort: when company changes, refresh the demo view.
    // Avoid spamming if no companyId.
    if (companyId && parseInt(companyId) > 0) {
      void refreshDemoSummary();
    }
  }, [companyId, refreshDemoSummary]);

  if (!demoSummary) {
    return (
      <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-semibold text-gray-900">Demo Output</h3>
            <p className="text-sm text-gray-600">Revenue summary and generated questions</p>
          </div>
          <button
            onClick={() => void refreshDemoSummary()}
            className="px-4 py-2 rounded-lg bg-gray-900 text-white text-sm hover:bg-gray-800 disabled:opacity-50"
            disabled={loading.upload}
          >
            Refresh
          </button>
        </div>
        <div className="mt-4 text-sm text-gray-600">
          Upload a file to generate demo output, then refresh.
        </div>
      </div>
    );
  }

  const { revenue, questions } = demoSummary;

  return (
    <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold text-gray-900">Demo Output</h3>
          <p className="text-sm text-gray-600">Company {demoSummary.company_id}</p>
        </div>
        <button
          onClick={() => void refreshDemoSummary()}
          className="px-4 py-2 rounded-lg bg-gray-900 text-white text-sm hover:bg-gray-800 disabled:opacity-50"
          disabled={loading.upload}
        >
          Refresh
        </button>
      </div>

      <div className="mt-6 grid md:grid-cols-4 gap-4">
        <div className="rounded-xl border border-gray-200 p-4">
          <div className="text-xs uppercase tracking-wide text-gray-500">Period</div>
          <div className="mt-1 text-lg font-semibold text-gray-900">{revenue.period_label}</div>
        </div>
        <div className="rounded-xl border border-gray-200 p-4">
          <div className="text-xs uppercase tracking-wide text-gray-500">Revenue</div>
          <div className="mt-1 text-lg font-semibold text-gray-900">
            {revenue.currency ? `${revenue.currency} ` : ''}{fmtNumber(revenue.value)}
          </div>
        </div>
        <div className="rounded-xl border border-gray-200 p-4">
          <div className="text-xs uppercase tracking-wide text-gray-500">MoM</div>
          <div className="mt-1 text-lg font-semibold text-gray-900">{fmtPct(revenue.mom_change_pct)}</div>
        </div>
        <div className="rounded-xl border border-gray-200 p-4">
          <div className="text-xs uppercase tracking-wide text-gray-500">YoY</div>
          <div className="mt-1 text-lg font-semibold text-gray-900">{fmtPct(revenue.yoy_change_pct)}</div>
        </div>
      </div>

      <div className="mt-4 text-sm text-gray-600">
        vs Budget: <span className="font-medium text-gray-900">{fmtPct(revenue.vs_budget_pct)}</span>
        {revenue.sources?.[0]?.source_file ? (
          <span className="ml-3">
            Source: <span className="font-mono text-xs">{revenue.sources[0].source_file}</span>
            {revenue.sources[0].source_page ? ` p.${revenue.sources[0].source_page}` : ''}
          </span>
        ) : null}
      </div>

      <div className="mt-6">
        <div className="flex items-center justify-between">
          <h4 className="text-md font-semibold text-gray-900">Questions / Challenges</h4>
          <div className="text-xs text-gray-500">Top {questions.length}</div>
        </div>

        <div className="mt-3 space-y-3">
          {questions.length === 0 ? (
            <div className="text-sm text-gray-600">No questions generated yet (check `config/questions.yaml`).</div>
          ) : (
            questions.map((q, idx) => (
              <div key={idx} className="rounded-xl border border-gray-200 p-4">
                <div className="flex items-center justify-between">
                  <div className="text-xs text-gray-500">
                    {q.category || 'general'} · priority {q.priority ?? '—'}
                  </div>
                  <div className="text-xs text-gray-400">{q.created_at ? new Date(q.created_at).toLocaleString() : ''}</div>
                </div>
                <div className="mt-2 text-sm text-gray-900">{q.text}</div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
};

export default DemoRevenueSummary;
