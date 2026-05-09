'use client';

import { useMemo } from 'react';
import { HealthHistoryRecord, DeploymentMarker, TimeRange } from '@/lib/api';

interface HealthTrendChartProps {
  records: HealthHistoryRecord[];
  deploymentMarkers: DeploymentMarker[];
  timeRange: TimeRange;
  onTimeRangeChange: (range: TimeRange) => void;
}

function getHealthColor(status: string): string {
  switch (status) {
    case 'healthy':
      return '#22c55e';
    case 'degraded':
      return '#f59e0b';
    case 'unhealthy':
      return '#ef4444';
    default:
      return '#9ca3af';
  }
}

function getHealthLabel(status: string): string {
  switch (status) {
    case 'healthy':
      return 'Healthy';
    case 'degraded':
      return 'Degraded';
    case 'unhealthy':
      return 'Health Check Failed';
    default:
      return 'Unknown';
  }
}

export default function HealthTrendChart({
  records,
  deploymentMarkers,
  timeRange,
  onTimeRangeChange,
}: HealthTrendChartProps) {
  const chartData = useMemo(() => {
    if (records.length === 0) {
      return { points: [], deploymentPositions: [], hasData: false };
    }

    const width = 600;
    const height = 200;
    const padding = { top: 20, right: 20, bottom: 30, left: 40 };
    const chartWidth = width - padding.left - padding.right;
    const chartHeight = height - padding.top - padding.bottom;

    const times = records.map((r) => new Date(r.timestamp).getTime());
    const minTime = Math.min(...times);
    const maxTime = Math.max(...times);
    const timeRangeMs = maxTime - minTime || 1;

    const responseTimes = records
      .map((r) => r.response_ms)
      .filter((ms): ms is number => ms !== null && ms !== undefined);
    const maxResponseTime = responseTimes.length > 0 ? Math.max(...responseTimes, 100) : 100;

    const points = records.map((record) => {
      const time = new Date(record.timestamp).getTime();
      const x = padding.left + ((time - minTime) / timeRangeMs) * chartWidth;
      const responseMs = record.response_ms ?? 0;
      const y =
        padding.top +
        chartHeight -
        (responseMs / maxResponseTime) * chartHeight * 0.8;

      return {
        x,
        y: Math.max(padding.top + 5, y),
        time,
        healthStatus: record.health_status,
        responseMs: record.response_ms,
      };
    });

    const deploymentPositions = deploymentMarkers
      .map((marker) => {
        const markerTime = new Date(marker.timestamp).getTime();
        if (markerTime < minTime || markerTime > maxTime) {
          return null;
        }
        const x =
          padding.left + ((markerTime - minTime) / timeRangeMs) * chartWidth;
        return {
          x,
          y: padding.top,
          marker,
        };
      })
      .filter((p): p is NonNullable<typeof p> => p !== null);

    return {
      width,
      height,
      padding,
      chartWidth,
      chartHeight,
      points,
      deploymentPositions,
      maxResponseTime,
      hasData: true,
    };
  }, [records, deploymentMarkers]);

  const formatTime = (timestamp: string) => {
    const date = new Date(timestamp);
    if (timeRange === '24h') {
      return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }
    return date.toLocaleDateString([], { month: 'short', day: 'numeric' });
  };

  if (!chartData.hasData || chartData.points.length === 0) {
    return (
      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
            <span>📈</span>
            Health Trend
          </h2>
          <div className="flex gap-2">
            <button
              onClick={() => onTimeRangeChange('24h')}
              className={`px-3 py-1 text-sm rounded-md transition-colors ${
                timeRange === '24h'
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              24h
            </button>
            <button
              onClick={() => onTimeRangeChange('7d')}
              className={`px-3 py-1 text-sm rounded-md transition-colors ${
                timeRange === '7d'
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              7d
            </button>
          </div>
        </div>
        <div className="card p-6">
          <div className="text-center text-gray-500 py-8">
            <div className="text-4xl mb-2">📊</div>
            <p>No health history data available yet.</p>
            <p className="text-sm mt-1">
              Heartbeats from the agent will appear here once collected.
            </p>
          </div>
        </div>
      </div>
    );
  }

  const { points, deploymentPositions } = chartData;
  const maxResponseTime = chartData.maxResponseTime ?? 100;

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
          <span>📈</span>
          Health Trend
        </h2>
        <div className="flex gap-2">
          <button
            onClick={() => onTimeRangeChange('24h')}
            className={`px-3 py-1 text-sm rounded-md transition-colors ${
              timeRange === '24h'
                ? 'bg-blue-600 text-white'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            24h
          </button>
          <button
            onClick={() => onTimeRangeChange('7d')}
            className={`px-3 py-1 text-sm rounded-md transition-colors ${
              timeRange === '7d'
                ? 'bg-blue-600 text-white'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            7d
          </button>
        </div>
      </div>

      <div className="card p-6">
        <div className="flex flex-wrap gap-4 mb-4 text-xs">
          <div className="flex items-center gap-1.5">
            <span
              className="w-3 h-3 rounded-full"
              style={{ backgroundColor: '#22c55e' }}
            />
            <span className="text-gray-600">Healthy</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span
              className="w-3 h-3 rounded-full"
              style={{ backgroundColor: '#f59e0b' }}
            />
            <span className="text-gray-600">Degraded</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span
              className="w-3 h-3 rounded-full"
              style={{ backgroundColor: '#ef4444' }}
            />
            <span className="text-gray-600">Unhealthy</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-0.5 bg-gray-400" />
            <span className="text-gray-600">Response Time</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="text-blue-600 font-bold">▼</span>
            <span className="text-gray-600">Deployment</span>
          </div>
        </div>

        <div className="overflow-x-auto">
          <svg
            width="100%"
            viewBox="0 0 600 200"
            className="min-w-[500px]"
            preserveAspectRatio="xMidYMid meet"
          >
            <defs>
              <linearGradient id="lineGradient" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stopColor="#3b82f6" />
                <stop offset="100%" stopColor="#8b5cf6" />
              </linearGradient>
            </defs>

            {[0, 0.25, 0.5, 0.75, 1].map((ratio, i) => (
              <line
                key={`grid-${i}`}
                x1={40}
                y1={20 + ratio * 150}
                x2={580}
                y2={20 + ratio * 150}
                stroke="#e5e7eb"
                strokeWidth={1}
                strokeDasharray={ratio === 1 ? '0' : '4,4'}
              />
            ))}

            <text x={35} y={25} fontSize={10} fill="#9ca3af" textAnchor="end">
              {maxResponseTime}ms
            </text>
            <text x={35} y={95} fontSize={10} fill="#9ca3af" textAnchor="end">
              {Math.round(maxResponseTime / 2)}ms
            </text>
            <text x={35} y={175} fontSize={10} fill="#9ca3af" textAnchor="end">
              0ms
            </text>

            {points.length > 1 && (
              <polyline
                points={points.map((p) => `${p.x},${p.y}`).join(' ')}
                fill="none"
                stroke="url(#lineGradient)"
                strokeWidth={2}
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            )}

            {points.map((point, i) => (
              <circle
                key={`point-${i}`}
                cx={point.x}
                cy={point.y}
                r={4}
                fill={getHealthColor(point.healthStatus)}
                stroke="white"
                strokeWidth={1.5}
              >
                <title>
                  {getHealthLabel(point.healthStatus)}
                  {point.responseMs !== null && point.responseMs !== undefined
                    ? ` - ${point.responseMs}ms`
                    : ''}
                  {' - '}
                  {new Date(point.time).toLocaleString()}
                </title>
              </circle>
            ))}

            {deploymentPositions.map((pos, i) => {
              const isSuccess = pos.marker.status === 'success' || pos.marker.status === 'rolled_back';
              return (
                <g key={`deployment-${i}`}>
                  <line
                    x1={pos.x}
                    y1={15}
                    x2={pos.x}
                    y2={180}
                    stroke={isSuccess ? '#22c55e' : '#ef4444'}
                    strokeWidth={1}
                    strokeDasharray="4,4"
                    opacity={0.6}
                  />
                  <polygon
                    points={`${pos.x},5 ${pos.x - 5},15 ${pos.x + 5},15`}
                    fill={isSuccess ? '#22c55e' : '#ef4444'}
                  >
                    <title>
                      {pos.marker.kind === 'rollback' ? 'Rollback' : 'Deployment'} #{pos.marker.deployment_id}
                      {' - '}
                      {pos.marker.status}
                      {pos.marker.commit_hash ? ` (${pos.marker.commit_hash.substring(0, 8)})` : ''}
                      {' - '}
                      {new Date(pos.marker.timestamp).toLocaleString()}
                    </title>
                  </polygon>
                </g>
              );
            })}

            {points.length >= 5 && (
              <>
                <text
                  x={points[0].x}
                  y={195}
                  fontSize={10}
                  fill="#9ca3af"
                  textAnchor="middle"
                >
                  {formatTime(records[0].timestamp)}
                </text>
                <text
                  x={points[Math.floor(points.length / 2)].x}
                  y={195}
                  fontSize={10}
                  fill="#9ca3af"
                  textAnchor="middle"
                >
                  {formatTime(records[Math.floor(records.length / 2)].timestamp)}
                </text>
                <text
                  x={points[points.length - 1].x}
                  y={195}
                  fontSize={10}
                  fill="#9ca3af"
                  textAnchor="middle"
                >
                  {formatTime(records[records.length - 1].timestamp)}
                </text>
              </>
            )}
          </svg>
        </div>

        <div className="mt-4 grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
          <div className="bg-gray-50 rounded p-3">
            <div className="text-xs text-gray-500 mb-1">Total Heartbeats</div>
            <div className="text-xl font-semibold text-gray-900">
              {records.length}
            </div>
          </div>
          <div className="bg-green-50 rounded p-3">
            <div className="text-xs text-gray-500 mb-1">Healthy</div>
            <div className="text-xl font-semibold text-green-600">
              {records.filter((r) => r.health_status === 'healthy').length}
            </div>
          </div>
          <div className="bg-yellow-50 rounded p-3">
            <div className="text-xs text-gray-500 mb-1">Degraded</div>
            <div className="text-xl font-semibold text-yellow-600">
              {records.filter((r) => r.health_status === 'degraded').length}
            </div>
          </div>
          <div className="bg-red-50 rounded p-3">
            <div className="text-xs text-gray-500 mb-1">Unhealthy</div>
            <div className="text-xl font-semibold text-red-600">
              {records.filter((r) => r.health_status === 'unhealthy').length}
            </div>
          </div>
        </div>

        {deploymentMarkers.length > 0 && (
          <div className="mt-4 border-t pt-4">
            <h3 className="text-sm font-medium text-gray-700 mb-2">
              Deployments in this period
            </h3>
            <div className="space-y-2">
              {deploymentMarkers.map((marker) => (
                <div
                  key={marker.deployment_id}
                  className="flex items-center justify-between text-sm bg-gray-50 rounded px-3 py-2"
                >
                  <div className="flex items-center gap-2">
                    <span
                      className={`w-2 h-2 rounded-full ${
                        marker.status === 'success' || marker.status === 'rolled_back'
                          ? 'bg-green-500'
                          : 'bg-red-500'
                      }`}
                    />
                    <span className="font-medium">
                      {marker.kind === 'rollback' ? 'Rollback' : 'Deployment'} #{marker.deployment_id}
                    </span>
                    {marker.commit_hash && (
                      <span className="text-gray-500 font-mono text-xs">
                        ({marker.commit_hash.substring(0, 8)})
                      </span>
                    )}
                  </div>
                  <span className="text-gray-500 text-xs">
                    {new Date(marker.timestamp).toLocaleString()}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
