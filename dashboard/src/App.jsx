import { BrowserRouter, Routes, Route, NavLink, Navigate } from 'react-router-dom';
import { Shield, Target, FileText, Play, BarChart3, Zap } from 'lucide-react';
import Home from './pages/Home';
import TargetDetail from './pages/TargetDetail';
import QualityReport from './pages/QualityReport';
import RunView from './pages/RunView';

const navItems = [
  { path: '/', icon: Target, label: 'Targets' },
];

function Sidebar() {
  return (
    <aside className="w-56 h-screen fixed left-0 top-0 bg-surface-1 border-r border-surface-3 flex flex-col z-50">
      <div className="p-5 border-b border-surface-3">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-probe-600 flex items-center justify-center">
            <Shield className="w-4 h-4 text-white" />
          </div>
          <div>
            <h1 className="text-sm font-semibold text-gray-100 tracking-tight">AgentProbe</h1>
            <p className="text-[10px] text-gray-500 font-mono">v0.1.0</p>
          </div>
        </div>
      </div>

      <nav className="flex-1 p-3">
        {navItems.map(({ path, icon: Icon, label }) => (
          <NavLink
            key={path}
            to={path}
            end
            className={({ isActive }) =>
              `flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-colors ${
                isActive
                  ? 'bg-probe-600/15 text-probe-400 font-medium'
                  : 'text-gray-400 hover:text-gray-200 hover:bg-surface-2'
              }`
            }
          >
            <Icon className="w-4 h-4" />
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="p-4 border-t border-surface-3">
        <div className="flex items-center gap-2 text-[11px] text-gray-600">
          <Zap className="w-3 h-3" />
          <span>AI Agent QA Platform</span>
        </div>
      </div>
    </aside>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <div className="flex min-h-screen">
        <Sidebar />
        <main className="flex-1 ml-56 p-8 min-h-screen">
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/targets/:id" element={<TargetDetail />} />
            <Route path="/runs/:id" element={<RunView />} />
            <Route path="/reports/:id" element={<QualityReport />} />
            <Route path="*" element={<Navigate to="/" />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
