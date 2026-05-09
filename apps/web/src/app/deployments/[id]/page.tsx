'use client';

import { useState, useEffect, useRef, useMemo } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import {
  ArrowLeft,
  Clock,
  GitCommit,
  User,
  AlertTriangle,
  Activity,
  RefreshCw,
  RotateCw,
  Pause,
  Play,
  Download,
  RotateCcw,
  ArrowLeftCircle,
  Copy,
  Check,
  Server,
  CheckCircle,
  XCircle,
  Loader2,
  Ban,
  Lock,
} from 'lucide-react';
import AppLayout from '@/components/AppLayout';
import StatusBadge from '@/components/StatusBadge';
import DeploymentFailurePanel from '@/components/DeploymentFailurePanel';
import { api, Deployment, DeploymentLog, DeploymentDetailWithTargets } from '@/lib/api';

function formatDate(dateStr: string | null) {
  if (!dateStr) return '—';
  return new Date(dateStr).toLocaleString();
}

const PHASE_LABELS: Record<string, string> = {
  init: 'Initialize',
  git: 'Git Fetch',
  build: 'Build',
  pull: 'Pull Images',
  deploy: 'Deploy',
  healthcheck: 'Health Check',
  rollback: 'Rollback',
  cleanup: 'Cleanup',
  unknown: 'Other',
};

const PHASE_ORDER = ['init', 'git', 'build', 'pull', 'deploy', 'healthcheck', 'rollback', 'cleanup', 'unknown'];

function getPhaseLabel(phase: string | null): string {
  if (!phase) return 'Other';
  return PHASE_LABELS[phase] || phase;
}

function groupLogsByPhase(logs: DeploymentLog[]): Map<string, DeploymentLog[]> {
  const groups = new Map<string, DeploymentLog[]>();
  logs.forEach((log) => {
    const phase = log.phase || 'unknown';
    if (!groups.has(phase)) {
      groups.set(phase, []);
    }
    groups.get(phase)!.push(log);
  });
  return groups;
}

function containsError(content: string): boolean {
  const lower = content.toLowerCase();
  return (
    lower.includes('error') ||
    lower.includes('failed') ||
    lower.includes('fatal') ||
    lower.includes('exception') ||
    lower.includes('traceback')
  );
}

