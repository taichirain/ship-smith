'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { AlertTriangle, ArrowRight, CheckCircle2, ExternalLink, Play, XCircle } from 'lucide-react';
import StatusBadge from '@/components/StatusBadge';
import { api, Alert, Deployment, ProjectStatus } from '@/lib/api';
import { parseApiTimestamp } from '@/lib/datetime';

const AGENT_STALE_MS = 10 * 60 * 1000;

function relativeTime(value?: string | null): string {
  if (!value) return 'never';
  const minutes = Math.max(0, Math.floor((Date.now() - parseApiTimestamp(value).getTime()) / 60000));
  if (minutes < 1) return 'just now';
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

interface Issue {
  key: string;
  title: string;
  detail: string;
  tone: 'error' | 'warning';
}

interface ProjectDiagnosisProps {
  projectId: number;
  status: ProjectStatus | null;
  deployments: Deployment[];
  healthcheckUrl?: string | null;
}

export default function ProjectDiagnosis({
  projectId,
  status,
  deployments,
  healthcheckUrl,
}: ProjectDiagnosisProps) {
  const [alerts, setAlerts] = useState<Alert[]>([]);

  useEffect(() => {
    let active = true;
    api
      .listAlerts({ project_id: projectId, status: ['open'], limit: 5 })
      .then((result) => {
        if (active) setAlerts(result.alerts);
      })
      .catch(() => {
        if (active) setAlerts([]);
      });
    return () => {
      active = false;
    };
  }, [projectId]);

  if (!status) return null;

  const issues: Issue[] = [];
  const lastDeployment = deployments[0];
  const agentStale =
    !status.agent_last_seen_at ||
    Date.now() - parseApiTimestamp(status.agent_last_seen_at).getTime() > AGENT_STALE_MS;

  if (agentStale) {
    issues.push({
      key: 'agent',
      tone: 'error',
      title: 'Agent 心跳中断',
      detail: `最后心跳 ${relativeTime(status.agent_last_seen_at)}，面板拿不到最新状态；先确认服务器上的 shipsmith-agent 是否在运行。`,
    });
  }

  if (status.app_health && status.app_health.status !== 'healthy') {
    const http = status.app_health.http_status ? `（HTTP ${status.app_health.http_status}）` : '';
    const detailParts = [
      status.app_health.response_ms != null ? `${status.app_health.response_ms}ms` : null,
      healthcheckUrl ? `探测 ${healthcheckUrl}` : null,
      status.app_health.error || null,
    ].filter(Boolean);
    issues.push({
      key: 'health',
      tone: 'error',
      title: `应用健康检查失败${http}`,
      detail: detailParts.join(' · ') || '健康检查端点没有返回预期状态',
    });
  }

  const brokenContainers = (status.containers || []).filter((container) => container.status !== 'running');
  if (!status.app_health && brokenContainers.length > 0) {
    issues.push({
      key: 'containers',
      tone: 'warning',
      title: `${brokenContainers.length} 个容器不在运行状态`,
      detail: brokenContainers.map((container) => container.service).join(' · '),
    });
  }

  if (lastDeployment && lastDeployment.status === 'failed') {
    issues.push({
      key: 'deploy',
      tone: 'error',
      title: `最后一次部署 #${lastDeployment.id} 失败`,
      detail: lastDeployment.failure_phase
        ? `失败阶段：${lastDeployment.failure_phase}`
        : '打开部署详情查看日志',
    });
  }

  const hasError = issues.some((issue) => issue.tone === 'error');

  if (issues.length === 0) {
    const lastCheck = status.app_health?.http_status
      ? `HTTP ${status.app_health.http_status}${
          status.app_health.response_ms != null ? ` · ${status.app_health.response_ms}ms` : ''
        }`
      : '无健康检查端点';
    return (
      <section className="mb-8 flex flex-wrap items-center gap-x-4 gap-y-2 rounded-lg border border-green-200 bg-green-50 px-4 py-3">
        <span className="flex items-center gap-2 text-sm font-medium text-green-800">
          <CheckCircle2 className="h-4 w-4" />
          运行正常
        </span>
        <span className="text-xs text-green-700">{lastCheck}</span>
        <span className="text-xs text-green-700">
          Agent 心跳 {relativeTime(status.agent_last_seen_at)}
        </span>
        <span className="text-xs text-gray-500">状态更新于 {relativeTime(status.updated_at)}</span>
        <a href="#agent-precheck" className="ml-auto text-xs font-medium text-green-800 hover:underline">
          运行环境预检 →
        </a>
      </section>
    );
  }

  return (
    <section
      className={`mb-8 rounded-lg border bg-white p-4 shadow-sm ${
        hasError ? 'border-red-200 border-l-4 border-l-red-500' : 'border-amber-200 border-l-4 border-l-amber-500'
      }`}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          {hasError ? (
            <XCircle className="mt-0.5 h-5 w-5 shrink-0 text-red-600" />
          ) : (
            <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-amber-600" />
          )}
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-sm font-semibold text-gray-900">
                {hasError ? '需要立即处理' : '需要关注'}
              </h2>
              <StatusBadge status={status.health_status || 'unknown'} small />
              <span className="text-xs text-gray-500">
                状态更新于 {relativeTime(status.updated_at)}
              </span>
            </div>
            <ul className="mt-3 space-y-2">
              {issues.map((issue) => (
                <li key={issue.key} className="text-sm">
                  <span className={issue.tone === 'error' ? 'font-medium text-red-700' : 'font-medium text-amber-700'}>
                    {issue.title}
                  </span>
                  <span className="ml-2 text-xs text-gray-500">{issue.detail}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <a href="#agent-precheck" className="btn btn-secondary text-xs">
            <Play className="mr-1 h-3 w-3" />
            运行预检
          </a>
          {lastDeployment && (
            <Link href={`/deployments/${lastDeployment.id}`} className="btn btn-secondary text-xs">
              最近部署 #{lastDeployment.id}
              <ArrowRight className="ml-1 h-3 w-3" />
            </Link>
          )}
          {healthcheckUrl && (
            <a href={healthcheckUrl} target="_blank" rel="noopener noreferrer" className="btn btn-secondary text-xs">
              健康检查地址
              <ExternalLink className="ml-1 h-3 w-3" />
            </a>
          )}
        </div>
      </div>

      {alerts.length > 0 && (
        <div className="mt-4 border-t border-gray-100 pt-3">
          <div className="mb-1 flex items-center gap-2 text-xs font-medium text-gray-600">
            <AlertTriangle className="h-3 w-3 text-orange-500" />
            未处理告警（{alerts.length}）
          </div>
          <ul className="space-y-1">
            {alerts.map((alert) => (
              <li key={alert.id} className="text-xs text-gray-600">
                <span className="font-medium text-gray-800">{alert.title}</span>
                <span className="ml-2 text-gray-400">{relativeTime(alert.last_seen_at)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
