import { useParams, Link } from 'react-router-dom';
import { ChevronRight, Loader2, CheckCircle2, XCircle, AlertCircle, Clock, Wrench } from 'lucide-react';
import { api } from '../lib/api';
import { useApi } from '../hooks/useApi';

function StatusIcon({ status }) {
  switch (status) {
    case 'passed': return <CheckCircle2 className="w-4 h-4 text-green-400" />;
    case 'failed': return <XCircle className="w-4 h-4 text-red-400" />;
    case 'error': return <AlertCircle className="w-4 h-4 text-amber-400" />;
    default: return <Clock className="w-4 h-4 text-gray-500" />;
  }
}

export default function RunView() {
  const { id } = useParams();
  const { data: run, loading } = useApi(() => api.getRun(id), [id]);

  if (loading) {
    return <div className="flex items-center justify-center h-64"><Loader2 className="w-6 h-6 text-probe-500 animate-spin" /></div>;
  }

  if (!run) {
    return <div className="text-gray-500">Run not found</div>;
  }

  const passRate = run.results?.length > 0
    ? (run.results.filter(r => r.status === 'passed').length / run.results.length * 100).toFixed(0)
    : 0;

  return (
    <div className="max-w-5xl animate-fade-in">
      <div className="flex items-center gap-2 text-xs text-gray-500 mb-6">
        <Link to="/" className="hover:text-gray-300 transition-colors">Targets</Link>
        <ChevronRight className="w-3 h-3" />
        <span className="text-gray-400">Test run</span>
      </div>

      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Test run</h1>
          <p className="text-xs text-gray-500 font-mono mt-1">{run.id}</p>
        </div>
        <div className="flex items-center gap-4">
          <div className="text-right">
            <div className="text-2xl font-bold text-gray-100">{passRate}%</div>
            <div className="text-xs text-gray-500">pass rate</div>
          </div>
        </div>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-4 gap-3 mb-8">
        <div className="stat-card">
          <span className="text-xs text-gray-500 uppercase tracking-wider">Passed</span>
          <span className="text-xl font-semibold text-green-400">
            {run.results?.filter(r => r.status === 'passed').length || 0}
          </span>
        </div>
        <div className="stat-card">
          <span className="text-xs text-gray-500 uppercase tracking-wider">Failed</span>
          <span className="text-xl font-semibold text-red-400">
            {run.results?.filter(r => r.status === 'failed').length || 0}
          </span>
        </div>
        <div className="stat-card">
          <span className="text-xs text-gray-500 uppercase tracking-wider">Errors</span>
          <span className="text-xl font-semibold text-amber-400">
            {run.results?.filter(r => r.status === 'error').length || 0}
          </span>
        </div>
        <div className="stat-card">
          <span className="text-xs text-gray-500 uppercase tracking-wider">Cost</span>
          <span className="text-xl font-semibold text-gray-200">${run.total_cost_usd?.toFixed(4) || '0'}</span>
        </div>
      </div>

      {/* Individual results */}
      <div className="card p-5">
        <h2 className="text-sm font-medium text-gray-300 mb-4">
          Test results ({run.results?.length || 0})
        </h2>
        <div className="grid gap-2">
          {run.results?.map((result, i) => (
            <details key={result.id || i} className="group">
              <summary className="flex items-center gap-3 p-3 rounded-lg bg-surface-2/50 hover:bg-surface-3/50 cursor-pointer transition-colors list-none">
                <StatusIcon status={result.status} />
                <div className="flex-1 min-w-0">
                  <span className="text-sm text-gray-200 truncate block">
                    {result.response_text?.substring(0, 80) || result.error_message || 'No response'}
                    {result.response_text?.length > 80 ? '...' : ''}
                  </span>
                </div>
                <div className="flex items-center gap-3 text-xs text-gray-500 flex-shrink-0">
                  {result.tool_calls?.length > 0 && (
                    <span className="flex items-center gap-1">
                      <Wrench className="w-3 h-3" />
                      {result.tool_calls.length}
                    </span>
                  )}
                  <span>{Math.round(result.latency_ms || 0)}ms</span>
                  <span>{result.total_tokens || 0} tok</span>
                </div>
              </summary>
              <div className="mt-1 ml-7 p-3 rounded-lg bg-surface-0 border border-surface-3 text-xs space-y-3">
                {result.response_text && (
                  <div>
                    <span className="text-gray-500 uppercase tracking-wider text-[10px]">Response</span>
                    <p className="text-gray-300 mt-1 leading-relaxed whitespace-pre-wrap font-mono text-[11px]">{result.response_text}</p>
                  </div>
                )}
                {result.tool_calls?.length > 0 && (
                  <div>
                    <span className="text-gray-500 uppercase tracking-wider text-[10px]">Tool calls</span>
                    {result.tool_calls.map((tc, j) => (
                      <div key={j} className="mt-1 p-2 rounded bg-surface-2 font-mono text-[11px]">
                        <span className="text-probe-400">{tc.tool_name}</span>
                        <span className="text-gray-600">(</span>
                        <span className="text-amber-300">{JSON.stringify(tc.arguments)}</span>
                        <span className="text-gray-600">)</span>
                      </div>
                    ))}
                  </div>
                )}
                {result.error_message && (
                  <div>
                    <span className="text-gray-500 uppercase tracking-wider text-[10px]">Error</span>
                    <p className="text-red-400 mt-1 font-mono text-[11px]">{result.error_message}</p>
                  </div>
                )}
              </div>
            </details>
          ))}
        </div>
      </div>
    </div>
  );
}