export default function DeploymentDetailPage() {
  const params = useParams();
  const deploymentId = Number(params.id);

  const [deployment, setDeployment] = useState<DeploymentDetailWithTargets | null>(null);
  const [logs, setLogs] = useState<DeploymentLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [lastLogSeq, setLastLogSeq] = useState<number>(-1);
  const [expandedPhases, setExpandedPhases] = useState<Set<string>>(
    new Set(PHASE_ORDER),
  );
  const logsEndRef = useRef<HTMLDivElement>(null);
  const autoScrollRef = useRef(true);

  const [retrying, setRetrying] = useState(false);
  const [copied, setCopied] = useState(false);
  const [rollingBack, setRollingBack] = useState(false);

  const loadDeployment = async () => {
    try {
      const data = await api.getDeploymentDetail(deploymentId);
      setDeployment(data);
      return data;
    } catch (err: any) {
      setError(err.message || 'Failed to load deployment');
      return null;
    }
  };

  const loadLogs = async (incremental: boolean = false) => {
    try {
      const logsData = await api.getDeploymentLogs(
        deploymentId,
        incremental && lastLogSeq >= 0 ? lastLogSeq : undefined,
      );

      if (logsData.length > 0) {
        const maxSeq = Math.max(...logsData.map((l) => l.seq));
        setLastLogSeq(maxSeq);

        if (incremental) {
          setLogs((prev) => [...prev, ...logsData]);
        } else {
          setLogs(logsData);
        }
      }
    } catch (err: any) {
      setError(err.message || 'Failed to load logs');
    }
  };

  const loadInitialData = async () => {
    try {
      setLoading(true);
      const deploymentData = await loadDeployment();
      if (deploymentData) {
        await loadLogs(false);
      }
      setError(null);
    } catch (err: any) {
      setError(err.message || 'Failed to load deployment');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadInitialData();
  }, [deploymentId]);

  useEffect(() => {
    if (!autoRefresh || !deployment || deployment.status !== 'running') {
      return;
    }

    const interval = setInterval(async () => {
      await loadDeployment();
      await loadLogs(true);
    }, 3000);

    return () => clearInterval(interval);
  }, [autoRefresh, deployment?.status, deploymentId, lastLogSeq]);

  useEffect(() => {
    if (autoScrollRef.current) {
      logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs]);

  const groupedLogs = useMemo(() => groupLogsByPhase(logs), [logs]);
  const hasError = logs.some((log) => containsError(log.content));

  const togglePhase = (phase: string) => {
    setExpandedPhases((prev) => {
      const next = new Set(prev);
      if (next.has(phase)) {
        next.delete(phase);
      } else {
        next.add(phase);
      }
      return next;
    });
  };

  const handleManualRefresh = async () => {
    await loadDeployment();
    await loadLogs(true);
  };

  const handleRetry = async () => {
    try {
      setRetrying(true);
      await api.retryDeployment(deploymentId);
      await loadDeployment();
      await loadLogs(true);
    } catch (err: any) {
      setError(err.message || 'Failed to retry deployment');
    } finally {
      setRetrying(false);
    }
  };

  const handleRollbackThis = async () => {
    if (!deployment || deployment.kind === 'rollback') return;
    try {
      setRollingBack(true);
      await api.rollbackProject(deployment.project_id, deploymentId);
      loadDeployment();
      loadLogs(true);
    } catch (err: any) {
      setError(err.message || 'Failed to rollback');
    } finally {
      setRollingBack(false);
    }
  };

  const handleDownloadLogs = () => {
    const token = api.getToken();
    const url = api.getDeploymentLogsDownloadUrl(deploymentId);
    
    const a = document.createElement('a');
    a.href = url;
    a.download = `deployment-${deploymentId}-logs.txt`;
    
    if (token) {
      fetch(url, {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      })
        .then(response => response.blob())
        .then(blob => {
          const blobUrl = URL.createObjectURL(blob);
          a.href = blobUrl;
          a.click();
          URL.revokeObjectURL(blobUrl);
        });
    } else {
      a.click();
    }
  };

  const handleCopyLogs = async () => {
    const allLogs = logs.map(log => log.content).join('\n');
    try {
      await navigator.clipboard.writeText(allLogs);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err: any) {
      console.error('Failed to copy:', err);
    }
  };

  if (loading) {
    return (
      <AppLayout>
        <div className="p-8 text-center text-gray-500">Loading...</div>
      </AppLayout>
    );
  }

  if (!deployment) {
    return (
      <AppLayout>
        <div className="p-8 text-center text-red-500">
          {error || 'Deployment not found'}
        </div>
      </AppLayout>
    );
  }

  const isRunning = deployment.status === 'running';

  return (
    <AppLayout>
      <div className="p-8 max-w-6xl">
        <Link
          href={`/projects/${deployment.project_id}`}
          className="inline-flex items-center text-sm text-gray-600 hover:text-gray-900 mb-6"
        >
          <ArrowLeft className="w-4 h-4 mr-1" />
          Back to project
        </Link>

        <div className="card p-6 mb-6">
          <div className="flex items-start justify-between">
            <div>
              <div className="flex items-center gap-3 mb-2">
                <h1 className="text-xl font-bold text-gray-900">
                  Deployment #{deployment.id}
                </h1>
                <StatusBadge status={deployment.status} />
                <span className="text-xs uppercase text-gray-500 bg-gray-100 px-2 py-0.5 rounded">
                  {deployment.kind}
                </span>
              </div>
              <div className="flex items-center gap-6 text-sm text-gray-600">
                {deployment.commit_hash && (
                  <span className="flex items-center gap-1">
                    <GitCommit className="w-4 h-4" />
                    Commit:{' '}
                    <code className="font-mono">
                      {deployment.commit_hash.substring(0, 10)}
                    </code>
                  </span>
                )}
                {deployment.triggered_by && (
                  <span className="flex items-center gap-1">
                    <User className="w-4 h-4" />
                    {deployment.triggered_by}
                  </span>
                )}
                {deployment.trigger_source && (
                  <span className="flex items-center gap-1">
                    via {deployment.trigger_source}
                  </span>
                )}
              </div>
            </div>
            <div className="flex items-center gap-2">
              {isRunning && (
                <>
                  <button
                    onClick={handleManualRefresh}
                    className="btn btn-secondary text-sm"
                    disabled={loading}
                  >
                    <RefreshCw
                      className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`}
                    />
                    Refresh
                  </button>
                  <button
                    onClick={() => setAutoRefresh(!autoRefresh)}
                    className={`btn text-sm ${
                      autoRefresh ? 'btn-primary' : 'btn-secondary'
                    }`}
                  >
                    {autoRefresh ? (
                      <>
                        <Pause className="w-4 h-4 mr-2" />
                        Pause
                      </>
                    ) : (
                      <>
                        <Play className="w-4 h-4 mr-2" />
                        Auto-refresh
                      </>
                    )}
                  </button>
                </>
              )}
              {(deployment.status === 'failed' || deployment.status === 'cancelled') && (
                <button
                  onClick={handleRetry}
                  disabled={retrying}
                  className="btn btn-secondary text-sm"
                >
                  <RotateCw
                    className={`w-4 h-4 mr-2 ${retrying ? 'animate-spin' : ''}`}
                  />
                  Retry
                </button>
              )}
              {deployment.status === 'success' && deployment.kind !== 'rollback' && (
                <button
                  onClick={handleRollbackThis}
                  disabled={rollingBack}
                  className="btn btn-secondary text-sm inline-flex items-center"
                >
                  <RotateCcw
                    className={`w-4 h-4 mr-2 ${rollingBack ? 'animate-spin' : ''}`}
                  />
                  Rollback to this
                </button>
              )}
            </div>
          </div>

          <div className="mt-4 grid grid-cols-3 gap-4 text-sm">
            <div className="text-gray-600">
              <span className="text-gray-400">Queued at:</span>
              <div className="font-mono">{formatDate(deployment.queued_at)}</div>
            </div>
            <div className="text-gray-600">
              <span className="text-gray-400">Started at:</span>
              <div className="font-mono">
                {deployment.started_at
                  ? formatDate(deployment.started_at)
                  : '—'}
              </div>
            </div>
            <div className="text-gray-600">
              <span className="text-gray-400">Finished at:</span>
              <div className="font-mono">
                {deployment.finished_at
                  ? formatDate(deployment.finished_at)
                  : '—'}
              </div>
            </div>
          </div>

          {deployment.last_heartbeat_at && isRunning && (
            <div className="mt-3 text-xs text-gray-500 flex items-center gap-1">
              <Activity className="w-3 h-3" />
              Last heartbeat: {formatDate(deployment.last_heartbeat_at)}
            </div>
          )}

          {deployment.failure_phase && (
            <div className="mt-4 flex items-center gap-2 text-red-600 text-sm bg-red-50 px-4 py-2 rounded-md">
              <AlertTriangle className="w-4 h-4" />
              <span className="font-medium">
                Failed at: {getPhaseLabel(deployment.failure_phase)}
              </span>
            </div>
          )}

          {deployment.error_code && (
            <div className="mt-2 text-red-600 text-sm bg-red-50 px-4 py-2 rounded-md font-mono">
              Error Code: {deployment.error_code}
            </div>
          )}
        </div>

        {(deployment.status === 'failed' || deployment.status === 'rollback_failed') && (
          <div className="mt-6">
            <DeploymentFailurePanel deploymentId={deployment.id} />
          </div>
        )}

        {deployment.targets && deployment.targets.length > 0 && (
          <div className="card p-6 mb-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
                <Server className="w-5 h-5" />
                Deployment Targets
              </h2>
              {deployment.target_stats && (
                <div className="flex items-center gap-3 text-sm">
                  <span className="text-gray-500">
                    {deployment.target_stats.total} total
                  </span>
                  {deployment.target_stats.success > 0 && (
                    <span className="text-green-600 flex items-center gap-1">
                      <CheckCircle className="w-4 h-4" />
                      {deployment.target_stats.success}
                    </span>
                  )}
                  {deployment.target_stats.failed > 0 && (
                    <span className="text-red-600 flex items-center gap-1">
                      <XCircle className="w-4 h-4" />
                      {deployment.target_stats.failed}
                    </span>
                  )}
                  {deployment.target_stats.running > 0 && (
                    <span className="text-blue-600 flex items-center gap-1">
                      <Loader2 className="w-4 h-4 animate-spin" />
                      {deployment.target_stats.running}
                    </span>
                  )}
                  {deployment.target_stats.queued > 0 && (
                    <span className="text-yellow-600">
                      Queued: {deployment.target_stats.queued}
                    </span>
                  )}
                  {deployment.target_stats.blocked > 0 && (
                    <span className="text-gray-600 flex items-center gap-1">
                      <Lock className="w-4 h-4" />
                      {deployment.target_stats.blocked}
                    </span>
                  )}
                  {deployment.target_stats.cancelled > 0 && (
                    <span className="text-gray-600 flex items-center gap-1">
                      <Ban className="w-4 h-4" />
                      {deployment.target_stats.cancelled}
                    </span>
                  )}
                </div>
              )}
            </div>

            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead>
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Target
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Agent
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Status
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Started
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Finished
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Commit
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Error
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {deployment.targets.map((target) => (
                    <tr key={target.id} className="hover:bg-gray-50">
                      <td className="px-4 py-3 whitespace-nowrap">
                        <div className="flex items-center gap-2">
                          <span className="font-medium text-gray-900">
                            {target.target_name || `Target #${target.id}`}
                          </span>
                          {target.target_role && (
                            <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-blue-50 text-blue-700">
                              {target.target_role}
                            </span>
                          )}
                          {target.target_order_index !== undefined &&
                            target.target_order_index > 0 && (
                              <span className="text-xs text-gray-400">
                                #{target.target_order_index}
                              </span>
                            )}
                        </div>
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm font-mono text-gray-600">
                        {target.agent_id}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap">
                        <StatusBadge status={target.status} />
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-500">
                        {target.started_at
                          ? formatDate(target.started_at)
                          : '—'}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-500">
                        {target.finished_at
                          ? formatDate(target.finished_at)
                          : '—'}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm font-mono text-gray-600">
                        {target.commit_hash
                          ? target.commit_hash.substring(0, 8)
                          : '—'}
                      </td>
                      <td className="px-4 py-3">
                        {target.error_message ? (
                          <div className="max-w-xs text-xs text-red-600 bg-red-50 px-2 py-1 rounded overflow-hidden text-ellipsis whitespace-nowrap">
                            {target.error_message}
                          </div>
                        ) : target.error_code ? (
                          <div className="text-xs font-mono text-red-600">
                            {target.error_code}
                          </div>
                        ) : (
                          <span className="text-xs text-gray-400">—</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        <div className="card p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-gray-900">Logs</h2>
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-4 text-sm text-gray-500">
                <span>{logs.length} log entries</span>
                {hasError && (
                  <span className="text-red-600 flex items-center gap-1">
                    <AlertTriangle className="w-4 h-4" />
                    Contains errors
                  </span>
                )}
              </div>
              {logs.length > 0 && (
                <div className="flex gap-1">
                  <button
                    onClick={handleCopyLogs}
                    className="btn btn-secondary text-xs py-1 px-2"
                    title="Copy all logs"
                  >
                    {copied ? (
                      <Check className="w-3 h-3 text-green-600" />
                    ) : (
                      <Copy className="w-3 h-3" />
                    )}
                  </button>
                  <button
                    onClick={handleDownloadLogs}
                    className="btn btn-secondary text-xs py-1 px-2"
                    title="Download logs as text file"
                  >
                    <Download className="w-3 h-3" />
                  </button>
                </div>
              )}
            </div>
          </div>

          {logs.length === 0 ? (
            <div className="text-center py-8 text-gray-500">
              No logs available yet.
              {isRunning && (
                <span className="block mt-2">
                  Logs will appear as the deployment progresses...
                </span>
              )}
            </div>
          ) : (
            <div className="space-y-3">
              {PHASE_ORDER.map((phase) => {
                const phaseLogs = groupedLogs.get(phase);
                if (!phaseLogs || phaseLogs.length === 0) return null;

                const isExpanded = expandedPhases.has(phase);
                const phaseHasError = phaseLogs.some((log) =>
                  containsError(log.content),
                );
                const isFailurePhase = deployment.failure_phase === phase;

                return (
                  <div key={phase}>
                    <button
                      onClick={() => togglePhase(phase)}
                      className={`w-full flex items-center justify-between p-3 rounded-md text-left transition-colors ${
                        phaseHasError || isFailurePhase
                          ? 'bg-red-50 hover:bg-red-100 border border-red-200'
                          : 'bg-gray-50 hover:bg-gray-100'
                      }`}
                    >
                      <div className="flex items-center gap-3">
                        <span className="text-xs font-mono text-gray-400">
                          {phaseLogs[0].seq} -{' '}
                          {phaseLogs[phaseLogs.length - 1].seq}
                        </span>
                        <span
                          className={`font-medium ${
                            phaseHasError || isFailurePhase
                              ? 'text-red-700'
                              : 'text-gray-700'
                          }`}
                        >
                          {getPhaseLabel(phase)}
                        </span>
                        <span className="text-xs text-gray-500">
                          ({phaseLogs.length} lines)
                        </span>
                        {isFailurePhase && (
                          <span className="text-xs text-red-600 bg-red-100 px-2 py-0.5 rounded">
                            FAILED
                          </span>
                        )}
                        {phaseHasError && !isFailurePhase && (
                          <AlertTriangle className="w-4 h-4 text-red-500" />
                        )}
                      </div>
                      <span className="text-gray-400">
                        {isExpanded ? '▼' : '▶'}
                      </span>
                    </button>

                    {isExpanded && (
                      <div className="bg-gray-900 text-gray-100 rounded-b-md mt-0 font-mono text-xs overflow-x-auto max-h-96 overflow-y-auto">
                        <div className="p-4">
                          {phaseLogs.map((log) => (
                            <div
                              key={log.id}
                              className={`whitespace-pre-wrap py-0.5 ${
                                containsError(log.content)
                                  ? 'text-red-400 bg-red-900/30 -mx-4 px-4'
                                  : ''
                              }`}
                            >
                              {log.content}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}

          <div ref={logsEndRef} />
        </div>
      </div>
    </AppLayout>
  );
}
