'use client';

import { useCallback, useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import Link from 'next/link';
import { AlertTriangle, ArrowRight, CheckCircle, GitBranch, Package, Power, RefreshCw, Server, Sparkles, XCircle } from 'lucide-react';
import AppLayout from '@/components/AppLayout';
import LoginForm from '@/components/LoginForm';
import StatusBadge from '@/components/StatusBadge';
import { api, getToken, AUTH_EXPIRED_EVENT, DashboardSummaryResponse, AlertListResponse, Project } from '@/lib/api';
import { parseApiTimestamp } from '@/lib/datetime';

const PREVIEW_COUNT = 3;
const FLEET_LIMIT = 8;

function relativeTime(value: string | null): string {
  if (!value) return 'N/A';
  const minutes = Math.max(0, Math.floor((Date.now() - parseApiTimestamp(value).getTime()) / 60000));
  if (minutes < 1) return 'Just now';
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return days < 7 ? `${days}d ago` : parseApiTimestamp(value).toLocaleDateString();
}

const HEALTH_PRIORITY: Record<string, number> = { unhealthy: 0, degraded: 1, offline: 2, unknown: 3, stopped: 4, healthy: 5 };

const DEPLOY_TONES: Record<string, string> = {
  success: 'text-emerald-600',
  failed: 'text-red-600',
  running: 'text-blue-600',
  queued: 'text-yellow-600',
};

function SummaryCards({ summary }: { summary: DashboardSummaryResponse['summary'] }) {
  // Six counters, one comfortable row on wide screens. Every one is a
  // drill-down entry point: the project list understands health_status.
  const cards = [
    { label: 'Total Projects', value: summary.total_projects, icon: Package, color: 'text-blue-600 bg-blue-50', href: '/projects' },
    { label: 'Healthy', value: summary.healthy_projects, icon: CheckCircle, color: 'text-green-600 bg-green-50', href: '/projects?health_status=healthy' },
    { label: 'Degraded', value: summary.degraded_projects, icon: AlertTriangle, color: 'text-yellow-600 bg-yellow-50', href: '/projects?health_status=degraded' },
    { label: 'Unhealthy', value: summary.unhealthy_projects, icon: XCircle, color: 'text-red-600 bg-red-50', href: '/projects?health_status=unhealthy' },
    { label: 'Agent Offline', value: summary.offline_projects, icon: Server, color: 'text-orange-600 bg-orange-50', href: '/projects?health_status=offline' },
    { label: 'Stopped', value: summary.stopped_projects, icon: Power, color: 'text-gray-600 bg-gray-100', href: '/projects?health_status=stopped' },
  ];
  return <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-6">
    {cards.map(({ label, value, icon: Icon, color, href }) => <Link key={label} href={href} title={`View ${label.toLowerCase()}`} className="card flex items-center gap-3 p-4 transition hover:-translate-y-0.5 hover:border-primary-300 hover:shadow-md focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-500">
      <span className={`shrink-0 rounded-lg p-2 ${color}`}><Icon className="h-5 w-5" /></span>
      <div className="min-w-0">
        <p className="truncate text-xs text-gray-500">{label}</p>
        <p className="text-2xl font-semibold text-gray-900">{value}</p>
      </div>
    </Link>)}
  </div>;
}

function OverviewPanel({ title, count, href, icon: Icon, tone, children }: {
  title: string; count: number; href: string; icon: typeof AlertTriangle; tone: string; children: ReactNode;
}) {
  return <section className="card flex min-w-0 flex-col overflow-hidden">
    <div className="flex items-center gap-2 border-b border-gray-100 px-4 py-4">
      <Icon className={`h-5 w-5 ${tone}`} />
      <h2 className="min-w-0 flex-1 truncate font-semibold text-gray-900">{title}</h2>
      <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-600">{count}</span>
    </div>
    <div className="min-h-[15rem] flex-1 divide-y divide-gray-100">{children}</div>
    <Link href={href} className="flex items-center justify-between border-t border-gray-100 px-4 py-3 text-sm font-medium text-primary-700 hover:bg-primary-50">
      <span>View more</span><ArrowRight className="h-4 w-4" />
    </Link>
  </section>;
}

function EmptyPreview({ text }: { text: string }) {
  return <div className="flex h-60 items-center justify-center px-4 text-center text-sm text-gray-500">{text}</div>;
}

function FleetPanel({ projects }: { projects: Project[] }) {
  // Problems first; the API sort does not know about the agent-liveness view.
  const ordered = [...projects].sort((a, b) =>
    (HEALTH_PRIORITY[a.health_status || 'unknown'] ?? 99) - (HEALTH_PRIORITY[b.health_status || 'unknown'] ?? 99));
  const visible = ordered.slice(0, FLEET_LIMIT);
  return <section className="card flex min-w-0 flex-col overflow-hidden lg:col-span-2">
    <div className="flex items-center gap-2 border-b border-gray-100 px-4 py-4">
      <Package className="h-5 w-5 text-primary-600" />
      <h2 className="min-w-0 flex-1 truncate font-semibold text-gray-900">Projects</h2>
      <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-600">{projects.length}</span>
    </div>
    <div className="flex-1 overflow-x-auto">
      {visible.length === 0 ? <div className="px-4 py-10 text-center text-sm text-gray-500">No projects yet</div> : <table className="w-full min-w-[36rem] text-sm">
        <thead>
          <tr className="text-left text-[11px] uppercase tracking-wide text-gray-400">
            <th className="px-4 py-2 font-medium">Project</th>
            <th className="px-4 py-2 font-medium">Health</th>
            <th className="px-4 py-2 font-medium">Last deploy</th>
            <th className="px-4 py-2 font-medium">Heartbeat</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {visible.map(project => <tr key={project.id} className="hover:bg-gray-50">
            <td className="px-4 py-3">
              <Link href={`/projects/${project.id}`} className="font-medium text-gray-900 hover:text-primary-700">{project.name}</Link>
              <p className="text-xs capitalize text-gray-500">{project.environment || 'no environment'}</p>
            </td>
            <td className="px-4 py-3"><StatusBadge status={project.health_status || 'unknown'} small /></td>
            <td className="px-4 py-3 text-xs">
              {project.last_deployment_status
                ? <span className={DEPLOY_TONES[project.last_deployment_status] || 'text-gray-600'}>{project.last_deployment_status} · {relativeTime(project.last_deployment_at ?? null)}</span>
                : <span className="text-gray-400">never</span>}
            </td>
            <td className="px-4 py-3 text-xs text-gray-600">
              {project.agent_last_seen_at ? relativeTime(project.agent_last_seen_at) : <span className="text-gray-400">never</span>}
            </td>
          </tr>)}
        </tbody>
      </table>}
    </div>
    <Link href="/projects" className="flex items-center justify-between border-t border-gray-100 px-4 py-3 text-sm font-medium text-primary-700 hover:bg-primary-50">
      <span>View all projects</span><ArrowRight className="h-4 w-4" />
    </Link>
  </section>;
}

function DeploymentActivity({ summary }: { summary: DashboardSummaryResponse['summary'] }) {
  const success = summary.last_24h_deployments_success;
  const failed = summary.last_24h_deployments_failed;
  const total = success + failed;
  const rate = total === 0 ? null : Math.round((success / total) * 100);
  return <section className="card flex min-w-0 flex-col overflow-hidden">
    <div className="flex items-center gap-2 border-b border-gray-100 px-4 py-4">
      <Sparkles className="h-5 w-5 text-emerald-600" />
      <h2 className="min-w-0 flex-1 truncate font-semibold text-gray-900">Deployment activity</h2>
      <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-600">24h</span>
    </div>
    <div className="flex-1 space-y-5 px-4 py-5">
      <div className="grid grid-cols-3 gap-2 text-center">
        <div><p className="text-2xl font-semibold text-emerald-600">{success}</p><p className="text-xs text-gray-500">Succeeded</p></div>
        <div><p className="text-2xl font-semibold text-red-600">{failed}</p><p className="text-xs text-gray-500">Failed</p></div>
        <div><p className="text-2xl font-semibold text-gray-900">{rate === null ? '—' : `${rate}%`}</p><p className="text-xs text-gray-500">Success rate</p></div>
      </div>
      <div>
        <div className="flex h-2 w-full overflow-hidden rounded-full bg-gray-100">
          <div className="h-full bg-emerald-500" style={{ width: `${rate ?? 0}%` }} />
          <div className="h-full bg-red-400" style={{ width: `${total === 0 ? 0 : 100 - (rate ?? 0)}%` }} />
        </div>
        <p className="mt-2 text-xs text-gray-500">{total === 0 ? 'No deployments in the last 24 hours' : `${success} of ${total} deployments succeeded`}</p>
      </div>
    </div>
    <Link href="/activity/changes" className="flex items-center justify-between border-t border-gray-100 px-4 py-3 text-sm font-medium text-primary-700 hover:bg-primary-50">
      <span>View deployment history</span><ArrowRight className="h-4 w-4" />
    </Link>
  </section>;
}

function DashboardPage() {
  const [data, setData] = useState<DashboardSummaryResponse | null>(null);
  const [alerts, setAlerts] = useState<AlertListResponse | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const [summary, alertList, projectList] = await Promise.all([
        api.getDashboardSummary(),
        api.listAlerts({ status: ['open'], limit: PREVIEW_COUNT }),
        api.listProjects({ sort_by: 'health_status_priority', sort_order: 'asc' }),
      ]);
      setData(summary);
      setAlerts(alertList);
      setProjects(projectList);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load dashboard');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  return <AppLayout><div className="mx-auto max-w-[1500px] p-5 md:p-8">
    <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
      <div><h1 className="text-2xl font-bold text-gray-900">Dashboard</h1><p className="mt-1 text-sm text-gray-500">Fleet health, what needs attention, and what changed recently</p></div>
      <button onClick={refresh} disabled={loading} className="btn btn-secondary gap-2"><RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />Refresh</button>
    </div>
    {error && <div className="mb-5 rounded-md bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}
    {loading && !data ? <div className="card p-8 text-sm text-gray-500">Loading dashboard...</div> : data && <div className="space-y-5">
      <SummaryCards summary={data.summary} />
      <div className="grid items-stretch gap-4 lg:grid-cols-3">
        <OverviewPanel title="Needs Attention" count={data.anomaly_projects.length} href="/activity/attention" icon={AlertTriangle} tone="text-red-500">
          {data.anomaly_projects.length === 0 ? <EmptyPreview text="All projects look healthy" /> : data.anomaly_projects.slice(0, PREVIEW_COUNT).map(project =>
            <Link key={project.project_id} href={`/projects/${project.project_id}`} className="block h-20 px-4 py-3 hover:bg-gray-50">
              <div className="flex items-center gap-2"><span className="truncate text-sm font-medium text-gray-900">{project.project_name}</span>{project.health_status && <StatusBadge status={project.health_status} small />}</div>
              <p className="mt-1 truncate text-xs text-gray-500">{project.anomaly_types.map(type => type.replaceAll('_', ' ')).join(' · ')}</p>
            </Link>)}
        </OverviewPanel>
        <OverviewPanel title="Recent Changes" count={data.recent_changes.length} href="/activity/changes" icon={GitBranch} tone="text-primary-600">
          {data.recent_changes.length === 0 ? <EmptyPreview text="No recent changes" /> : data.recent_changes.slice(0, PREVIEW_COUNT).map((change, index) =>
            <Link key={`${change.event_type}-${change.occurred_at}-${index}`} href={change.deployment_id ? `/deployments/${change.deployment_id}` : `/projects/${change.project_id}`} className="block h-20 px-4 py-3 hover:bg-gray-50">
              <p className="truncate text-sm font-medium text-gray-900">{change.title}</p>
              <p className="mt-1 truncate text-xs text-gray-500">{change.project_name} · {relativeTime(change.occurred_at)}</p>
            </Link>)}
        </OverviewPanel>
        <OverviewPanel title="Recent Alerts" count={alerts?.open_count || 0} href="/activity/alerts" icon={AlertTriangle} tone="text-orange-500">
          {!alerts || alerts.alerts.length === 0 ? <EmptyPreview text="No active alerts" /> : alerts.alerts.map(alert =>
            <Link key={alert.id} href={`/projects/${alert.project_id}`} className="block h-20 px-4 py-3 hover:bg-gray-50">
              <p className="truncate text-sm font-medium text-gray-900">{alert.title}</p>
              <p className="mt-1 truncate text-xs text-gray-500">{alert.project_name || `Project #${alert.project_id}`} · {relativeTime(alert.last_seen_at)}</p>
            </Link>)}
        </OverviewPanel>
      </div>
      <div className="grid items-stretch gap-4 lg:grid-cols-3">
        <FleetPanel projects={projects} />
        <DeploymentActivity summary={data.summary} />
      </div>
    </div>}
  </div></AppLayout>;
}

export default function HomePage() {
  const [authenticated, setAuthenticated] = useState<boolean | null>(null);
  const [sessionExpired, setSessionExpired] = useState(false);

  useEffect(() => {
    setAuthenticated(!!getToken());
    // The API client fires this when the token is rejected: swap the panel for
    // the login form instead of leaving a half-loaded dashboard behind.
    const onExpired = () => {
      setSessionExpired(true);
      setAuthenticated(false);
    };
    window.addEventListener(AUTH_EXPIRED_EVENT, onExpired);
    return () => window.removeEventListener(AUTH_EXPIRED_EVENT, onExpired);
  }, []);

  if (authenticated === null) return <div className="flex min-h-screen items-center justify-center"><RefreshCw className="h-7 w-7 animate-spin text-primary-600" /></div>;
  return authenticated ? <DashboardPage /> : <LoginForm notice={sessionExpired ? '登录已过期，请重新登录' : undefined} />;
}
