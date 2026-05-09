'use client';

import { useState, useEffect, useCallback } from 'react';
import {
  Play,
  RefreshCw,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Loader2,
  ChevronDown,
  ChevronUp,
  Settings,
  FileCode,
  Server,
  Database,
  Network,
  Monitor,
  Clock,
  HelpCircle,
} from 'lucide-react';
import { api } from '@/lib/api';

interface PrecheckCheck {
  name: string;
  category: string;
  passed: boolean;
  message: string;
  severity: string;
  details?: string;
  resolution?: string;
}

interface LatestPrecheck {
  id: number;
  project_id: number;
  agent_id: string;
  overall_status: string;
  summary: {
    total: number;
    passed: number;
    failed: number;
    errors: number;
    warnings: number;
  };
  result_json: {
    agent_version?: string;
    timestamp?: number;
    categories?: Record<string, {
      passed: number;
      failed: number;
      checks: PrecheckCheck[];
    }>;
    checks?: PrecheckCheck[];
  };
  started_at: string | null;
  finished_at: string | null;
  created_at: string | null;
}

interface PendingTask {
  id: number;
  status: string;
  started_at: string | null;
  queued_at: string | null;
}

const CATEGORY_ICONS: Record<string, typeof Settings> = {
  configuration: Settings,
  tools: FileCode,
  docker: Server,
  filesystem: Database,
  network: Network,
  system: Monitor,
};

const CATEGORY_LABELS: Record<string, string> = {
  configuration: '配置检查',
  tools: '工具检查',
  docker: 'Docker 检查',
  filesystem: '文件系统',
  network: '网络检查',
  system: '系统资源',
};

const STATUS_LABELS: Record<string, { label: string; color: string; bgColor: string }> = {
  healthy: { label: '健康', color: 'text-green-700', bgColor: 'bg-green-100' },
  degraded: { label: '降级', color: 'text-amber-700', bgColor: 'bg-amber-100' },
  unhealthy: { label: '不健康', color: 'text-red-700', bgColor: 'bg-red-100' },
  unknown: { label: '未知', color: 'text-gray-700', bgColor: 'bg-gray-100' },
};

function formatDate(dateStr: string | null) {
  if (!dateStr) return '—';
  return new Date(dateStr).toLocaleString();
}

interface AgentPrecheckPanelProps {
  projectId: number;
}

