import { useParams, Link } from 'react-router-dom';
import { ChevronRight, Loader2, AlertTriangle, CheckCircle2, XCircle, HelpCircle, ArrowDown } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, PieChart, Pie, Cell, ResponsiveContainer } from 'recharts';
import { api } from '../lib/api';
import { useApi } from '../hooks/useApi';

const VERDICT_COLORS = { supported: '#22c55e', refuted: '#ef4444', not_found: '#f59e0b', needs_review: '#8b5cf6' };
const VERDICT_ICONS = { supported: CheckCircle2, refuted: XCircle, not_found: HelpCircle, needs_review: AlertTriangle };

function GradeRing({ score, grade, size = 'lg' }) {
  const pct = Math.round(score * 100);
  const circumference = 2 * Math.PI * 42;
  const offset = circumference - (score * circumference);
  const color = score >= 0.8 ? '#22c55e' : score >= 0.6 ? '#f59e0b' : '#ef4444';

  return (
    <div className="relative flex items-center justify-center">
      <svg width={size === 'lg' ? 108 : 72} height={size === 'lg' ? 108 : 72} className="-rotate-90">
        <circle cx="50%" cy="50%" r="42" fill="none" stroke="#1a222d" strokeWidth="6" />
        <circle
          cx="50%" cy="50%" r="42" fill="none" stroke={color} strokeWidth="6"
          strokeDasharray={circumference} strokeDashoffset={offset}
          strokeLinecap="round" className="transition-all duration-1000"
        />
      </svg>
      <div className="absolute flex flex-col items-center">
        <span className={`font-bold ${size === 'lg' ? 'text-2xl' : 'text-lg'}`} style={{ color }}>{grade}</span>
        <span className="text-[10px] text-gray-500">{pct}%</span>
      </div>
    </div>
  );
}

function StatCard({ label, value, sub, color }) {
  return (
    <div className="stat-card">
      <span className="text-xs text-gray-500 uppercase tracking-wider">{label}</span>
      <span className={`text-xl font-semibold ${color || 'text-gray-100'}`}>{value}</span>
      {sub && <span className="text-xs text-gray-600">{sub}</span>}
    </div>
  );
}

