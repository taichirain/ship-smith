'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { AlertTriangle, ArrowLeft, ArrowRight, GitBranch, RefreshCw } from 'lucide-react';
import AppLayout from '@/components/AppLayout';
import StatusBadge from '@/components/StatusBadge';
import { api, Alert, AlertListResponse, AlertStatus, DashboardSummaryResponse } from '@/lib/api';

const PAGE_SIZE = 20;
const sections = [
  { key: 'attention', label: 'Needs Attention', icon: AlertTriangle },
  { key: 'changes', label: 'Recent Changes', icon: GitBranch },
  { key: 'alerts', label: 'Recent Alerts', icon: AlertTriangle },
] as const;
type Section = typeof sections[number]['key'];

function dateTime(value: string | null): string {
  return value ? new Date(value).toLocaleString() : 'N/A';
}

export default function ActivityPage() {
  const { section: rawSection } = useParams<{ section: string }>();
  const section = sections.some(item => item.key === rawSection) ? rawSection as Section : null;
  const [summary, setSummary] = useState<DashboardSummaryResponse | null>(null);
  const [alerts, setAlerts] = useState<AlertListResponse | null>(null);
  const [status, setStatus] = useState<AlertStatus | 'all'>('open');
  const [page, setPage] = useState(0);
  const [loading, setLoading] = useState(true);
  const [busyAlertId, setBusyAlertId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!section) return;
    setLoading(true);
    try {
      if (section === 'alerts') {
        setAlerts(await api.listAlerts({
          status: status === 'all' ? undefined : [status],
          limit: PAGE_SIZE,
          offset: page * PAGE_SIZE,
        }));
      } else {
        setSummary(await api.getDashboardSummary());
      }
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load activity');
    } finally {
      setLoading(false);
    }
  }, [section, status, page]);

  useEffect(() => { void load(); }, [load]);

  const updateAlert = async (alert: Alert, action: 'acknowledge' | 'resolve') => {
    setBusyAlertId(alert.id);
    try {
      if (action === 'acknowledge') await api.acknowledgeAlert(alert.id);
      else await api.resolveAlert(alert.id);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update alert');
    } finally {
      setBusyAlertId(null);
    }
  };

  if (!section) return <AppLayout><div className="p-8"><h1 className="text-xl font-semibold">Section not found</h1><Link href="/" className="text-primary-700">Back to dashboard</Link></div></AppLayout>;

  return <AppLayout><div className="mx-auto max-w-5xl p-5 md:p-8">
    <Link href="/" className="mb-5 inline-flex items-center gap-2 text-sm text-gray-600 hover:text-primary-700"><ArrowLeft className="h-4 w-4" />Dashboard</Link>
    <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
      <div><h1 className="text-2xl font-bold text-gray-900">{sections.find(item => item.key === section)?.label}</h1>
        <p className="mt-1 text-sm text-gray-500">{section === 'changes' ? 'Latest 30 changes across projects' : section === 'alerts' ? 'Review and manage project alerts' : 'Projects currently requiring attention'}</p>
      </div>
      <button className="btn btn-secondary gap-2" disabled={loading} onClick={load}><RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />Refresh</button>
    </div>
    <div className="mb-5 flex flex-wrap gap-2 border-b border-gray-200 pb-3">
      {sections.map(item => <Link key={item.key} href={`/activity/${item.key}`} className={`inline-flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium ${section === item.key ? 'bg-primary-100 text-primary-700' : 'text-gray-600 hover:bg-gray-100'}`}><item.icon className="h-4 w-4" />{item.label}</Link>)}
    </div>
    {error && <div className="mb-4 rounded-md bg-red-50 p-3 text-sm text-red-700">{error}</div>}
    {loading ? <div className="card p-8 text-sm text-gray-500">Loading...</div> : section === 'attention' ? <div className="space-y-3">
      {!summary?.anomaly_projects.length && <div className="card p-8 text-center text-sm text-gray-500">No projects need attention.</div>}
      {summary?.anomaly_projects.map(project => <Link key={project.project_id} href={`/projects/${project.project_id}`} className="card block p-4 hover:border-primary-300 hover:bg-gray-50">
        <div className="flex flex-wrap items-center gap-2"><span className="font-semibold text-gray-900">{project.project_name}</span>{project.health_status && <StatusBadge status={project.health_status} small />}</div>
        <p className="mt-2 text-sm text-gray-600">{project.anomaly_types.map(type => type.replaceAll('_', ' ')).join(' · ')}</p>
        <p className="mt-2 text-xs text-gray-500">Last agent heartbeat: {dateTime(project.agent_last_seen_at)}</p>
      </Link>)}
    </div> : section === 'changes' ? <div className="card divide-y divide-gray-100">
      {!summary?.recent_changes.length && <p className="p-8 text-center text-sm text-gray-500">No recent changes.</p>}
      {summary?.recent_changes.map((change, index) => <Link key={`${change.event_type}-${change.occurred_at}-${index}`} href={change.deployment_id ? `/deployments/${change.deployment_id}` : `/projects/${change.project_id}`} className="flex items-center gap-3 p-4 hover:bg-gray-50">
        <div className="min-w-0 flex-1"><p className="font-medium text-gray-900">{change.title}</p><p className="mt-1 text-sm text-gray-600">{change.project_name} · {change.event_category.replaceAll('_', ' ')}</p>{change.summary && <p className="mt-1 text-xs text-gray-500">{change.summary}</p>}</div>
        <span className="shrink-0 text-xs text-gray-500">{dateTime(change.occurred_at)}</span><ArrowRight className="h-4 w-4 shrink-0 text-gray-400" />
      </Link>)}
    </div> : <div>
      <div className="mb-4 flex flex-wrap gap-2">{(['open', 'acknowledged', 'resolved', 'all'] as const).map(value =>
        <button key={value} className={`rounded-md px-3 py-1.5 text-sm capitalize ${status === value ? 'bg-primary-100 font-medium text-primary-700' : 'bg-white text-gray-600 hover:bg-gray-100'}`} aria-pressed={status === value} onClick={() => { setStatus(value); setPage(0); }}>{value}</button>
      )}</div>
      <div className="space-y-3">
        {!alerts?.alerts.length && <div className="card p-8 text-center text-sm text-gray-500">No alerts in this view.</div>}
        {alerts?.alerts.map(alert => <div key={alert.id} className="card p-4">
          <div className="flex flex-wrap items-start justify-between gap-3"><div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2"><span className="font-medium text-gray-900">{alert.title}</span><span className="rounded bg-gray-100 px-2 py-0.5 text-xs capitalize text-gray-600">{alert.status}</span></div>
            <Link href={`/projects/${alert.project_id}`} className="mt-1 inline-block text-sm text-primary-700 hover:underline">{alert.project_name || `Project #${alert.project_id}`}</Link>
            <p className="mt-1 text-xs text-gray-500">Last seen: {dateTime(alert.last_seen_at)}</p>
            {alert.message && <p className="mt-2 whitespace-pre-line text-sm text-gray-600">{alert.message}</p>}
          </div><div className="flex gap-2">
            {alert.status === 'open' && <button className="btn btn-secondary text-xs" disabled={busyAlertId !== null} onClick={() => void updateAlert(alert, 'acknowledge')}>Acknowledge</button>}
            {alert.status !== 'resolved' && <button className="btn btn-secondary text-xs" disabled={busyAlertId !== null} onClick={() => void updateAlert(alert, 'resolve')}>Resolve</button>}
          </div></div>
        </div>)}
      </div>
      <div className="mt-4 flex items-center justify-between text-sm text-gray-500"><span>{alerts ? `${page * PAGE_SIZE + (alerts.alerts.length ? 1 : 0)}–${page * PAGE_SIZE + alerts.alerts.length} of ${alerts.total}` : ''}</span><div className="flex gap-2">
        <button className="btn btn-secondary" disabled={page === 0 || loading} onClick={() => setPage(page - 1)}>Previous</button>
        <button className="btn btn-secondary" disabled={!alerts || (page + 1) * PAGE_SIZE >= alerts.total || loading} onClick={() => setPage(page + 1)}>Next</button>
      </div></div>
    </div>}
  </div></AppLayout>;
}
