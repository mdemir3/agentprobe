import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Target, Plus, Wrench, Trash2, Loader2, AlertCircle, ExternalLink } from 'lucide-react';
import { api } from '../lib/api';
import { useApi } from '../hooks/useApi';

export default function Home() {
  const { data: targets, loading, error, refetch } = useApi(() => api.listTargets());
  const [showAdd, setShowAdd] = useState(false);
  const [addForm, setAddForm] = useState({ url: '', name: '', connector_type: 'api' });
  const [adding, setAdding] = useState(false);
  const [addError, setAddError] = useState('');

  async function handleAdd(e) {
    e.preventDefault();
    setAdding(true);
    setAddError('');
    try {
      await api.registerTarget(addForm);
      setShowAdd(false);
      setAddForm({ url: '', name: '', connector_type: 'api' });
      refetch();
    } catch (err) {
      setAddError(err.message);
    } finally {
      setAdding(false);
    }
  }

  async function handleDelete(id) {
    if (!confirm('Delete this target agent?')) return;
    try {
      await api.deleteTarget(id);
      refetch();
    } catch (err) {
      alert(err.message);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-6 h-6 text-probe-500 animate-spin" />
      </div>
    );
  }

  return (
    <div className="max-w-5xl animate-fade-in">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Target agents</h1>
          <p className="text-sm text-gray-500 mt-1">
            Register AI agents, run quality probes, and track hallucination rates
          </p>
        </div>
        <button
          onClick={() => setShowAdd(!showAdd)}
          className="flex items-center gap-2 px-4 py-2 bg-probe-600 hover:bg-probe-500 text-white text-sm font-medium rounded-lg transition-colors"
        >
          <Plus className="w-4 h-4" />
          Add target
        </button>
      </div>

      {showAdd && (
        <form onSubmit={handleAdd} className="card p-5 mb-6 animate-slide-up">
          <h3 className="text-sm font-medium mb-4">Register a new target agent</h3>
          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className="block text-xs text-gray-500 mb-1.5">Agent URL</label>
              <input
                type="url"
                required
                placeholder="http://localhost:8001"
                value={addForm.url}
                onChange={(e) => setAddForm({ ...addForm, url: e.target.value })}
                className="w-full px-3 py-2 bg-surface-2 border border-surface-4 rounded-lg text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:ring-1 focus:ring-probe-600"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1.5">Name</label>
              <input
                type="text"
                placeholder="My Support Bot"
                value={addForm.name}
                onChange={(e) => setAddForm({ ...addForm, name: e.target.value })}
                className="w-full px-3 py-2 bg-surface-2 border border-surface-4 rounded-lg text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:ring-1 focus:ring-probe-600"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1.5">Type</label>
              <select
                value={addForm.connector_type}
                onChange={(e) => setAddForm({ ...addForm, connector_type: e.target.value })}
                className="w-full px-3 py-2 bg-surface-2 border border-surface-4 rounded-lg text-sm text-gray-200 focus:outline-none focus:ring-1 focus:ring-probe-600"
              >
                <option value="api">REST API</option>
                <option value="mcp">MCP</option>
              </select>
            </div>
          </div>
          {addError && (
            <div className="mt-3 flex items-center gap-2 text-sm text-red-400">
              <AlertCircle className="w-4 h-4" /> {addError}
            </div>
          )}
          <div className="flex gap-2 mt-4">
            <button
              type="submit"
              disabled={adding}
              className="px-4 py-2 bg-probe-600 hover:bg-probe-500 disabled:opacity-50 text-white text-sm rounded-lg transition-colors flex items-center gap-2"
            >
              {adding ? <Loader2 className="w-4 h-4 animate-spin" /> : <Target className="w-4 h-4" />}
              Connect &amp; discover
            </button>
            <button
              type="button"
              onClick={() => setShowAdd(false)}
              className="px-4 py-2 text-gray-400 hover:text-gray-200 text-sm rounded-lg transition-colors"
            >
              Cancel
            </button>
          </div>
        </form>
      )}

      {error && (
        <div className="card p-5 mb-6 border-red-500/30">
          <div className="flex items-center gap-2 text-red-400 text-sm">
            <AlertCircle className="w-4 h-4" />
            {error}. Make sure the AgentProbe API is running on port 8000.
          </div>
        </div>
      )}

      {targets && targets.length === 0 && !showAdd && (
        <div className="card p-12 text-center">
          <Target className="w-10 h-10 text-gray-600 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-300 mb-2">No target agents yet</h3>
          <p className="text-sm text-gray-500 mb-4">
            Register an AI agent to start testing it for hallucinations, tool accuracy, and safety
          </p>
          <button
            onClick={() => setShowAdd(true)}
            className="px-4 py-2 bg-probe-600 hover:bg-probe-500 text-white text-sm font-medium rounded-lg transition-colors"
          >
            Add your first target
          </button>
        </div>
      )}

      <div className="grid gap-3">
        {targets?.map((target, i) => (
          <Link
            key={target.id}
            to={`/targets/${target.id}`}
            className="card-hover p-5 flex items-center gap-4 animate-slide-up"
            style={{ animationDelay: `${i * 60}ms` }}
          >
            <div className="w-10 h-10 rounded-lg bg-probe-600/15 flex items-center justify-center flex-shrink-0">
              <Target className="w-5 h-5 text-probe-400" />
            </div>
            <div className="flex-1 min-w-0">
              <h3 className="text-sm font-medium text-gray-200 truncate">{target.name}</h3>
              <p className="text-xs text-gray-500 font-mono truncate mt-0.5">{target.url}</p>
            </div>
            <div className="flex items-center gap-4 text-xs text-gray-500">
              <div className="flex items-center gap-1.5">
                <Wrench className="w-3.5 h-3.5" />
                <span>{target.tools?.length || 0} tools</span>
              </div>
              <span className="badge bg-surface-3 text-gray-400">{target.connector_type}</span>
            </div>
            <button
              onClick={(e) => { e.preventDefault(); handleDelete(target.id); }}
              className="p-1.5 text-gray-600 hover:text-red-400 transition-colors rounded"
            >
              <Trash2 className="w-4 h-4" />
            </button>
          </Link>
        ))}
      </div>
    </div>
  );
}
