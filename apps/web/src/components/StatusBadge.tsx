import clsx from 'clsx';

interface StatusBadgeProps {
  status: 'queued' | 'running' | 'success' | 'failed' | 'healthy' | 'degraded' | 'unhealthy' | 'unknown' | string;
  small?: boolean;
}

const STATUS_CONFIG: Record<string, { label: string; className: string }> = {
  queued: { label: 'Queued', className: 'bg-gray-100 text-gray-700' },
  running: { label: 'Running', className: 'bg-blue-100 text-blue-700' },
  success: { label: 'Deployed', className: 'bg-green-100 text-green-700' },
  failed: { label: 'Deploy Failed', className: 'bg-red-100 text-red-700' },
  healthy: { label: 'Healthy', className: 'bg-green-100 text-green-700' },
  degraded: { label: 'Degraded', className: 'bg-yellow-100 text-yellow-700' },
  unhealthy: { label: 'Health Check Failed', className: 'bg-red-100 text-red-700' },
  unknown: { label: 'Unknown', className: 'bg-gray-100 text-gray-700' },
  rolled_back: { label: 'Rolled Back', className: 'bg-purple-100 text-purple-700' },
  stopped: { label: 'Stopped', className: 'bg-gray-200 text-gray-700' },
  offline: { label: 'Agent Offline', className: 'bg-gray-200 text-gray-700' },
};

export default function StatusBadge({ status, small = false }: StatusBadgeProps) {
  const config = STATUS_CONFIG[status] || STATUS_CONFIG.unknown;

  return (
    <span
      className={clsx(
        'inline-flex items-center rounded-full font-medium',
        small ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-1 text-sm',
        config.className,
      )}
    >
      {config.label}
    </span>
  );
}