export default function QualityReport() {
  const { id } = useParams();
  const { data: report, loading, error } = useApi(() => api.getReport(id), [id]);

  if (loading) {
    return <div className="flex items-center justify-center h-64"><Loader2 className="w-6 h-6 text-probe-500 animate-spin" /></div>;
  }

  if (error || !report) {
    return <div className="text-gray-500">Report not found</div>;
  }

  // Category breakdown chart data
  const categoryData = Object.entries(report.scores_by_category || {}).map(([cat, score]) => ({
    name: cat.replace(/_/g, ' '),
    score: Math.round(score * 100),
    fill: score >= 0.8 ? '#22c55e' : score >= 0.6 ? '#f59e0b' : '#ef4444',
  }));

  // Verdict pie data
  const verdictCounts = {};
  report.test_case_evals?.forEach((e) => {
    e.scores?.forEach((s) => {
      if (s.metric_name === 'hallucination_check' && s.details?.judgements) {
        s.details.judgements.forEach((j) => {
          verdictCounts[j.verdict] = (verdictCounts[j.verdict] || 0) + 1;
        });
      }
    });
  });
  const verdictData = Object.entries(verdictCounts).map(([v, count]) => ({
    name: v.replace(/_/g, ' '),
    value: count,
    color: VERDICT_COLORS[v] || '#8b5cf6',
  }));

  // Collect all hallucination judgements for drilldown
  const allJudgements = [];
  report.test_case_evals?.forEach((e) => {
    e.scores?.forEach((s) => {
      if (s.metric_name === 'hallucination_check' && s.details?.judgements) {
        s.details.judgements.forEach((j) => allJudgements.push(j));
      }
    });
  });

  return (
    <div className="max-w-5xl animate-fade-in">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-xs text-gray-500 mb-6">
        <Link to="/" className="hover:text-gray-300 transition-colors">Targets</Link>
        <ChevronRight className="w-3 h-3" />
        <span className="text-gray-400">Quality report</span>
      </div>

      {/* Header with grade */}
      <div className="flex items-center gap-6 mb-8">
        <GradeRing score={report.overall_score} grade={report.grade} />
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Quality report</h1>
          <p className="text-sm text-gray-500 mt-1">{report.target_name}</p>
          <p className="text-xs text-gray-600 mt-0.5 font-mono">
            {report.total_tests} tests &middot; {new Date(report.created_at).toLocaleString()}
          </p>
        </div>
      </div>

      {/* Top stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <StatCard
          label="Hallucination rate"
          value={`${Math.round(report.hallucination_rate * 100)}%`}
          color={report.hallucination_rate <= 0.1 ? 'text-green-400' : report.hallucination_rate <= 0.3 ? 'text-amber-400' : 'text-red-400'}
          sub={report.hallucination_rate === 0 ? 'Zero hallucinations' : `${report.total_tests} tests checked`}
        />
        <StatCard
          label="Tool accuracy"
          value={`${Math.round(report.tool_accuracy * 100)}%`}
          color={report.tool_accuracy >= 0.8 ? 'text-green-400' : 'text-amber-400'}
        />
        <StatCard
          label="Safety pass"
          value={`${Math.round(report.safety_pass_rate * 100)}%`}
          color={report.safety_pass_rate >= 0.9 ? 'text-green-400' : 'text-red-400'}
        />
        <StatCard
          label="Avg latency"
          value={`${Math.round(report.avg_latency_ms)}ms`}
          sub={`P95: ${Math.round(report.p95_latency_ms)}ms`}
        />
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8">
        <StatCard label="Tests passed" value={report.passed_tests} color="text-green-400" />
        <StatCard label="Tests failed" value={report.failed_tests} color={report.failed_tests > 0 ? 'text-red-400' : 'text-gray-400'} />
        <StatCard label="Total cost" value={`$${report.total_cost_usd?.toFixed(4) || '0'}`} />
        <StatCard label="Total tokens" value={report.total_tokens?.toLocaleString() || '0'} />
      </div>

      {/* Category breakdown chart */}
      {categoryData.length > 0 && (
        <div className="card p-5 mb-6">
          <h2 className="text-sm font-medium text-gray-300 mb-4">Score by category</h2>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={categoryData} layout="vertical" margin={{ left: 80 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#232d3a" horizontal={false} />
              <XAxis type="number" domain={[0, 100]} tick={{ fill: '#6b7280', fontSize: 11 }} axisLine={false} />
              <YAxis type="category" dataKey="name" tick={{ fill: '#9ca3af', fontSize: 12 }} axisLine={false} width={80} />
              <Tooltip
                contentStyle={{ background: '#1a222d', border: '1px solid #2d3848', borderRadius: '8px', fontSize: '12px' }}
                labelStyle={{ color: '#9ca3af' }}
                formatter={(v) => [`${v}%`, 'Score']}
              />
              <Bar dataKey="score" radius={[0, 4, 4, 0]} barSize={18}>
                {categoryData.map((entry, i) => <Cell key={i} fill={entry.fill} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Hallucination verdict breakdown */}
      {verdictData.length > 0 && (
        <div className="card p-5 mb-6">
          <h2 className="text-sm font-medium text-gray-300 mb-4">Hallucination verdicts</h2>
          <div className="flex items-center gap-8">
            <ResponsiveContainer width={160} height={160}>
              <PieChart>
                <Pie data={verdictData} dataKey="value" cx="50%" cy="50%" innerRadius={40} outerRadius={65} paddingAngle={3}>
                  {verdictData.map((entry, i) => <Cell key={i} fill={entry.color} />)}
                </Pie>
              </PieChart>
            </ResponsiveContainer>
            <div className="flex flex-col gap-2">
              {verdictData.map((v) => (
                <div key={v.name} className="flex items-center gap-2.5 text-sm">
                  <div className="w-3 h-3 rounded-sm" style={{ background: v.color }} />
                  <span className="text-gray-400 capitalize">{v.name}</span>
                  <span className="text-gray-200 font-medium">{v.value}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Hallucination drilldown — per-claim verdicts */}
      {allJudgements.length > 0 && (
        <div className="card p-5 mb-6">
          <h2 className="text-sm font-medium text-gray-300 mb-4 flex items-center gap-2">
            <ArrowDown className="w-4 h-4 text-amber-400" />
            Claim-by-claim analysis ({allJudgements.length} claims)
          </h2>
          <div className="grid gap-2">
            {allJudgements.map((j, i) => {
              const Icon = VERDICT_ICONS[j.verdict] || HelpCircle;
              const color = VERDICT_COLORS[j.verdict] || '#8b5cf6';
              return (
                <div key={i} className="p-3 rounded-lg bg-surface-2/50 border-l-2" style={{ borderColor: color }}>
                  <div className="flex items-start gap-2.5">
                    <Icon className="w-4 h-4 mt-0.5 flex-shrink-0" style={{ color }} />
                    <div className="min-w-0">
                      <p className="text-sm text-gray-200 leading-relaxed">"{j.claim}"</p>
                      <p className="text-xs text-gray-500 mt-1">{j.reasoning}</p>
                      <span className="badge mt-1.5 text-[10px]" style={{ background: `${color}15`, color }}>{j.verdict.replace(/_/g, ' ')}</span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Recommendations */}
      {report.recommendations?.length > 0 && (
        <div className="card p-5">
          <h2 className="text-sm font-medium text-gray-300 mb-4">Recommendations</h2>
          <div className="grid gap-2">
            {report.recommendations.map((rec, i) => (
              <div key={i} className="flex items-start gap-2.5 p-3 rounded-lg bg-surface-2/30">
                <span className="text-probe-400 text-xs font-mono mt-0.5">{i + 1}.</span>
                <p className="text-sm text-gray-400 leading-relaxed">{rec}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