export default function AgentPrecheckPanel({ projectId }: AgentPrecheckPanelProps) {
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pendingTask, setPendingTask] = useState<PendingTask | null>(null);
  const [latestPrecheck, setLatestPrecheck] = useState<LatestPrecheck | null>(null);
  const [expandedCategories, setExpandedCategories] = useState<Set<string>>(new Set());

  const fetchStatus = useCallback(async () => {
    try {
      const result = await api.getLatestPrecheck(projectId);
      setPendingTask(result.pending_task);
      setLatestPrecheck(result.latest_precheck);
      setError(null);
    } catch (err: any) {
      setError(err.message || 'Failed to load precheck status');
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    fetchStatus();
  }, [fetchStatus]);

  useEffect(() => {
    if (!pendingTask) return;

    const interval = setInterval(() => {
      fetchStatus();
    }, 3000);

    return () => clearInterval(interval);
  }, [pendingTask, fetchStatus]);

  const handleRunPrecheck = async () => {
    setRunning(true);
    setError(null);
    try {
      await api.triggerAgentPrecheck(projectId);
      await fetchStatus();
    } catch (err: any) {
      setError(err.message || 'Failed to trigger precheck');
    } finally {
      setRunning(false);
    }
  };

  const toggleCategory = (category: string) => {
    const newExpanded = new Set(expandedCategories);
    if (newExpanded.has(category)) {
      newExpanded.delete(category);
    } else {
      newExpanded.add(category);
    }
    setExpandedCategories(newExpanded);
  };

  const getCheckIcon = (check: PrecheckCheck) => {
    if (check.passed) {
      return <CheckCircle2 className="w-5 h-5 text-green-500" />;
    }
    if (check.severity === 'warning') {
      return <AlertTriangle className="w-5 h-5 text-amber-500" />;
    }
    return <XCircle className="w-5 h-5 text-red-500" />;
  };

  const getStatusStyle = (status: string) => {
    return STATUS_LABELS[status] || STATUS_LABELS.unknown;
  };

  if (loading) {
    return (
      <div className="card p-6">
        <div className="flex items-center justify-center py-8">
          <Loader2 className="w-8 h-8 animate-spin text-primary-600" />
        </div>
      </div>
    );
  }

  return (
    <div className="card p-6">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-primary-100 flex items-center justify-center">
            <Monitor className="w-5 h-5 text-primary-700" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-gray-900">Agent 环境预检</h3>
            <p className="text-sm text-gray-500">检查 Agent 运行环境是否符合部署要求</p>
          </div>
        </div>
        <button
          onClick={handleRunPrecheck}
          disabled={running || !!pendingTask}
          className="btn btn-primary flex items-center gap-2"
        >
          {running || pendingTask ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Play className="w-4 h-4" />
          )}
          {running ? '运行中...' : pendingTask ? '排队中...' : '运行预检'}
        </button>
      </div>

      {error && (
        <div className="mb-4 p-3 rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm">
          {error}
        </div>
      )}

      {!latestPrecheck && !pendingTask && (
        <div className="text-center py-12">
          <Monitor className="w-12 h-12 text-gray-300 mx-auto mb-4" />
          <p className="text-gray-500 mb-4">还没有运行过环境预检</p>
          <p className="text-sm text-gray-400">点击上方按钮运行首次预检</p>
        </div>
      )}

      {latestPrecheck && (
        <>
          <div className="mb-6">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <span className="text-sm text-gray-500">最新预检结果</span>
                <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${getStatusStyle(latestPrecheck.overall_status).bgColor} ${getStatusStyle(latestPrecheck.overall_status).color}`}>
                  {getStatusStyle(latestPrecheck.overall_status).label}
                </span>
              </div>
              <div className="flex items-center gap-1 text-xs text-gray-400">
                <Clock className="w-3 h-3" />
                {formatDate(latestPrecheck.finished_at || latestPrecheck.created_at)}
              </div>
            </div>

            <div className="grid grid-cols-4 gap-4">
              <div className="p-3 rounded-lg bg-gray-50">
                <div className="text-2xl font-bold text-gray-900">
                  {latestPrecheck.summary.passed}
                </div>
                <div className="text-xs text-gray-500">通过</div>
              </div>
              <div className="p-3 rounded-lg bg-gray-50">
                <div className="text-2xl font-bold text-gray-900">
                  {latestPrecheck.summary.total}
                </div>
                <div className="text-xs text-gray-500">总计</div>
              </div>
              <div className="p-3 rounded-lg bg-red-50">
                <div className="text-2xl font-bold text-red-600">
                  {latestPrecheck.summary.errors}
                </div>
                <div className="text-xs text-red-600">错误</div>
              </div>
              <div className="p-3 rounded-lg bg-amber-50">
                <div className="text-2xl font-bold text-amber-600">
                  {latestPrecheck.summary.warnings}
                </div>
                <div className="text-xs text-amber-600">警告</div>
              </div>
            </div>
          </div>

          {latestPrecheck.result_json?.categories && (
            <div className="space-y-4">
              {Object.entries(latestPrecheck.result_json.categories).map(([category, data]) => {
                const Icon = CATEGORY_ICONS[category] || Settings;
                const label = CATEGORY_LABELS[category] || category;
                const isExpanded = expandedCategories.has(category);
                const hasFailures = data.failed > 0;
                const allPassed = data.failed === 0;

                return (
                  <div
                    key={category}
                    className={`border rounded-lg overflow-hidden ${
                      hasFailures ? 'border-red-200' : 'border-gray-200'
                    }`}
                  >
                    <button
                      onClick={() => toggleCategory(category)}
                      className={`w-full p-4 flex items-center justify-between text-left ${
                        hasFailures ? 'bg-red-50 hover:bg-red-100' : 'bg-gray-50 hover:bg-gray-100'
                      } transition-colors`}
                    >
                      <div className="flex items-center gap-3">
                        <Icon className={`w-5 h-5 ${hasFailures ? 'text-red-500' : 'text-gray-500'}`} />
                        <div>
                          <span className="font-medium text-gray-900">{label}</span>
                          <span className="ml-2 text-xs text-gray-500">
                            ({data.passed}/{data.passed + data.failed} 通过)
                          </span>
                        </div>
                        {allPassed ? (
                          <CheckCircle2 className="w-5 h-5 text-green-500" />
                        ) : (
                          <AlertTriangle className="w-5 h-5 text-amber-500" />
                        )}
                      </div>
                      {isExpanded ? (
                        <ChevronUp className="w-5 h-5 text-gray-400" />
                      ) : (
                        <ChevronDown className="w-5 h-5 text-gray-400" />
                      )}
                    </button>

                    {isExpanded && (
                      <div className="p-4 space-y-3 border-t bg-white">
                        {data.checks.map((check, index) => (
                          <div key={index} className="p-3 rounded-lg bg-gray-50">
                            <div className="flex items-start gap-3">
                              {getCheckIcon(check)}
                              <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2">
                                  <span className="font-medium text-gray-900 text-sm">
                                    {check.name}
                                  </span>
                                  {!check.passed && (
                                    <span className={`px-1.5 py-0.5 rounded text-xs ${
                                      check.severity === 'warning'
                                        ? 'bg-amber-100 text-amber-700'
                                        : 'bg-red-100 text-red-700'
                                    }`}>
                                      {check.severity === 'warning' ? '警告' : '错误'}
                                    </span>
                                  )}
                                </div>
                                <p className="text-sm text-gray-600 mt-1">{check.message}</p>
                                {check.details && (
                                  <p className="text-xs text-gray-400 mt-1">{check.details}</p>
                                )}
                                {!check.passed && check.resolution && (
                                  <div className="mt-2 p-2 rounded bg-blue-50 border border-blue-200">
                                    <div className="flex items-start gap-2">
                                      <HelpCircle className="w-4 h-4 text-blue-500 mt-0.5 flex-shrink-0" />
                                      <div className="text-xs text-blue-700">
                                        <span className="font-medium">建议：</span>
                                        {check.resolution}
                                      </div>
                                    </div>
                                  </div>
                                )}
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </>
      )}

      {pendingTask && (
        <div className="mt-4 p-4 rounded-lg bg-blue-50 border border-blue-200">
          <div className="flex items-center gap-3">
            <Loader2 className="w-5 h-5 text-blue-600 animate-spin" />
            <div>
              <p className="font-medium text-blue-900">预检任务正在运行</p>
              <p className="text-sm text-blue-700">
                任务已排队，等待 Agent 执行...
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
