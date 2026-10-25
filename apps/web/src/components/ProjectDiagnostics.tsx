'use client';

import { useCallback, useEffect, useState } from 'react';
import { AlertTriangle, ChevronDown, ChevronUp, FileText, Loader2, RefreshCw } from 'lucide-react';
import { api, DiagnosticSnapshotSummary } from '@/lib/api';
import { parseApiTimestamp } from '@/lib/datetime';

const TRIGGER_LABELS: Record<string, string> = {
  manual: '手动采集',
  deploy_failed: '部署失败自动采集',
  unhealthy: '健康检查转异常',
};

function formatTime(value: string): string {
  return parseApiTimestamp(value).toLocaleString();
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  return `${(bytes / 1024).toFixed(1)} KB`;
}

export default function ProjectDiagnostics({ projectId }: { projectId: number }) {
  const [snapshots, setSnapshots] = useState<DiagnosticSnapshotSummary[]>([]);
  const [selected, setSelected] = useState<{ id: number; content: string } | null>(null);
  const [loading, setLoading] = useState(true);
  const [collecting, setCollecting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const rows = await api.listProjectLogs(projectId, 20);
      setSnapshots(rows);
      setError(null);
      return rows;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load snapshots');
      return [];
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    void load();
  }, [load]);

  async function handleCollect() {
    setCollecting(true);
    setError(null);
    try {
      const before = snapshots[0]?.id ?? 0;
      await api.requestProjectLogs(projectId);
      // The agent picks the task up within a second or two; poll briefly.
      for (let attempt = 0; attempt < 12; attempt += 1) {
        await new Promise((resolve) => setTimeout(resolve, 2500));
        const rows = await load();
        if ((rows[0]?.id ?? 0) > before) {
          await openSnapshot(rows[0].id);
          break;
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to request logs');
    } finally {
      setCollecting(false);
    }
  }

  async function openSnapshot(id: number) {
    if (selected?.id === id) {
      setSelected(null);
      return;
    }
    try {
      const detail = await api.getProjectLogSnapshot(projectId, id);
      setSelected({ id: detail.id, content: detail.content });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load snapshot');
    }
  }

  return (
    <div className="card p-6">
      <div className="mb-4 flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary-100">
            <FileText className="h-5 w-5 text-primary-700" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-gray-900">诊断日志</h3>
            <p className="text-sm text-gray-500">
              采集容器状态和最近 200 行运行日志，脱敏后最多保存 64 KB
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => void load()}
            className="btn btn-secondary text-xs"
            title="刷新列表"
          >
            <RefreshCw className="h-3 w-3" />
          </button>
          <button
            type="button"
            onClick={handleCollect}
            disabled={collecting}
            className="btn btn-primary text-sm"
          >
            {collecting ? <Loader2 className="mr-1 h-4 w-4 animate-spin" /> : null}
            {collecting ? '采集中...' : '采集日志'}
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-3 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>
      )}

      {loading ? (
        <p className="py-6 text-center text-sm text-gray-500">Loading...</p>
      ) : snapshots.length === 0 ? (
        <p className="py-6 text-center text-sm text-gray-500">
          还没有快照。点「采集日志」拉一次，或等部署失败/健康异常时自动采集。
        </p>
      ) : (
        <ul className="divide-y divide-gray-100">
          {snapshots.map((snapshot) => (
            <li key={snapshot.id}>
              <button
                type="button"
                onClick={() => void openSnapshot(snapshot.id)}
                className="flex w-full items-center justify-between gap-2 py-2 text-left hover:bg-gray-50"
              >
                <span className="flex min-w-0 items-center gap-2">
                  <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-600">
                    {TRIGGER_LABELS[snapshot.trigger] || snapshot.trigger}
                  </span>
                  <span className="truncate text-sm text-gray-700">
                    {snapshot.reason || formatTime(snapshot.created_at)}
                  </span>
                  {snapshot.truncated && (
                    <span className="flex items-center gap-1 text-xs text-amber-600">
                      <AlertTriangle className="h-3 w-3" /> 已截断
                    </span>
                  )}
                </span>
                <span className="flex shrink-0 items-center gap-3 text-xs text-gray-500">
                  {formatSize(snapshot.byte_size)}
                  {selected?.id === snapshot.id ? (
                    <ChevronUp className="h-4 w-4" />
                  ) : (
                    <ChevronDown className="h-4 w-4" />
                  )}
                </span>
              </button>
              {selected?.id === snapshot.id && (
                <pre className="mb-3 max-h-96 overflow-auto rounded-md bg-gray-900 p-3 text-xs leading-relaxed text-gray-100">
                  {selected.content}
                </pre>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
