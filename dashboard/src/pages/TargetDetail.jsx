import { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { Wrench, Play, FileText, Loader2, AlertCircle, ChevronRight, Clock, Coins } from 'lucide-react';
import { api } from '../lib/api';
import { useApi } from '../hooks/useApi';

function StatusBadge({ status }) {
  const styles = {
    passed: 'badge-passed',
    failed: 'badge-failed',
    error: 'badge-error',
    running: 'bg-blue-500/15 text-blue-400',
    pending: 'bg-gray-500/15 text-gray-400',
  };
  return <span className={`badge ${styles[status] || styles.pending}`}>{status}</span>;
}

export default function TargetDetail() {
  const { id } = useParams();
  const { data: target, loading: loadingTarget } = useApi(() => api.getTarget(id), [id]);
  const { data: plans, loading: loadingPlans, refetch: refetchPlans } = useApi(() => api.listPlans(id), [id]);
  const { data: runs, loading: loadingRuns, refetch: refetchRuns } = useApi(() => api.listRuns(id), [id]);
  const { data: reports, refetch: refetchReports } = useApi(() => api.listReports(id), [id]);

  const [generating, setGenerating] = useState(false);
  const [running, setRunning] = useState(false);
  const [evaluating, setEvaluating] = useState(false);
  const [error, setError] = useState('');

  async function handleGeneratePlan() {
    setGenerating(true);
    setError('');
    try {
      await api.createPlan({ target_id: id, max_cases: 30 });
      refetchPlans();
    } catch (err) {
      setError(err.message);
    } finally {
      setGenerating(false);
    }
  }

  async function handleRunPlan(planId) {
    setRunning(true);
    setError('');
    try {
      const run = await api.startRun({ plan_id: planId });
      refetchRuns();
      // Auto-generate report
      setEvaluating(true);
      await api.generateReport(run.id);
      refetchReports();
    } catch (err) {
      setError(err.message);
    } finally {
      setRunning(false);
      setEvaluating(false);
    }
  }

  if (loadingTarget) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-6 h-6 text-probe-500 animate-spin" />
      </div>
    );
  }

  if (!target) {
    return <div className="text-gray-500">Target not found</div>;
  }

  // Find latest report for display
  const latestReport = reports?.sort((a, b) => new Date(b.created_at) - new Date(a.created_at))?.[0];

  return (
    <div className="max-w-5xl animate-fade-in">
      {/* Header */}
      <div className="flex items-start justify-between mb-8">
        <div>
          <div className="flex items-center gap-2 text-xs text-gray-500 mb-2">
            <Link to="/" className="hover:text-gray-300 transition-colors">Targets</Link>
            <ChevronRight className="w-3 h-3" />
            <span className="text-gray-400">{target.name}</span>
          </div>
          <h1 className="text-2xl font-semibold tracking-tight">{target.name}</h1>
          <p className="text-sm text-gray-500 font-mono mt-1">{target.url}</p>
        </div>
        {latestReport && (
          <Link to={`/reports/${latestReport.id}`} className="text-right">
            <div className={`grade-ring ${
              latestReport.overall_score >= 0.8 ? 'border-green-500 text-green-400' :
              latestReport.overall_score >= 0.6 ? 'border-amber-500 text-amber-400' :
              'border-red-500 text-red-400'
            }`}>
              {latestReport.grade}
            </div>
            <div className="text-xs text-gray-500 mt-1">{Math.round(latestReport.overall_score * 100)}%</div>
          </Link>
        )}
      </div>

      {error && (
        <div className="card p-4 mb-4 border-red-500/30 flex items-center gap-2 text-sm text-red-400">
          <AlertCircle className="w-4 h-4 flex-shrink-0" /> {error}
        </div>
      )}

      {/* Discovered Tools */}
      <div className="card p-5 mb-6">
        <h2 className="text-sm font-medium text-gray-300 mb-4 flex items-center gap-2">
          <Wrench className="w-4 h-4 text-probe-400" />
          Discovered tools ({target.tools?.length || 0})
        </h2>
        <div className="grid gap-2">
          {target.tools?.map((tool) => (
            <div key={tool.name} className="flex items-start gap-3 p-3 rounded-lg bg-surface-2/50">
              <div className="w-2 h-2 rounded-full bg-probe-500 mt-1.5 flex-shrink-0" />
              <div>
                <span className="text-sm font-mono text-gray-200">{tool.name}</span>
                <p className="text-xs text-gray-500 mt-0.5">{tool.description}</p>
                {tool.required_params?.length > 0 && (
                  <div className="flex gap-1.5 mt-1.5">
                    {tool.required_params.map((p) => (
                      <span key={p} className="text-[10px] px-1.5 py-0.5 bg-surface-3 text-gray-400 rounded font-mono">{p}</span>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}
          {(!target.tools || target.tools.length === 0) && (
            <p className="text-sm text-gray-600">No tools discovered</p>
          )}
        </div>
      </div>

      {/* Actions */}
      <div className="flex gap-3 mb-6">
        <button
          onClick={handleGeneratePlan}
          disabled={generating}
          className="flex items-center gap-2 px-4 py-2 bg-surface-2 hover:bg-surface-3 border border-surface-4 text-sm text-gray-300 rounded-lg transition-colors disabled:opacity-50"
        >
          {generating ? <Loader2 className="w-4 h-4 animate-spin" /> : <FileText className="w-4 h-4" />}
          Generate test plan
        </button>
      </div>

      {/* Test Plans */}
      {plans && plans.length > 0 && (
        <div className="card p-5 mb-6">
          <h2 className="text-sm font-medium text-gray-300 mb-4 flex items-center gap-2">
            <FileText className="w-4 h-4 text-blue-400" />
            Test plans ({plans.length})
          </h2>
          <div className="grid gap-2">
            {plans.map((plan) => (
              <div key={plan.id} className="flex items-center justify-between p-3 rounded-lg bg-surface-2/50">
                <div>
                  <span className="text-sm text-gray-200">{plan.name}</span>
                  <p className="text-xs text-gray-500 mt-0.5">{plan.test_cases?.length || 0} test cases</p>
                </div>
                <button
                  onClick={() => handleRunPlan(plan.id)}
                  disabled={running}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-probe-600 hover:bg-probe-500 text-white text-xs font-medium rounded-lg transition-colors disabled:opacity-50"
                >
                  {running ? <Loader2 className="w-3 h-3 animate-spin" /> : <Play className="w-3 h-3" />}
                  Run tests
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Test Runs */}
      {runs && runs.length > 0 && (
        <div className="card p-5 mb-6">
          <h2 className="text-sm font-medium text-gray-300 mb-4 flex items-center gap-2">
            <Play className="w-4 h-4 text-amber-400" />
            Test runs ({runs.length})
          </h2>
          <div className="grid gap-2">
            {runs.map((run) => (
              <Link
                key={run.id}
                to={`/runs/${run.id}`}
                className="flex items-center justify-between p-3 rounded-lg bg-surface-2/50 hover:bg-surface-3/50 transition-colors"
              >
                <div className="flex items-center gap-3">
                  <StatusBadge status={run.status} />
                  <div>
                    <span className="text-sm text-gray-300">
                      {run.passed || 0} passed / {run.failed || 0} failed / {run.error_count || 0} errors
                    </span>
                    <div className="flex items-center gap-3 text-xs text-gray-500 mt-0.5">
                      <span className="flex items-center gap-1"><Coins className="w-3 h-3" />${run.total_cost_usd?.toFixed(4) || '0.00'}</span>
                      <span className="flex items-center gap-1"><Clock className="w-3 h-3" />{run.completed_at ? new Date(run.completed_at).toLocaleString() : 'running'}</span>
                    </div>
                  </div>
                </div>
                <ChevronRight className="w-4 h-4 text-gray-600" />
              </Link>
            ))}
          </div>
        </div>
      )}

      {/* Reports */}
      {reports && reports.length > 0 && (
        <div className="card p-5">
          <h2 className="text-sm font-medium text-gray-300 mb-4">Quality reports</h2>
          <div className="grid gap-2">
            {reports.map((report) => (
              <Link
                key={report.id}
                to={`/reports/${report.id}`}
                className="flex items-center justify-between p-3 rounded-lg bg-surface-2/50 hover:bg-surface-3/50 transition-colors"
              >
                <div className="flex items-center gap-3">
                  <div className={`grade-ring w-10 h-10 text-base ${
                    report.overall_score >= 0.8 ? 'border-green-500 text-green-400' :
                    report.overall_score >= 0.6 ? 'border-amber-500 text-amber-400' :
                    'border-red-500 text-red-400'
                  }`}>
                    {report.grade}
                  </div>
                  <div>
                    <span className="text-sm text-gray-300">{Math.round(report.overall_score * 100)}% overall</span>
                    <div className="text-xs text-gray-500">Hallucination: {Math.round(report.hallucination_rate * 100)}%</div>
                  </div>
                </div>
                <ChevronRight className="w-4 h-4 text-gray-600" />
              </Link>
            ))}
          </div>
        </div>
      )}

      {evaluating && (
        <div className="card p-5 mt-4 flex items-center gap-3 text-sm text-gray-400">
          <Loader2 className="w-4 h-4 animate-spin text-probe-500" />
          Evaluating results and generating quality report...
        </div>
      )}
    </div>
  );
}
