'use client';

import { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import {
  RefreshCw,
  AlertTriangle,
  Server,
  CheckCircle,
  AlertCircle,
  XCircle,
  Clock,
  ArrowRight,
  ExternalLink,
  Package,
  GitBranch,
  Webhook,
  Flag,
  Undo2,
  Sparkles,
} from 'lucide-react';
import LoginForm from '@/components/LoginForm';
import AppLayout from '@/components/AppLayout';
import StatusBadge from '@/components/StatusBadge';
import {
  api,
  getToken,
  DashboardSummaryResponse,
  AnomalyProject,
  ChangeEvent,
  AnomalyType,
  EventCategory,
  Alert,
  AlertListResponse,
  AlertStatus,
  AlertType,
} from '@/lib/api';

const ANOMALY_LABELS: Record<AnomalyType, { label: string; icon: React.ReactNode; className: string }> = {
  agent_offline: {
    label: 'Agent Offline',
    icon: <Server className="w-3 h-3" />,
    className: 'bg-red-100 text-red-700',
  },
  health_unhealthy: {
    label: 'Health Check Failed',
    icon: <XCircle className="w-3 h-3" />,
    className: 'bg-red-100 text-red-700',
  },
  health_degraded: {
    label: 'Degraded',
    icon: <AlertTriangle className="w-3 h-3" />,
    className: 'bg-yellow-100 text-yellow-700',
  },
  last_deploy_failed: {
    label: 'Deploy Failed',
    icon: <XCircle className="w-3 h-3" />,
    className: 'bg-red-100 text-red-700',
  },
};

const EVENT_ICONS: Record<EventCategory, React.ReactNode> = {
  deployment: <Package className="w-4 h-4" />,
  rollback: <Undo2 className="w-4 h-4" />,
  flag_audit: <Flag className="w-4 h-4" />,
  webhook: <Webhook className="w-4 h-4" />,
};

const EVENT_LABELS: Record<EventCategory, string> = {
  deployment: 'Deployment',
  rollback: 'Rollback',
  flag_audit: 'Flag Change',
  webhook: 'Webhook',
};

function formatRelativeTime(dateStr: string | null): string {
  if (!dateStr) return 'N/A';
  
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  
  return date.toLocaleDateString();
}

function SummaryCards({ summary }: { summary: DashboardSummaryResponse['summary'] }) {
  const cards = [
    {
      label: 'Total Projects',
      value: summary.total_projects,
      icon: <Package className="w-5 h-5" />,
      bgColor: 'bg-blue-50',
      iconColor: 'text-blue-600',
    },
    {
      label: 'Healthy',
      value: summary.healthy_projects,
      icon: <CheckCircle className="w-5 h-5" />,
      bgColor: 'bg-green-50',
      iconColor: 'text-green-600',
    },
    {
      label: 'Degraded',
      value: summary.degraded_projects,
      icon: <AlertTriangle className="w-5 h-5" />,
      bgColor: 'bg-yellow-50',
      iconColor: 'text-yellow-600',
    },
    {
      label: 'Unhealthy',
      value: summary.unhealthy_projects,
      icon: <XCircle className="w-5 h-5" />,
      bgColor: 'bg-red-50',
      iconColor: 'text-red-600',
    },
    {
      label: 'Agent Offline',
      value: summary.offline_projects,
      icon: <Server className="w-5 h-5" />,
      bgColor: 'bg-orange-50',
      iconColor: 'text-orange-600',
    },
    {
      label: '24h Deployments',
      value: `${summary.last_24h_deployments_success}/${summary.last_24h_deployments_success + summary.last_24h_deployments_failed}`,
      subLabel: `${summary.last_24h_deployments_failed} failed`,
      icon: <Sparkles className="w-5 h-5" />,
      bgColor: summary.last_24h_deployments_failed > 0 ? 'bg-red-50' : 'bg-green-50',
      iconColor: summary.last_24h_deployments_failed > 0 ? 'text-red-600' : 'text-green-600',
    },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
      {cards.map((card, idx) => (
        <div key={idx} className="card p-4">
          <div className="flex items-center gap-3">
            <div className={`p-2 rounded-lg ${card.bgColor}`}>
              <span className={card.iconColor}>{card.icon}</span>
            </div>
            <div>
              <p className="text-sm text-gray-500">{card.label}</p>
              <p className="text-2xl font-bold text-gray-900">{card.value}</p>
              {card.subLabel && (
                <p className="text-xs text-red-600">{card.subLabel}</p>
              )}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

function AnomalyProjects({ projects }: { projects: AnomalyProject[] }) {
  if (projects.length === 0) {
    return (
      <div className="card p-8 text-center">
        <CheckCircle className="w-12 h-12 text-green-500 mx-auto mb-3" />
        <p className="text-gray-600">No abnormal projects detected. Everything looks good!</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {projects.map((project) => (
        <Link
          key={project.project_id}
          href={`/projects/${project.project_id}`}
          className="block card p-4 hover:border-primary-300 hover:shadow-md transition-all group"
        >
          <div className="flex items-start justify-between">
            <div className="flex-1">
              <div className="flex items-center gap-3 mb-2">
                <h3 className="text-lg font-semibold text-gray-900 group-hover:text-primary-700">
                  {project.project_name}
                </h3>
                {project.health_status && (
                  <StatusBadge status={project.health_status} small />
                )}
              </div>
              
              <div className="flex flex-wrap gap-2 mb-3">
                {project.anomaly_types.map((type, idx) => {
                  const config = ANOMALY_LABELS[type];
                  return (
                    <span
                      key={idx}
                      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${config.className}`}
                    >
                      {config.icon}
                      {config.label}
                    </span>
                  );
                })}
              </div>

              <div className="flex flex-wrap gap-4 text-sm text-gray-500">
                {project.agent_last_seen_at && (
                  <span className="flex items-center gap-1">
                    <Clock className="w-4 h-4" />
                    Last seen: {formatRelativeTime(project.agent_last_seen_at)}
                  </span>
                )}
                {project.last_deployment_id && (
                  <Link
                    href={`/deployments/${project.last_deployment_id}`}
                    onClick={(e) => e.stopPropagation()}
                    className="flex items-center gap-1 text-primary-600 hover:text-primary-700 hover:underline"
                  >
                    <ArrowRight className="w-4 h-4" />
                    {project.last_deployment_status === 'failed' ? 'Failed' : 'Last'} deployment
                  </Link>
                )}
              </div>
            </div>
            <ExternalLink className="w-5 h-5 text-gray-400 flex-shrink-0" />
          </div>
        </Link>
      ))}
    </div>
  );
}

function RecentChanges({ changes }: { changes: ChangeEvent[] }) {
  if (changes.length === 0) {
    return (
      <div className="card p-8 text-center">
        <GitBranch className="w-12 h-12 text-gray-400 mx-auto mb-3" />
        <p className="text-gray-600">No recent changes.</p>
      </div>
    );
  }

  const displayChanges = changes.slice(0, 20);

  return (
    <div className="space-y-1">
      {displayChanges.map((change, idx) => (
        <div
          key={idx}
          className="flex items-start gap-4 p-3 rounded-lg hover:bg-gray-50 transition-colors"
        >
          <div className="flex-shrink-0 mt-0.5">
            <div className={`p-1.5 rounded-lg ${
              change.event_category === 'deployment' ? 'bg-blue-100 text-blue-700' :
              change.event_category === 'rollback' ? 'bg-purple-100 text-purple-700' :
              change.event_category === 'flag_audit' ? 'bg-orange-100 text-orange-700' :
              'bg-gray-100 text-gray-700'
            }`}>
              {EVENT_ICONS[change.event_category]}
            </div>
          </div>
          
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-0.5">
              <span className="text-xs font-medium text-gray-500 uppercase">
                {EVENT_LABELS[change.event_category]}
              </span>
              <span className="text-xs text-gray-400">•</span>
              <span className="text-xs text-gray-500">
                {formatRelativeTime(change.occurred_at)}
              </span>
            </div>
            
            <p className="text-sm text-gray-900 truncate">
              {change.title}
            </p>
            
            <div className="flex items-center gap-3 mt-1">
              <Link
                href={`/projects/${change.project_id}`}
                className="text-xs text-gray-500 hover:text-primary-600 hover:underline"
              >
                {change.project_name}
              </Link>
              
              {change.deployment_id && (
                <Link
                  href={`/deployments/${change.deployment_id}`}
                  className="text-xs text-primary-600 hover:text-primary-700 hover:underline"
                >
                  View deployment
                </Link>
              )}
              
              {change.actor && (
                <span className="text-xs text-gray-400">
                  by {change.actor}
                </span>
              )}
            </div>
            
            {change.summary && (
              <p className="text-xs text-gray-400 mt-1 truncate">
                {change.summary}
              </p>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

const ALERT_TYPE_LABELS: Record<AlertType, { label: string; icon: React.ReactNode; color: string }> = {
  agent_offline: {
    label: 'Agent Offline',
    icon: <Server className="w-4 h-4" />,
    color: 'text-orange-600',
  },
  deployment_failed: {
    label: 'Deploy Failed',
    icon: <XCircle className="w-4 h-4" />,
    color: 'text-red-600',
  },
  health_unhealthy: {
    label: 'Health Check Failed',
    icon: <AlertCircle className="w-4 h-4" />,
    color: 'text-red-600',
  },
};

const ALERT_STATUS_LABELS: Record<AlertStatus, { label: string; icon: React.ReactNode; className: string }> = {
  open: {
    label: 'Open',
    icon: <AlertTriangle className="w-4 h-4" />,
    className: 'bg-red-100 text-red-700',
  },
  acknowledged: {
    label: 'Acknowledged',
    icon: <AlertCircle className="w-4 h-4" />,
    className: 'bg-blue-100 text-blue-700',
  },
  resolved: {
    label: 'Resolved',
    icon: <CheckCircle className="w-4 h-4" />,
    className: 'bg-green-100 text-green-700',
  },
};

function RecentAlerts({ alerts, counts, onAcknowledge, onResolve }: {
  alerts: Alert[];
  counts: { open: number; acknowledged: number; resolved: number };
  onAcknowledge: (alertId: number) => Promise<void>;
  onResolve: (alertId: number) => Promise<void>;
}) {
  const [statusFilter, setStatusFilter] = useState<AlertStatus | null>('open');
  const [acknowledgeLoading, setAcknowledgeLoading] = useState<number | null>(null);
  const [resolveLoading, setResolveLoading] = useState<number | null>(null);

  const filteredAlerts = alerts.filter(alert => {
    if (!statusFilter) return true;
    return alert.status === statusFilter;
  });

  const totalActive = counts.open + counts.acknowledged;

  if (alerts.length === 0) {
    return (
      <div className="card p-8 text-center">
        <CheckCircle className="w-12 h-12 text-green-500 mx-auto mb-3" />
        <p className="text-gray-600">No alerts. Everything looks good!</p>
      </div>
    );
  }

  const handleAcknowledge = async (alert: Alert) => {
    if (acknowledgeLoading !== null || resolveLoading !== null) return;
    setAcknowledgeLoading(alert.id);
    try {
      await onAcknowledge(alert.id);
    } finally {
      setAcknowledgeLoading(null);
    }
  };

  const handleResolve = async (alert: Alert) => {
    if (acknowledgeLoading !== null || resolveLoading !== null) return;
    setResolveLoading(alert.id);
    try {
      await onResolve(alert.id);
    } finally {
      setResolveLoading(null);
    }
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <AlertTriangle className="w-5 h-5 text-red-500" />
          <h2 className="text-lg font-semibold text-gray-900">
            Recent Alerts
          </h2>
          {totalActive > 0 && (
            <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-700">
              {totalActive} active
            </span>
          )}
        </div>

        <div className="flex gap-1">
          {(['open', 'acknowledged', 'resolved', null] as const).map(status => (
            <button
              key={status || 'all'}
              onClick={() => setStatusFilter(status)}
              className={`px-2 py-1 text-xs rounded-md transition-colors ${
                statusFilter === status
                  ? 'bg-primary-100 text-primary-700 font-medium'
                  : 'text-gray-600 hover:bg-gray-100'
              }`}
            >
              {status ? (
                <>
                  {ALERT_STATUS_LABELS[status].label}
                  {status === 'open' && counts.open > 0 && (
                    <span className="ml-1">({counts.open})</span>
                  )}
                  {status === 'acknowledged' && counts.acknowledged > 0 && (
                    <span className="ml-1">({counts.acknowledged})</span>
                  )}
                  {status === 'resolved' && counts.resolved > 0 && (
                    <span className="ml-1">({counts.resolved})</span>
                  )}
                </>
              ) : (
                'All'
              )}
            </button>
          ))}
        </div>
      </div>

      {filteredAlerts.length === 0 ? (
        <div className="card p-8 text-center">
          <p className="text-gray-500">No alerts with this status.</p>
        </div>
      ) : (
        <div className="space-y-2">
          {filteredAlerts.slice(0, 20).map(alert => {
            const typeConfig = ALERT_TYPE_LABELS[alert.alert_type];
            const statusConfig = ALERT_STATUS_LABELS[alert.status];

            return (
              <div
                key={alert.id}
                className={`card p-3 ${
                  alert.status === 'open' ? 'border-l-4 border-l-red-500' :
                  alert.status === 'acknowledged' ? 'border-l-4 border-l-blue-500' :
                  'border-l-4 border-l-green-500'
                }`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1 flex-wrap">
                      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${statusConfig.className}`}>
                        {statusConfig.icon}
                        {statusConfig.label}
                      </span>
                      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs ${typeConfig.color} bg-gray-100`}>
                        {typeConfig.icon}
                        {typeConfig.label}
                      </span>
                    </div>

                    <h4 className="text-sm font-medium text-gray-900 mb-1">
                      {alert.title}
                    </h4>

                    <div className="flex items-center gap-3 text-xs text-gray-500 mb-1 flex-wrap">
                      <span className="flex items-center gap-1">
                        <Server className="w-3 h-3" />
                        {alert.project_name || `Project #${alert.project_id}`}
                      </span>
                      <span className="flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        {formatRelativeTime(alert.first_seen_at)}
                      </span>
                      {alert.last_seen_at !== alert.first_seen_at && (
                        <span className="text-gray-400">
                          Last seen: {formatRelativeTime(alert.last_seen_at)}
                        </span>
                      )}
                    </div>

                    {alert.message && (
                      <p className="text-xs text-gray-600 whitespace-pre-line line-clamp-2">
                        {alert.message}
                      </p>
                    )}

                    {alert.acknowledged_by && (
                      <p className="text-xs text-gray-400 mt-1">
                        Acknowledged by {alert.acknowledged_by}
                      </p>
                    )}
                    {alert.resolved_by && (
                      <p className="text-xs text-gray-400 mt-1">
                        Resolved by {alert.resolved_by}
                      </p>
                    )}
                  </div>

                  <div className="flex flex-col gap-1 flex-shrink-0">
                    {alert.status === 'open' && (
                      <button
                        onClick={() => handleAcknowledge(alert)}
                        disabled={acknowledgeLoading === alert.id}
                        className="btn btn-secondary text-xs py-1 px-2"
                        title="Acknowledge"
                      >
                        {acknowledgeLoading === alert.id ? (
                          <RefreshCw className="w-3 h-3 animate-spin" />
                        ) : (
                          'Acknowledge'
                        )}
                      </button>
                    )}
                    {alert.status !== 'resolved' && (
                      <button
                        onClick={() => handleResolve(alert)}
                        disabled={resolveLoading === alert.id}
                        className="btn btn-secondary text-xs py-1 px-2 text-green-700 hover:bg-green-50"
                        title="Resolve"
                      >
                        {resolveLoading === alert.id ? (
                          <RefreshCw className="w-3 h-3 animate-spin" />
                        ) : (
                          'Resolve'
                        )}
                      </button>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function DashboardPage() {
  const [data, setData] = useState<DashboardSummaryResponse | null>(null);
  const [alertsData, setAlertsData] = useState<AlertListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    try {
      if (!refreshing) {
        setLoading(true);
      } else {
        setRefreshing(true);
      }

      const [dashboardResult, alertsResult] = await Promise.all([
        api.getDashboardSummary(),
        api.listAlerts({ limit: 50 }),
      ]);

      setData(dashboardResult);
      setAlertsData(alertsResult);
      setError(null);
    } catch (err: any) {
      setError(err.message || 'Failed to load dashboard');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [refreshing]);

  const handleAcknowledge = useCallback(async (alertId: number) => {
    await api.acknowledgeAlert(alertId);
    await fetchData();
  }, [fetchData]);

  const handleResolve = useCallback(async (alertId: number) => {
    await api.resolveAlert(alertId);
    await fetchData();
  }, [fetchData]);

  useEffect(() => {
    fetchData();
  }, []);

  return (
    <AppLayout>
      <div className="p-8 max-w-7xl">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
            <p className="text-gray-600 mt-1">Overview of your deployment infrastructure</p>
          </div>
          <button
            onClick={fetchData}
            disabled={refreshing || loading}
            className="btn btn-secondary flex items-center gap-2"
          >
            <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
            {refreshing ? 'Refreshing...' : 'Refresh'}
          </button>
        </div>

        {error && (
          <div className="mb-6 text-red-600 text-sm bg-red-50 px-4 py-3 rounded-md">
            {error}
          </div>
        )}

        {loading ? (
          <div className="space-y-8">
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
              {[...Array(6)].map((_, i) => (
                <div key={i} className="card p-4 animate-pulse">
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 bg-gray-200 rounded-lg" />
                    <div className="flex-1">
                      <div className="h-3 bg-gray-200 rounded w-16 mb-2" />
                      <div className="h-6 bg-gray-200 rounded w-8" />
                    </div>
                  </div>
                </div>
              ))}
            </div>
            
            <div className="card p-8">
              <div className="h-5 bg-gray-200 rounded w-48 mb-4 animate-pulse" />
              <div className="space-y-3">
                {[...Array(3)].map((_, i) => (
                  <div key={i} className="h-16 bg-gray-100 rounded animate-pulse" />
                ))}
              </div>
            </div>
          </div>
        ) : data ? (
          <div className="space-y-8">
            <SummaryCards summary={data.summary} />
            
            <div className="grid lg:grid-cols-2 gap-8">
              <div>
                <div className="flex items-center gap-2 mb-4">
                  <AlertTriangle className="w-5 h-5 text-red-500" />
                  <h2 className="text-lg font-semibold text-gray-900">
                    Needs Attention
                  </h2>
                  <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-700">
                    {data.anomaly_projects.length}
                  </span>
                </div>
                <AnomalyProjects projects={data.anomaly_projects} />
              </div>
              
              <div>
                <div className="flex items-center gap-2 mb-4">
                  <GitBranch className="w-5 h-5 text-primary-600" />
                  <h2 className="text-lg font-semibold text-gray-900">
                    Recent Changes
                  </h2>
                  <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-primary-100 text-primary-700">
                    {data.recent_changes.length}
                  </span>
                </div>
                <div className="card">
                  <RecentChanges changes={data.recent_changes} />
                </div>
              </div>
            </div>

            {alertsData && (
              <div className="mt-8">
                <RecentAlerts
                  alerts={alertsData.alerts}
                  counts={{
                    open: alertsData.open_count,
                    acknowledged: alertsData.acknowledged_count,
                    resolved: alertsData.resolved_count,
                  }}
                  onAcknowledge={handleAcknowledge}
                  onResolve={handleResolve}
                />
              </div>
            )}
          </div>
        ) : null}
      </div>
    </AppLayout>
  );
}

export default function HomePage() {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null);

  useEffect(() => {
    setIsAuthenticated(!!getToken());
  }, []);

  if (isAuthenticated === null) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="w-8 h-8 border-4 border-primary-600 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <LoginForm />;
  }

  return <DashboardPage />;
}
