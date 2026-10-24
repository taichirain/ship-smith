'use client';

import { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import {
  ArrowLeft,
  Play,
  RotateCcw,
  Plus,
  Clock,
  GitCommit,
  User,
  Flag,
  Settings,
  Key,
  Webhook,
  RefreshCw,
  Copy,
  Check,
  AlertTriangle,
  Trash2,
  Archive,
  ArchiveRestore,
  Server,
  Activity,
  HardDrive,
  Cpu,
  Monitor,
  Terminal,
  FileCode,
  HelpCircle,
  History,
  ChevronDown,
  Filter,
  Loader2,
  Bell,
  BellOff,
  Send,
  XCircle,
  CheckCircle2,
  Zap,
  ExternalLink,
  Link2,
  Sparkles,
  Notebook,
  AlertCircle,
  BarChart3,
  FileSearch,
  Database,
  FileEdit,
  ShieldCheck,
  FolderGit2,
  Rocket,
} from 'lucide-react';
import AppLayout from '@/components/AppLayout';
import StatusBadge from '@/components/StatusBadge';
import HealthTrendChart from '@/components/HealthTrendChart';
import AgentPrecheckPanel from '@/components/AgentPrecheckPanel';
import {
  api,
  Project,
  Deployment,
  FeatureFlag,
  ProjectStatus,
  ProjectUpdate,
  TimelineEvent,
  TimelineEventType,
  NotificationChannel,
  NotificationSetting,
  NotificationDelivery,
  NotificationEventType,
  ChannelType,
  HealthHistoryRecord,
  DeploymentMarker,
  TimeRange,
  ProjectTarget,
  ProjectTargetCreate,
  ProjectTargetUpdate,
  OnboardingStatusResponse,
  InstallCommandResponse,
  InstallCommandRequest,
  TargetPlatform,
  GitCredentialType,
} from '@/lib/api';
import { parseApiTimestamp } from '@/lib/datetime';

function formatDate(dateStr: string | null) {
  if (!dateStr) return '—';
  return parseApiTimestamp(dateStr).toLocaleString();
}

function copyToClipboard(text: string): Promise<void> {
  return navigator.clipboard.writeText(text);
}

const TIMELINE_FILTER_OPTIONS: { value: TimelineEventType | null; label: string; category: string }[] = [
  { value: null, label: 'All Events', category: 'general' },
  { value: 'deployment_queued', label: 'Deployment Queued', category: 'deployment' },
  { value: 'deployment_running', label: 'Deployment Running', category: 'deployment' },
  { value: 'deployment_success', label: 'Deployment Success', category: 'deployment' },
  { value: 'deployment_failed', label: 'Deployment Failed', category: 'deployment' },
  { value: 'rollback_queued', label: 'Rollback Queued', category: 'deployment' },
  { value: 'rollback_running', label: 'Rollback Running', category: 'deployment' },
  { value: 'rollback_success', label: 'Rollback Success', category: 'deployment' },
  { value: 'rollback_failed', label: 'Rollback Failed', category: 'deployment' },
  { value: 'flag_created', label: 'Flag Created', category: 'flag' },
  { value: 'flag_updated', label: 'Flag Updated', category: 'flag' },
  { value: 'flag_archived', label: 'Flag Archived', category: 'flag' },
  { value: 'flag_unarchived', label: 'Flag Unarchived', category: 'flag' },
  { value: 'config_updated', label: 'Config Updated', category: 'config' },
  { value: 'webhook_accepted', label: 'Webhook Received', category: 'webhook' },
  { value: 'agent_offline', label: 'Agent Offline', category: 'agent' },
  { value: 'agent_recovered', label: 'Agent Recovered', category: 'agent' },
];

function getTimelineEventIcon(type: TimelineEventType) {
  if (type.startsWith('deployment_') || type.startsWith('rollback_')) {
    return GitCommit;
  }
  if (type.startsWith('flag_')) {
    return Flag;
  }
  if (type === 'config_updated') {
    return Settings;
  }
  if (type.startsWith('webhook_')) {
    return Webhook;
  }
  if (type.startsWith('agent_')) {
    return Activity;
  }
  return Clock;
}

function getTimelineEventStyle(type: TimelineEventType): { iconBg: string; iconColor: string; borderColor: string; important: boolean } {
  const typeStr = type as string;
  
  const importantTypes = new Set([
    'deployment_failed',
    'rollback_failed',
    'agent_offline',
    'flag_archived',
  ]);
  
  if (importantTypes.has(typeStr)) {
    return {
      iconBg: 'bg-red-100',
      iconColor: 'text-red-600',
      borderColor: 'border-l-red-400',
      important: true,
    };
  }
  
  const successTypes = new Set([
    'deployment_success',
    'rollback_success',
    'agent_recovered',
  ]);
  if (successTypes.has(typeStr)) {
    return {
      iconBg: 'bg-green-100',
      iconColor: 'text-green-600',
      borderColor: 'border-l-green-300',
      important: false,
    };
  }
  
  const runningTypes = new Set([
    'deployment_queued',
    'deployment_running',
    'rollback_queued',
    'rollback_running',
  ]);
  if (runningTypes.has(typeStr)) {
    return {
      iconBg: 'bg-blue-100',
      iconColor: 'text-blue-600',
      borderColor: 'border-l-blue-300',
      important: false,
    };
  }
  
  const flagTypes = new Set([
    'flag_created',
    'flag_updated',
    'flag_unarchived',
  ]);
  if (flagTypes.has(typeStr)) {
    return {
      iconBg: 'bg-purple-100',
      iconColor: 'text-purple-600',
      borderColor: 'border-l-purple-300',
      important: false,
    };
  }
  
  if (typeStr === 'config_updated') {
    return {
      iconBg: 'bg-orange-100',
      iconColor: 'text-orange-600',
      borderColor: 'border-l-orange-300',
      important: false,
    };
  }
  
  if (typeStr.startsWith('webhook_')) {
    return {
      iconBg: 'bg-cyan-100',
      iconColor: 'text-cyan-600',
      borderColor: 'border-l-cyan-300',
      important: false,
    };
  }
  
  return {
    iconBg: 'bg-gray-100',
    iconColor: 'text-gray-600',
    borderColor: 'border-l-gray-300',
    important: false,
  };
}

interface QuickActionItem {
  label: string;
  value: string;
  icon: React.ReactNode;
  type: 'copy' | 'open' | 'jump';
  key: string;
  href?: string;
  disabled?: boolean;
}

function QuickActionButton({
  item,
  onCopy,
  copiedKey,
}: {
  item: QuickActionItem;
  onCopy: (text: string, key: string) => void;
  copiedKey: string | null;
}) {
  const isCopied = copiedKey === item.key;

  if (item.type === 'open' && item.href) {
    return (
      <a
        href={item.href}
        target="_blank"
        rel="noopener noreferrer"
        className="flex items-center gap-2 p-2 rounded-md hover:bg-gray-50 text-gray-600 hover:text-gray-900 transition-colors text-sm"
        title={item.disabled ? 'Not available' : `Open ${item.label}`}
        onClick={(e) => {
          if (item.disabled) e.preventDefault();
        }}
        style={{ opacity: item.disabled ? 0.4 : 1, pointerEvents: item.disabled ? 'none' : 'auto' }}
      >
        {item.icon}
        <span className="truncate flex-1">{item.value}</span>
        <ExternalLink className="w-3 h-3 flex-shrink-0 text-gray-400" />
      </a>
    );
  }

  if (item.type === 'jump' && item.href) {
    return (
      <Link
        href={item.href}
        className="flex items-center gap-2 p-2 rounded-md hover:bg-red-50 text-red-600 hover:text-red-700 transition-colors text-sm"
        style={{ opacity: item.disabled ? 0.4 : 1, pointerEvents: item.disabled ? 'none' : 'auto' }}
      >
        {item.icon}
        <span className="truncate flex-1">{item.value}</span>
        <ArrowLeft className="w-3 h-3 flex-shrink-0 rotate-180 text-red-400" />
      </Link>
    );
  }

  return (
    <button
      onClick={() => !item.disabled && onCopy(item.value, item.key)}
      className="flex items-center gap-2 p-2 rounded-md hover:bg-gray-50 text-gray-600 hover:text-gray-900 transition-colors text-sm w-full text-left disabled:opacity-40 disabled:cursor-not-allowed"
      title={item.disabled ? 'Not available' : `Copy ${item.label}`}
      disabled={item.disabled}
    >
      {isCopied ? (
        <Check className="w-4 h-4 text-green-500" />
      ) : (
        item.icon
      )}
      <span className="truncate flex-1 font-mono">{item.value}</span>
      {isCopied ? (
        <CheckCircle2 className="w-3 h-3 text-green-500" />
      ) : (
        <Copy className="w-3 h-3 flex-shrink-0 text-gray-400" />
      )}
    </button>
  );
}

function QuickActionsSection({
  project,
  projectStatus,
  lastSuccessDeployment,
  lastFailedDeployment,
  onCopy,
  copiedKey,
}: {
  project: Project;
  projectStatus: ProjectStatus | null;
  lastSuccessDeployment: Deployment | undefined;
  lastFailedDeployment: Deployment | undefined;
  onCopy: (text: string, key: string) => void;
  copiedKey: string | null;
}) {
  const getWebhookEndpoint = (type: 'github' | 'gitlab') => {
    if (!project.webhook_endpoint_id) return null;
    return `/api/v1/webhooks/${project.webhook_endpoint_id}/${type}`;
  };

  const getRepoUrl = () => {
    const repo = project.git_repo;
    if (!repo) return null;
    if (repo.startsWith('http://') || repo.startsWith('https://')) {
      return repo;
    }
    if (repo.startsWith('git@')) {
      return repo.replace(':', '/').replace('git@', 'https://');
    }
    return `https://${repo}`;
  };

  const actions: QuickActionItem[] = [
    {
      label: 'Agent ID',
      value: project.agent_id,
      icon: <Server className="w-4 h-4" />,
      type: 'copy',
      key: 'agent_id',
      disabled: !project.agent_id,
    },
    {
      label: 'Current Commit',
      value: projectStatus?.current_commit_hash
        ? projectStatus.current_commit_hash.substring(0, 12)
        : '—',
      icon: <GitCommit className="w-4 h-4" />,
      type: 'copy',
      key: 'current_commit',
      disabled: !projectStatus?.current_commit_hash,
    },
    {
      label: 'Webhook Secret',
      value: project.webhook_secret
        ? '••••••••••••••••'
        : 'Not configured',
      icon: <Key className="w-4 h-4" />,
      type: 'copy',
      key: 'webhook_secret',
      disabled: !project.webhook_secret,
    },
    {
      label: 'GitHub Webhook',
      value: getWebhookEndpoint('github') || 'Not configured',
      icon: <Webhook className="w-4 h-4" />,
      type: 'copy',
      key: 'webhook_github',
      disabled: !project.webhook_endpoint_id,
    },
    {
      label: 'GitLab Webhook',
      value: getWebhookEndpoint('gitlab') || 'Not configured',
      icon: <Webhook className="w-4 h-4" />,
      type: 'copy',
      key: 'webhook_gitlab',
      disabled: !project.webhook_endpoint_id,
    },
    {
      label: 'Health Check URL',
      value: project.healthcheck_url || 'Not configured',
      icon: <Activity className="w-4 h-4" />,
      type: 'open',
      key: 'health_url',
      href: project.healthcheck_url || undefined,
      disabled: !project.healthcheck_url,
    },
    {
      label: 'Git Repository',
      value: project.git_repo,
      icon: <GitCommit className="w-4 h-4" />,
      type: 'open',
      key: 'repo_url',
      href: getRepoUrl() || undefined,
      disabled: !getRepoUrl(),
    },
  ];

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
          <Sparkles className="w-5 h-5 text-yellow-500" />
          Quick Actions
        </h2>
      </div>
      <div className="card p-3 space-y-1">
        {actions.map((action) => (
          <QuickActionButton
            key={action.key}
            item={action}
            onCopy={onCopy}
            copiedKey={copiedKey}
          />
        ))}

        {lastFailedDeployment && (
          <div className="border-t pt-3 mt-3">
            <div className="text-xs text-gray-500 mb-2">Recent Issues</div>
            <QuickActionButton
              item={{
                label: 'Last Error Code',
                value: lastFailedDeployment.error_code || 'unknown',
                icon: <AlertTriangle className="w-4 h-4 text-red-500" />,
                type: 'copy',
                key: 'last_error_code',
                disabled: !lastFailedDeployment.error_code,
              }}
              onCopy={onCopy}
              copiedKey={copiedKey}
            />
            <QuickActionButton
              item={{
                label: 'Jump to Failed Deployment',
                value: `Deployment #${lastFailedDeployment.id}`,
                icon: <XCircle className="w-4 h-4 text-red-500" />,
                type: 'jump',
                key: 'jump_failed_deployment',
                href: `/deployments/${lastFailedDeployment.id}`,
              }}
              onCopy={onCopy}
              copiedKey={copiedKey}
            />
          </div>
        )}

        {lastSuccessDeployment && (
          <div className="border-t pt-3 mt-3">
            <div className="text-xs text-gray-500 mb-2">Stable Version</div>
            <QuickActionButton
              item={{
                label: 'Last Success Commit',
                value: lastSuccessDeployment.commit_hash
                  ? lastSuccessDeployment.commit_hash.substring(0, 12)
                  : 'unknown',
                icon: <CheckCircle2 className="w-4 h-4 text-green-500" />,
                type: 'copy',
                key: 'last_success_commit',
                disabled: !lastSuccessDeployment.commit_hash,
              }}
              onCopy={onCopy}
              copiedKey={copiedKey}
            />
          </div>
        )}
      </div>
    </div>
  );
}

function TimelineEventItem({ event }: { event: TimelineEvent }) {
  const Icon = getTimelineEventIcon(event.type);
  const style = getTimelineEventStyle(event.type);
  const deploymentId = event.metadata?.deployment_id;

  const content = (
    <div className={`pl-6 pb-4 border-l-2 ${style.borderColor} relative`}>
      <div className={`absolute -left-3 top-0 w-6 h-6 rounded-full ${style.iconBg} flex items-center justify-center ring-2 ring-white`}>
        <Icon className={`w-3.5 h-3.5 ${style.iconColor}`} />
      </div>
      
      <div className={`card p-4 ${style.important ? 'ring-1 ring-red-200 bg-red-50/30' : ''}`}>
        <div className="flex items-start justify-between gap-2">
          <div className="flex-1">
            <div className="flex items-center gap-2 flex-wrap">
              <h4 className={`text-sm font-medium ${style.important ? 'text-red-800' : 'text-gray-900'}`}>
                {event.title}
              </h4>
            </div>
            {event.summary && (
              <p className="text-xs text-gray-500 mt-1">{event.summary}</p>
            )}
            {event.actor && (
              <p className="text-xs text-gray-400 mt-1 flex items-center gap-1">
                <User className="w-3 h-3" />
                {event.actor}
              </p>
            )}
          </div>
          <span className="text-xs text-gray-400 whitespace-nowrap">
            {formatDate(event.occurred_at)}
          </span>
        </div>
      </div>
    </div>
  );

  if (deploymentId) {
    return (
      <Link href={`/deployments/${deploymentId}`} className="block group">
        <div className="group-hover:opacity-80 transition-opacity">
          {content}
        </div>
      </Link>
    );
  }

  return content;
}

export default function ProjectDetailPage() {
  const params = useParams();
  const router = useRouter();
  const projectId = Number(params.id);

  const [project, setProject] = useState<Project | null>(null);
  const [projectStatus, setProjectStatus] = useState<ProjectStatus | null>(null);
  const [deployments, setDeployments] = useState<Deployment[]>([]);
  const [showAllDeployments, setShowAllDeployments] = useState(false);
  const [flags, setFlags] = useState<FeatureFlag[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deploying, setDeploying] = useState(false);

  const [showEditForm, setShowEditForm] = useState(false);
  const [editFormData, setEditFormData] = useState<ProjectUpdate>({});
  const [editComposeProfilesText, setEditComposeProfilesText] = useState('');
  const [savingEdit, setSavingEdit] = useState(false);

  const [showRunbookForm, setShowRunbookForm] = useState(false);
  const [runbookFormData, setRunbookFormData] = useState<ProjectUpdate>({});
  const [savingRunbook, setSavingRunbook] = useState(false);

  const [showNewToken, setShowNewToken] = useState<string | null>(null);
  const [copiedToken, setCopiedToken] = useState(false);

  const [showWebhookForm, setShowWebhookForm] = useState(false);
  const [webhookSecret, setWebhookSecret] = useState('');
  const [generatingWebhookSecret, setGeneratingWebhookSecret] = useState(false);

  const [showFlagForm, setShowFlagForm] = useState(false);
  const [flagFormData, setFlagFormData] = useState({
    key: '',
    enabled: false,
    description: '',
  });
  const [savingFlag, setSavingFlag] = useState(false);
  const [includeArchivedFlags, setIncludeArchivedFlags] = useState(false);

  const [timelineEvents, setTimelineEvents] = useState<TimelineEvent[]>([]);
  const [timelineTotal, setTimelineTotal] = useState(0);
  const [timelineLoading, setTimelineLoading] = useState(false);
  const [timelineFilter, setTimelineFilter] = useState<TimelineEventType | null>(null);
  const [showTimelineFilter, setShowTimelineFilter] = useState(false);

  const [notificationChannels, setNotificationChannels] = useState<NotificationChannel[]>([]);
  const [notificationSettings, setNotificationSettings] = useState<NotificationSetting[]>([]);
  const [notificationDeliveries, setNotificationDeliveries] = useState<NotificationDelivery[]>([]);
  const [notificationsLoading, setNotificationsLoading] = useState(false);

  const [showNewChannelForm, setShowNewChannelForm] = useState(false);
  const [newChannelFormData, setNewChannelFormData] = useState({
    name: '',
    channel_type: 'webhook' as ChannelType,
    is_active: true,
    config: {} as Record<string, any>,
  });
  const [savingChannel, setSavingChannel] = useState(false);

  const [expandedSettingId, setExpandedSettingId] = useState<number | null>(null);

  const [testingChannelId, setTestingChannelId] = useState<number | null>(null);

  const [copiedItem, setCopiedItem] = useState<string | null>(null);

  const [healthHistoryRecords, setHealthHistoryRecords] = useState<HealthHistoryRecord[]>([]);
  const [healthDeploymentMarkers, setHealthDeploymentMarkers] = useState<DeploymentMarker[]>([]);
  const [healthHistoryLoading, setHealthHistoryLoading] = useState(false);
  const [healthTimeRange, setHealthTimeRange] = useState<TimeRange>('24h');

  const [targets, setTargets] = useState<ProjectTarget[]>([]);
  const [targetsLoading, setTargetsLoading] = useState(false);
  const [showAddTargetForm, setShowAddTargetForm] = useState(false);
  const [addTargetFormData, setAddTargetFormData] = useState<ProjectTargetCreate>({
    agent_id: '',
    name: '',
    role: 'secondary',
    enabled: true,
    order_index: 0,
  });
  const [savingTarget, setSavingTarget] = useState(false);

  const [onboardingStatus, setOnboardingStatus] = useState<OnboardingStatusResponse | null>(null);
  const [onboardingLoading, setOnboardingLoading] = useState(false);
  const [installCommand, setInstallCommand] = useState<InstallCommandResponse | null>(null);
  const [installCommandLoading, setInstallCommandLoading] = useState(false);
  const [installPlatform, setInstallPlatform] = useState<TargetPlatform>('linux-systemd');
  const [showOnboardingModal, setShowOnboardingModal] = useState(false);
  const [deployMode, setDeployMode] = useState<'all-at-once' | 'rolling'>('all-at-once');
  const [showDeployModal, setShowDeployModal] = useState(false);

  const handleCopyWithFeedback = async (text: string, itemKey: string) => {
    try {
      await copyToClipboard(text);
      setCopiedItem(itemKey);
      setTimeout(() => setCopiedItem(null), 2000);
    } catch (err: any) {
      console.error('Failed to copy:', err);
    }
  };

  const loadNotifications = useCallback(async () => {
    try {
      setNotificationsLoading(true);
      const [channels, settings, deliveries] = await Promise.all([
        api.listNotificationChannels(projectId),
        api.listNotificationSettings(projectId),
        api.listNotificationDeliveries(projectId, undefined, undefined, 30),
      ]);
      setNotificationChannels(channels);
      setNotificationSettings(settings);
      setNotificationDeliveries(deliveries);
    } catch (err: any) {
      // Silently fail for notifications
    } finally {
      setNotificationsLoading(false);
    }
  }, [projectId]);

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const [projectData, deploymentsData, flagsData] = await Promise.all([
        api.getProject(projectId),
        api.listDeployments(projectId),
        api.listFlags(projectId, includeArchivedFlags),
      ]);
      setProject(projectData);
      setDeployments(deploymentsData);
      setFlags(flagsData);
      setError(null);
    } catch (err: any) {
      setError(err.message || 'Failed to load project');
    } finally {
      setLoading(false);
    }
  }, [projectId, includeArchivedFlags]);

  const loadStatus = useCallback(async () => {
    try {
      const statusData = await api.getProjectStatus(projectId);
      setProjectStatus(statusData);
    } catch (err: any) {
      // Silently fail for status - don't show error in main UI
    }
  }, [projectId]);

  const loadTimeline = useCallback(async () => {
    try {
      setTimelineLoading(true);
      const data = await api.getProjectTimeline(projectId, {
        limit: 50,
        event_type: timelineFilter || undefined,
      });
      setTimelineEvents(data.events);
      setTimelineTotal(data.total);
    } catch (err: any) {
      // Silently fail for timeline
    } finally {
      setTimelineLoading(false);
    }
  }, [projectId, timelineFilter]);

  const loadTargets = useCallback(async () => {
    try {
      setTargetsLoading(true);
      const data = await api.listProjectTargets(projectId);
      setTargets(data);
    } catch (err: any) {
      // Silently fail for targets
    } finally {
      setTargetsLoading(false);
    }
  }, [projectId]);

  const loadOnboarding = useCallback(async () => {
    try {
      setOnboardingLoading(true);
      const data = await api.getOnboardingStatus(projectId);
      setOnboardingStatus(data);
    } catch (err: any) {
      // Silently fail for onboarding
    } finally {
      setOnboardingLoading(false);
    }
  }, [projectId]);

  const handleGenerateInstallCommand = async (platform?: TargetPlatform) => {
    try {
      setInstallCommandLoading(true);
      const platformToUse = platform || installPlatform;
      const data = await api.generateInstallCommand(projectId, {
        target_platform: platformToUse,
      });
      setInstallCommand(data);
      setInstallPlatform(platformToUse);
    } catch (err: any) {
      console.error('Failed to generate install command:', err);
    } finally {
      setInstallCommandLoading(false);
    }
  };

  const handleCreateTarget = async () => {
    try {
      setSavingTarget(true);
      if (!addTargetFormData.agent_id.trim()) {
        throw new Error('Agent ID is required');
      }
      const newTarget = await api.createProjectTarget(projectId, {
        ...addTargetFormData,
        name: addTargetFormData.name || `target-${Date.now()}`,
      });
      setTargets((prev) => [...prev, newTarget]);
      setShowAddTargetForm(false);
      setAddTargetFormData({
        agent_id: '',
        name: '',
        role: 'secondary',
        enabled: true,
        order_index: targets.length,
      });
    } catch (err: any) {
      console.error('Failed to create target:', err);
      alert(err.message || 'Failed to create target');
    } finally {
      setSavingTarget(false);
    }
  };

  const handleToggleTarget = async (targetId: number, enabled: boolean) => {
    try {
      const updated = await api.updateProjectTarget(projectId, targetId, { enabled });
      setTargets((prev) =>
        prev.map((t) => (t.id === targetId ? updated : t))
      );
    } catch (err: any) {
      console.error('Failed to update target:', err);
      alert(err.message || 'Failed to update target');
    }
  };

  const handleDeleteTarget = async (targetId: number) => {
    if (!confirm('Are you sure you want to delete this deployment target?')) {
      return;
    }
    try {
      await api.deleteProjectTarget(projectId, targetId);
      setTargets((prev) => prev.filter((t) => t.id !== targetId));
    } catch (err: any) {
      console.error('Failed to delete target:', err);
      alert(err.message || 'Failed to delete target');
    }
  };

  const handleTimeRangeChange = useCallback((range: TimeRange) => {
    setHealthTimeRange(range);
  }, []);

  useEffect(() => {
    loadData();
    loadStatus();
    loadTimeline();
    loadNotifications();
    loadTargets();
    loadOnboarding();
  }, [loadData, loadStatus, loadTimeline, loadNotifications, loadTargets, loadOnboarding]);

  useEffect(() => {
    let active = true;
    setHealthHistoryLoading(true);
    api.getProjectHealthHistory(projectId, healthTimeRange)
      .then((data) => {
        if (!active) return;
        setHealthHistoryRecords(data.records);
        setHealthDeploymentMarkers(data.deployment_markers);
      })
      .catch(() => {
        // Keep the previous chart if the refresh fails.
      })
      .finally(() => {
        if (active) setHealthHistoryLoading(false);
      });
    return () => { active = false; };
  }, [projectId, healthTimeRange]);

  useEffect(() => {
    const interval = setInterval(() => {
      loadStatus();
      loadOnboarding();
    }, 10000);
    return () => clearInterval(interval);
  }, [loadStatus, loadOnboarding]);

  async function handleDeploy(mode?: 'all-at-once' | 'rolling') {
    try {
      setDeploying(true);
      const deployModeToUse = mode || deployMode;
      await api.deployProject(projectId, undefined, deployModeToUse);
      setShowDeployModal(false);
      loadData();
    } catch (err: any) {
      setError(err.message || 'Failed to deploy');
    } finally {
      setDeploying(false);
    }
  }

  async function handleRollback(targetDeploymentId: number) {
    try {
      setDeploying(true);
      await api.rollbackProject(projectId, targetDeploymentId);
      loadData();
    } catch (err: any) {
      setError(err.message || 'Failed to rollback');
    } finally {
      setDeploying(false);
    }
  }

  async function handleRollbackToLastSuccess() {
    try {
      setDeploying(true);
      await api.rollbackToLastSuccess(projectId);
      loadData();
    } catch (err: any) {
      setError(err.message || 'Failed to rollback to last success');
    } finally {
      setDeploying(false);
    }
  }

  async function handleRetryLastFailed() {
    if (!lastFailedDeployment) return;
    try {
      setDeploying(true);
      await api.retryDeployment(lastFailedDeployment.id);
      loadData();
    } catch (err: any) {
      setError(err.message || 'Failed to retry deployment');
    } finally {
      setDeploying(false);
    }
  }

  function handleOpenEditForm() {
    if (!project) return;
    setEditFormData({
      name: project.name,
      environment: project.environment || null,
      git_repo: project.git_repo,
      git_branch: project.git_branch,
      git_credential_type: project.git_credential_type || 'none',
      git_credential_username: project.git_credential_username || '',
      git_credential_token: '',
      git_credential_ssh_private_key: '',
      git_credential_ssh_known_hosts: '',
      deploy_workdir: project.deploy_workdir,
      compose_file: project.compose_file,
      compose_service: project.compose_service,
      deploy_strategy: project.deploy_strategy,
      healthcheck_url: project.healthcheck_url,
      healthcheck_timeout_seconds: project.healthcheck_timeout_seconds,
      healthcheck_expected_status: project.healthcheck_expected_status,
      flags_file_path: project.flags_file_path,
      migration_service: project.migration_service,
      migration_command: project.migration_command,
      migration_timeout_seconds: project.migration_timeout_seconds,
      migration_no_deps: project.migration_no_deps,
      build_timeout_seconds: project.build_timeout_seconds,
      pull_timeout_seconds: project.pull_timeout_seconds,
      build_no_cache: project.build_no_cache,
    });
    setEditComposeProfilesText((project.compose_profiles || []).join(', '));
    setShowEditForm(true);
  }

  function handleOpenRunbookEdit() {
    if (!project) return;
    setRunbookFormData({
      notes: project.notes || '',
      release_notes_hint: project.release_notes_hint || '',
      troubleshooting_hint: project.troubleshooting_hint || '',
      admin_url: project.admin_url || '',
      metrics_url: project.metrics_url || '',
      logs_url: project.logs_url || '',
      ssh_hint: project.ssh_hint || '',
    });
    setShowRunbookForm(true);
  }

  async function handleSaveEdit(e: React.FormEvent) {
    e.preventDefault();
    try {
      setSavingEdit(true);
      const payload: ProjectUpdate = {
        ...editFormData,
        healthcheck_url: editFormData.healthcheck_url || null,
        migration_service: (editFormData.migration_service || '').trim(),
        migration_command: (editFormData.migration_command || '').trim() || null,
        compose_profiles: editComposeProfilesText
          .split(',')
          .map((item) => item.trim())
          .filter(Boolean),
      };
      const updated = await api.updateProject(projectId, payload);
      setProject(updated);
      setShowEditForm(false);
      loadData();
    } catch (err: any) {
      setError(err.message || 'Failed to update project');
    } finally {
      setSavingEdit(false);
    }
  }

  async function handleSaveRunbook(e: React.FormEvent) {
    e.preventDefault();
    try {
      setSavingRunbook(true);
      const updated = await api.updateProject(projectId, runbookFormData);
      setProject(updated);
      setShowRunbookForm(false);
      loadData();
    } catch (err: any) {
      setError(err.message || 'Failed to update runbook');
    } finally {
      setSavingRunbook(false);
    }
  }

  async function handleRotateToken() {
    if (!confirm('Are you sure? The old token will be invalidated immediately.')) {
      return;
    }
    try {
      const result = await api.rotateAgentToken(projectId);
      setShowNewToken(result.agent_token);
      setCopiedToken(false);
      loadData();
    } catch (err: any) {
      setError(err.message || 'Failed to rotate token');
    }
  }

  async function handleCopyToken() {
    if (!showNewToken) return;
    await copyToClipboard(showNewToken);
    setCopiedToken(true);
    setTimeout(() => setCopiedToken(false), 2000);
  }

  async function handleGenerateWebhookSecret() {
    try {
      setGeneratingWebhookSecret(true);
      const result = await api.generateWebhookSecret(projectId);
      setWebhookSecret(result.webhook_secret);
      loadData();
    } catch (err: any) {
      setError(err.message || 'Failed to generate webhook secret');
    } finally {
      setGeneratingWebhookSecret(false);
    }
  }

  async function handleToggleFlag(flag: FeatureFlag) {
    const newEnabled = !flag.enabled;
    setFlags((prev) =>
      prev.map((f) =>
        f.id === flag.id ? { ...f, enabled: newEnabled } : f,
      ),
    );

    try {
      await api.updateFlag(flag.id, { enabled: newEnabled });
      const freshFlags = await api.listFlags(projectId, includeArchivedFlags);
      setFlags(freshFlags);
    } catch (err: any) {
      setFlags((prev) =>
        prev.map((f) =>
          f.id === flag.id ? { ...f, enabled: flag.enabled } : f,
        ),
      );
      setError(err.message || 'Failed to update flag');
    }
  }

  async function handleArchiveFlag(flag: FeatureFlag) {
    if (!confirm(`Archive flag "${flag.key}"?`)) return;
    try {
      await api.archiveFlag(flag.id);
      loadData();
    } catch (err: any) {
      setError(err.message || 'Failed to archive flag');
    }
  }

  async function handleUnarchiveFlag(flag: FeatureFlag) {
    try {
      await api.unarchiveFlag(flag.id);
      loadData();
    } catch (err: any) {
      setError(err.message || 'Failed to unarchive flag');
    }
  }

  async function handleDeleteFlag(flag: FeatureFlag) {
    if (
      !confirm(
        `Delete flag "${flag.key}"? This cannot be undone. Use archive instead if you might need it later.`,
      )
    )
      return;
    try {
      await api.deleteFlag(flag.id);
      loadData();
    } catch (err: any) {
      setError(err.message || 'Failed to delete flag');
    }
  }

  async function handleCreateFlag(e: React.FormEvent) {
    e.preventDefault();
    try {
      setSavingFlag(true);
      await api.createFlag(projectId, flagFormData);
      setShowFlagForm(false);
      setFlagFormData({ key: '', enabled: false, description: '' });
      loadData();
    } catch (err: any) {
      setError(err.message || 'Failed to create flag');
    } finally {
      setSavingFlag(false);
    }
  }

  async function handleCreateChannel(e: React.FormEvent) {
    e.preventDefault();
    try {
      setSavingChannel(true);
      await api.createNotificationChannel(projectId, newChannelFormData);
      setShowNewChannelForm(false);
      setNewChannelFormData({
        name: '',
        channel_type: 'webhook',
        is_active: true,
        config: {},
      });
      loadNotifications();
    } catch (err: any) {
      setError(err.message || 'Failed to create notification channel');
    } finally {
      setSavingChannel(false);
    }
  }

  async function handleDeleteChannel(channel: NotificationChannel) {
    if (!confirm(`Delete notification channel "${channel.name}"?`)) return;
    try {
      await api.deleteNotificationChannel(channel.id);
      loadNotifications();
    } catch (err: any) {
      setError(err.message || 'Failed to delete channel');
    }
  }

  async function handleToggleChannel(channel: NotificationChannel) {
    try {
      await api.updateNotificationChannel(channel.id, {
        is_active: !channel.is_active,
      });
      loadNotifications();
    } catch (err: any) {
      setError(err.message || 'Failed to toggle channel');
    }
  }

  async function handleTestChannel(channel: NotificationChannel) {
    try {
      setTestingChannelId(channel.id);
      const result = await api.testNotificationChannel(channel.id, 'deployment_success');
      loadNotifications();
      if (!result.success) {
        setError(result.message || 'Test notification failed');
      }
    } catch (err: any) {
      setError(err.message || 'Failed to send test notification');
    } finally {
      setTestingChannelId(null);
    }
  }

  async function handleUpdateSetting(setting: NotificationSetting, updates: { enabled?: boolean; channel_ids?: number[]; cooldown_seconds?: number; send_recovery?: boolean }) {
    try {
      await api.updateNotificationSetting(setting.id, updates);
      loadNotifications();
    } catch (err: any) {
      setError(err.message || 'Failed to update notification setting');
    }
  }

  function getEventTypeName(eventType: NotificationEventType): string {
    const names: Record<NotificationEventType, string> = {
      deployment_success: '部署成功',
      deployment_failed: '部署失败',
      agent_offline: 'Agent 离线',
      health_degraded: '健康状态降级',
      health_unhealthy: '服务异常',
      health_recovered: '服务恢复',
    };
    return names[eventType] || eventType;
  }

  function getChannelTypeName(channelType: ChannelType): string {
    const names: Record<ChannelType, string> = {
      webhook: 'Webhook',
      feishu: '飞书',
      slack: 'Slack',
    };
    return names[channelType] || channelType;
  }

  const lastSuccessDeployment = deployments.find((d) => d.status === 'success');
  const lastFailedDeployment = deployments.find((d) => d.status === 'failed');

  if (loading) {
    return (
      <AppLayout>
        <div className="p-8 text-center text-gray-500">Loading...</div>
      </AppLayout>
    );
  }

  if (!project) {
    return (
      <AppLayout>
        <div className="p-8 text-center text-red-500">
          {error || 'Project not found'}
        </div>
      </AppLayout>
    );
  }

  return (
    <AppLayout>
      <div className="p-8 max-w-7xl">
        <div className="mb-8">
          <Link
            href="/projects"
            className="inline-flex items-center text-sm text-gray-600 hover:text-gray-900 mb-4"
          >
            <ArrowLeft className="w-4 h-4 mr-1" />
            Back to projects
          </Link>

          <div className="flex items-start justify-between">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">{project.name}</h1>
              <div className="mt-2 flex items-center gap-3 text-sm text-gray-600">
                <code className="bg-gray-100 px-2 py-0.5 rounded text-xs">
                  {project.deploy_strategy}
                </code>
                <span className="font-mono">{project.git_repo}</span>
              </div>
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => setShowDeployModal(true)}
                disabled={deploying}
                className="btn btn-primary"
              >
                <Play className="w-4 h-4 mr-2" />
                {deploying ? 'Deploying...' : 'Deploy'}
              </button>
              {lastFailedDeployment && (
                <button
                  onClick={handleRetryLastFailed}
                  disabled={deploying}
                  className="btn btn-secondary"
                >
                  <RotateCcw className="w-4 h-4 mr-2" />
                  Retry
                </button>
              )}
              {lastSuccessDeployment && (
                <button
                  onClick={handleRollbackToLastSuccess}
                  disabled={deploying}
                  className="btn btn-secondary"
                  title={`Rollback to #${lastSuccessDeployment.id}`}
                >
                  <RotateCcw className="w-4 h-4 mr-2" />
                  Rollback
                </button>
              )}
            </div>
          </div>
        </div>

        {error && (
          <div className="mb-6 text-red-600 text-sm bg-red-50 px-4 py-3 rounded-md">
            {error}
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          <div className="space-y-8">
            {projectStatus && (
              <div>
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
                    <Activity className="w-5 h-5" />
                    Health
                  </h2>
                  <span className="text-xs text-gray-500">
                    Auto-refreshes every 10s
                  </span>
                </div>
                <div className="card p-6">
                  <div className="grid grid-cols-2 gap-4 mb-4">
                    <div>
                      <span className="text-xs text-gray-500 block">Status</span>
                      <StatusBadge
                        status={projectStatus.health_status}
                      />
                    </div>
                    <div>
                      <span className="text-xs text-gray-500 block">
                        Agent Last Seen
                      </span>
                      <span className="text-sm font-mono">
                        {formatDate(projectStatus.agent_last_seen_at)}
                      </span>
                    </div>
                  </div>

                  <div className="grid grid-cols-3 gap-4 mb-4">
                    <div className="bg-gray-50 rounded p-3">
                      <div className="flex items-center gap-2 text-gray-600 text-xs mb-1">
                        <Cpu className="w-3 h-3" />
                        CPU
                      </div>
                      <span className="text-lg font-mono font-semibold">
                        {projectStatus.cpu_percent != null
                          ? `${projectStatus.cpu_percent}%`
                          : '—'}
                      </span>
                    </div>
                    <div className="bg-gray-50 rounded p-3">
                      <div className="flex items-center gap-2 text-gray-600 text-xs mb-1">
                        <HardDrive className="w-3 h-3" />
                        Memory
                      </div>
                      <span className="text-sm font-mono font-semibold">
                        {projectStatus.mem_used_mb != null &&
                        projectStatus.mem_total_mb != null
                          ? `${projectStatus.mem_used_mb}/${projectStatus.mem_total_mb} MB`
                          : '—'}
                      </span>
                    </div>
                    <div className="bg-gray-50 rounded p-3">
                      <div className="flex items-center gap-2 text-gray-600 text-xs mb-1">
                        <Server className="w-3 h-3" />
                        Disk
                      </div>
                      <span className="text-lg font-mono font-semibold">
                        {projectStatus.disk_used_percent != null
                          ? `${projectStatus.disk_used_percent}%`
                          : '—'}
                      </span>
                    </div>
                  </div>

                  {projectStatus.current_commit_hash && (
                    <div className="border-t pt-4 mt-4">
                      <span className="text-xs text-gray-500 block mb-1">
                        Current Commit
                      </span>
                      <code className="font-mono text-sm bg-gray-100 px-2 py-1 rounded">
                        {projectStatus.current_commit_hash}
                      </code>
                    </div>
                  )}

                  {projectStatus.agent_version && (
                    <div className="border-t pt-4 mt-4">
                      <span className="text-xs text-gray-500 block mb-2">
                        Agent Version
                      </span>
                      <div className="flex items-center gap-3">
                        <code className="font-mono text-sm bg-gray-100 px-2 py-1 rounded">
                          v{projectStatus.agent_version}
                        </code>
                        {projectStatus.agent_version_outdated ? (
                          <div className="flex items-center gap-2">
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-orange-100 text-orange-800">
                              <AlertTriangle className="w-3 h-3" />
                              版本落后
                            </span>
                            <div className="text-xs text-gray-500">
                              建议升级到最新版本以获得新功能和安全修复
                            </div>
                          </div>
                        ) : (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800">
                            <CheckCircle2 className="w-3 h-3" />
                            最新版本
                          </span>
                        )}
                      </div>

                      {projectStatus.agent_version_outdated && (
                        <div className="mt-3 p-3 bg-orange-50 border border-orange-200 rounded-md">
                          <div className="flex items-start gap-2">
                            <AlertCircle className="w-4 h-4 text-orange-600 flex-shrink-0 mt-0.5" />
                            <div className="flex-1">
                              <p className="text-sm font-medium text-orange-800 mb-1">
                                需要升级 Agent
                              </p>
                              <p className="text-xs text-orange-700 mb-2">
                                您的 Agent 版本 v{projectStatus.agent_version} 可能缺少重要的安全更新和功能改进。
                              </p>
                              <div className="text-xs text-orange-600">
                                <p className="font-medium mb-1">升级步骤：</p>
                                <ol className="list-decimal list-inside space-y-0.5">
                                  <li>SSH 登录到部署服务器</li>
                                  <li>停止 Agent 服务：<code className="bg-orange-100 px-1 rounded">systemctl stop shipsmith-agent</code></li>
                                  <li>更新 pip 包：<code className="bg-orange-100 px-1 rounded">pip install --upgrade shipsmith-agent</code></li>
                                  <li>重新启动服务：<code className="bg-orange-100 px-1 rounded">systemctl start shipsmith-agent</code></li>
                                </ol>
                              </div>
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  {projectStatus.containers &&
                    projectStatus.containers.length > 0 && (
                      <div className="border-t pt-4 mt-4">
                        <span className="text-xs text-gray-500 block mb-2">
                          Containers
                        </span>
                        <div className="space-y-2">
                          {projectStatus.containers.map((container, idx) => (
                            <div
                              key={idx}
                              className="flex items-center justify-between text-sm"
                            >
                              <span className="font-mono">{container.service}</span>
                              <StatusBadge
                                status={
                                  container.status === 'running'
                                    ? 'healthy'
                                    : container.status === 'exited'
                                      ? 'failed'
                                      : 'unknown'
                                }
                                small
                              />
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                  {projectStatus.app_health && (
                    <div className="border-t pt-4 mt-4">
                      <span className="text-xs text-gray-500 block mb-2">
                        App Health Check
                      </span>
                      <div className="flex items-center gap-3 text-sm">
                        <StatusBadge
                          status={
                            projectStatus.app_health.status === 'healthy'
                              ? 'healthy'
                              : projectStatus.app_health.status === 'degraded'
                                ? 'degraded'
                                : 'unhealthy'
                          }
                          small
                        />
                        {projectStatus.app_health.response_ms && (
                          <span className="text-gray-600">
                            {projectStatus.app_health.response_ms}ms
                          </span>
                        )}
                        {projectStatus.app_health.http_status && (
                          <span className="text-gray-600">
                            HTTP {projectStatus.app_health.http_status}
                          </span>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}

            <HealthTrendChart
              records={healthHistoryRecords}
              deploymentMarkers={healthDeploymentMarkers}
              timeRange={healthTimeRange}
              loading={healthHistoryLoading}
              onTimeRangeChange={handleTimeRangeChange}
            />

            <QuickActionsSection
              project={project}
              projectStatus={projectStatus}
              lastSuccessDeployment={lastSuccessDeployment}
              lastFailedDeployment={lastFailedDeployment}
              onCopy={handleCopyWithFeedback}
              copiedKey={copiedItem}
            />

            <div>
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
                  <Settings className="w-5 h-5" />
                  Project Configuration
                </h2>
                <button
                  onClick={handleOpenEditForm}
                  className="btn btn-secondary text-sm"
                >
                  <Settings className="w-4 h-4 mr-2" />
                  Edit
                </button>
              </div>
              <div className="card p-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-1">
                    <div className="flex items-center gap-1">
                      <span className="text-gray-500 text-xs font-medium">Git Repository</span>
                      <span className="text-xs text-gray-400">(代码仓库地址)</span>
                    </div>
                    <code className="font-mono text-sm">{project.git_repo}</code>
                    <p className="text-xs text-gray-400">
                      ShipSmith 从这里拉取代码进行部署
                    </p>
                  </div>
                  <div className="space-y-1">
                    <div className="flex items-center gap-1">
                      <span className="text-gray-500 text-xs font-medium">Branch</span>
                      <span className="text-xs text-gray-400">(部署分支)</span>
                    </div>
                    <code className="font-mono text-sm">{project.git_branch}</code>
                    <p className="text-xs text-gray-400">
                      默认从该分支拉取最新代码
                    </p>
                  </div>
                  <div className="space-y-1">
                    <div className="flex items-center gap-1">
                      <span className="text-gray-500 text-xs font-medium">Deploy Workdir</span>
                      <span className="text-xs text-gray-400">(部署工作目录)</span>
                    </div>
                    <code className="font-mono text-sm">{project.deploy_workdir}</code>
                    <p className="text-xs text-gray-400">
                      Agent 在服务器上执行部署命令的目录，必须存在且有读写权限
                    </p>
                  </div>
                  <div className="space-y-1">
                    <div className="flex items-center gap-1">
                      <span className="text-gray-500 text-xs font-medium">Compose File</span>
                      <span className="text-xs text-gray-400">(Docker Compose 文件)</span>
                    </div>
                    <code className="font-mono text-sm">{project.compose_file}</code>
                    <p className="text-xs text-gray-400">
                      相对于工作目录的 docker-compose.yml 路径
                    </p>
                  </div>
                  <div className="space-y-1">
                    <div className="flex items-center gap-1">
                      <span className="text-gray-500 text-xs font-medium">Compose Service</span>
                      <span className="text-xs text-gray-400">(主服务名)</span>
                    </div>
                    <code className="font-mono text-sm">{project.compose_service}</code>
                    <p className="text-xs text-gray-400">
                      docker-compose.yml 中定义的主要应用服务，用于健康检查判定
                    </p>
                  </div>
                  <div className="space-y-1">
                    <div className="flex items-center gap-1">
                      <span className="text-gray-500 text-xs font-medium">Health Check URL</span>
                      <span className="text-xs text-gray-400">(健康检查地址)</span>
                    </div>
                    <code className="font-mono text-sm">
                      {project.healthcheck_url || '—'}
                    </code>
                    <p className="text-xs text-gray-400">
                      Agent 调用此端点判断应用是否正常运行，建议返回 200 OK
                    </p>
                  </div>
                  <div className="space-y-1">
                    <div className="flex items-center gap-1">
                      <span className="text-gray-500 text-xs font-medium">Flags File Path</span>
                      <span className="text-xs text-gray-400">(功能开关文件)</span>
                    </div>
                    <code className="font-mono text-sm">{project.flags_file_path}</code>
                    <p className="text-xs text-gray-400">
                      功能开关 JSON 文件路径，应用可读取此文件控制功能开关
                    </p>
                  </div>
                  <div className="space-y-1">
                    <div className="flex items-center gap-1">
                      <span className="text-gray-500 text-xs font-medium">Deploy Strategy</span>
                      <span className="text-xs text-gray-400">(部署策略)</span>
                    </div>
                    <code className="font-mono text-sm">{project.deploy_strategy}</code>
                    <p className="text-xs text-gray-400">
                      compose-build: 构建镜像后部署 | compose-pull: 直接拉取镜像
                    </p>
                  </div>
                  <div className="space-y-1">
                    <div className="flex items-center gap-1">
                      <span className="text-gray-500 text-xs font-medium">Health Expected Status</span>
                      <span className="text-xs text-gray-400">(健康检查期望状态码)</span>
                    </div>
                    <code className="font-mono text-sm">{project.healthcheck_expected_status}</code>
                    <p className="text-xs text-gray-400">
                      Agent 每次心跳按此状态码判定应用健康
                    </p>
                  </div>
                  <div className="space-y-1">
                    <div className="flex items-center gap-1">
                      <span className="text-gray-500 text-xs font-medium">Migration</span>
                      <span className="text-xs text-gray-400">(构建后迁移)</span>
                    </div>
                    <code className="font-mono text-sm">
                      {project.migration_command
                        ? `${project.migration_service}: ${project.migration_command}`
                        : '—'}
                    </code>
                    <p className="text-xs text-gray-400">
                      构建后、启动前执行；{project.migration_no_deps ? '不拉起依赖服务' : '允许拉起依赖服务'}，超时 {project.migration_timeout_seconds} 秒
                    </p>
                  </div>
                  <div className="space-y-1">
                    <div className="flex items-center gap-1">
                      <span className="text-gray-500 text-xs font-medium">Compose Profiles</span>
                      <span className="text-xs text-gray-400">(显式启用)</span>
                    </div>
                    <code className="font-mono text-sm">
                      {(project.compose_profiles || []).length > 0 ? project.compose_profiles.join(', ') : '—'}
                    </code>
                    <p className="text-xs text-gray-400">
                      部署时 docker compose 显式启用的 profile
                    </p>
                  </div>
                  <div className="space-y-1">
                    <div className="flex items-center gap-1">
                      <span className="text-gray-500 text-xs font-medium">Build Tuning</span>
                      <span className="text-xs text-gray-400">(构建调优)</span>
                    </div>
                    <code className="font-mono text-sm">
                      build {project.build_timeout_seconds}s / pull {project.pull_timeout_seconds}s{project.build_no_cache ? ' / no-cache' : ''}
                    </code>
                    <p className="text-xs text-gray-400">
                      构建与拉取超时；{project.build_no_cache ? '不使用' : '使用'} Docker 层缓存
                    </p>
                  </div>
                </div>
              </div>
            </div>

            <div>
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
                  <Key className="w-5 h-5" />
                  Agent Configuration
                </h2>
              </div>
              <div className="card p-4">
                <div className="mb-4">
                  <span className="text-gray-500 text-xs block">Agent ID</span>
                  <code className="font-mono text-sm">{project.agent_id}</code>
                </div>

                <button
                  onClick={handleRotateToken}
                  className="btn btn-secondary text-sm w-full"
                >
                  <RefreshCw className="w-4 h-4 mr-2" />
                  Rotate Agent Token
                </button>

                {showNewToken && (
                  <div className="mt-4 p-4 bg-yellow-50 border border-yellow-200 rounded-md">
                    <div className="flex items-center gap-2 text-yellow-800 text-sm mb-2">
                      <AlertTriangle className="w-4 h-4" />
                      <span className="font-medium">New Token Generated</span>
                    </div>
                    <p className="text-xs text-yellow-700 mb-3">
                      Copy this token now - it will only be shown once.
                    </p>
                    <div className="flex items-center gap-2">
                      <input
                        type="text"
                        value={showNewToken}
                        readOnly
                        className="input text-sm font-mono flex-1"
                      />
                      <button
                        onClick={handleCopyToken}
                        className="btn btn-primary text-sm"
                      >
                        {copiedToken ? (
                          <>
                            <Check className="w-4 h-4 mr-2" />
                            Copied
                          </>
                        ) : (
                          <>
                            <Copy className="w-4 h-4 mr-2" />
                            Copy
                          </>
                        )}
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>

            <div>
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
                  <Server className="w-5 h-5" />
                  Deployment Targets
                </h2>
                <button
                  onClick={() => setShowAddTargetForm(true)}
                  className="btn btn-primary text-sm"
                >
                  <Plus className="w-4 h-4 mr-2" />
                  Add Target
                </button>
              </div>
              <div className="card p-4">
                {targetsLoading ? (
                  <div className="flex items-center justify-center py-8">
                    <Loader2 className="w-6 h-6 animate-spin text-gray-400" />
                    <span className="ml-2 text-gray-500">Loading targets...</span>
                  </div>
                ) : targets.length === 0 ? (
                  <div className="text-center py-8 text-gray-500">
                    <Server className="w-12 h-12 mx-auto mb-3 text-gray-300" />
                    <p className="text-sm">No deployment targets configured</p>
                    <p className="text-xs mt-1">Add targets to deploy to multiple machines</p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {targets.map((target) => (
                      <div
                        key={target.id}
                        className="flex items-center justify-between p-3 border border-gray-200 rounded-lg hover:bg-gray-50"
                      >
                        <div className="flex-1">
                          <div className="flex items-center gap-2">
                            <span className="font-medium text-sm">{target.name}</span>
                            <span
                              className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                                target.enabled
                                  ? 'bg-green-100 text-green-700'
                                  : 'bg-gray-100 text-gray-600'
                              }`}
                            >
                              {target.enabled ? 'Enabled' : 'Disabled'}
                            </span>
                            <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-blue-50 text-blue-700">
                              {target.role}
                            </span>
                          </div>
                          <div className="flex items-center gap-4 mt-1 text-xs text-gray-500">
                            <span>Agent ID: {target.agent_id}</span>
                            <span>Order: {target.order_index}</span>
                            <span>
                              Created: {formatDate(target.created_at)}
                            </span>
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          <button
                            onClick={() => handleToggleTarget(target.id, !target.enabled)}
                            className="text-xs px-2 py-1 rounded border border-gray-300 hover:bg-gray-100"
                          >
                            {target.enabled ? 'Disable' : 'Enable'}
                          </button>
                          <button
                            onClick={() => handleDeleteTarget(target.id)}
                            className="text-xs px-2 py-1 rounded border border-red-200 text-red-600 hover:bg-red-50"
                          >
                            Delete
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {showAddTargetForm && (
                  <div className="mt-4 pt-4 border-t border-gray-200">
                    <h3 className="text-sm font-medium text-gray-700 mb-3">Add New Target</h3>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                      <div>
                        <label className="label">
                          Agent ID <span className="text-red-500">*</span>
                        </label>
                        <input
                          type="text"
                          className="input"
                          placeholder="e.g., agent-abc123"
                          value={addTargetFormData.agent_id}
                          onChange={(e) =>
                            setAddTargetFormData({
                              ...addTargetFormData,
                              agent_id: e.target.value,
                            })
                          }
                        />
                      </div>
                      <div>
                        <label className="label">Name</label>
                        <input
                          type="text"
                          className="input"
                          placeholder="e.g., server-01"
                          value={addTargetFormData.name}
                          onChange={(e) =>
                            setAddTargetFormData({
                              ...addTargetFormData,
                              name: e.target.value,
                            })
                          }
                        />
                      </div>
                      <div>
                        <label className="label">Role</label>
                        <select
                          className="input"
                          value={addTargetFormData.role}
                          onChange={(e) =>
                            setAddTargetFormData({
                              ...addTargetFormData,
                              role: e.target.value,
                            })
                          }
                        >
                          <option value="primary">Primary</option>
                          <option value="secondary">Secondary</option>
                          <option value="standby">Standby</option>
                        </select>
                      </div>
                      <div>
                        <label className="label">Order Index</label>
                        <input
                          type="number"
                          className="input"
                          placeholder="0"
                          value={addTargetFormData.order_index}
                          onChange={(e) =>
                            setAddTargetFormData({
                              ...addTargetFormData,
                              order_index: parseInt(e.target.value) || 0,
                            })
                          }
                        />
                      </div>
                    </div>
                    <div className="flex items-center gap-2 mt-4">
                      <button
                        onClick={handleCreateTarget}
                        disabled={savingTarget}
                        className="btn btn-primary text-sm"
                      >
                        {savingTarget ? (
                          <>
                            <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                            Saving...
                          </>
                        ) : (
                          <>
                            <Plus className="w-4 h-4 mr-2" />
                            Add Target
                          </>
                        )}
                      </button>
                      <button
                        onClick={() => setShowAddTargetForm(false)}
                        className="btn btn-secondary text-sm"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>

            <div>
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
                  <Rocket className="w-5 h-5" />
                  Agent Onboarding
                </h2>
                <button
                  onClick={() => setShowOnboardingModal(true)}
                  className="btn btn-primary text-sm"
                >
                  <Activity className="w-4 h-4 mr-2" />
                  Onboarding Guide
                </button>
              </div>
              <div className="card p-4">
                {onboardingLoading ? (
                  <div className="flex items-center justify-center py-6">
                    <Loader2 className="w-5 h-5 animate-spin text-gray-400" />
                  </div>
                ) : onboardingStatus ? (
                  <div className="space-y-4">
                    <div className="flex items-center gap-4">
                      <div
                        className={`w-12 h-12 rounded-full flex items-center justify-center ${
                          onboardingStatus.status === 'online'
                            ? 'bg-green-100'
                            : onboardingStatus.status === 'waiting'
                              ? 'bg-yellow-100'
                              : 'bg-red-100'
                        }`}
                      >
                        {onboardingStatus.status === 'online' ? (
                          <CheckCircle2 className="w-6 h-6 text-green-600" />
                        ) : onboardingStatus.status === 'waiting' ? (
                          <Clock className="w-6 h-6 text-yellow-600" />
                        ) : (
                          <XCircle className="w-6 h-6 text-red-600" />
                        )}
                      </div>
                      <div className="flex-1">
                        <div className="font-medium text-gray-900">
                          Agent Status: {onboardingStatus.status.toUpperCase()}
                        </div>
                        <div className="text-sm text-gray-500">
                          {onboardingStatus.status === 'online' &&
                            `First seen: ${formatDate(onboardingStatus.agent_first_seen_at)}`}
                          {onboardingStatus.status === 'waiting' &&
                            'Waiting for Agent to connect...'}
                          {onboardingStatus.status === 'expired' &&
                            'Agent not connected - project created more than 60 minutes ago'}
                        </div>
                      </div>
                    </div>

                    {onboardingStatus.status !== 'online' && (
                      <div>
                        <div className="flex items-center gap-2 mb-3">
                          <span className="text-sm text-gray-600">Generate install command for:</span>
                          <select
                            className="input text-sm max-w-xs"
                            value={installPlatform}
                            onChange={(e) => setInstallPlatform(e.target.value as TargetPlatform)}
                          >
                            <option value="linux-systemd">Linux (systemd)</option>
                            <option value="linux-docker">Linux (Docker)</option>
                            <option value="manual">Manual</option>
                          </select>
                          <button
                            onClick={() => handleGenerateInstallCommand()}
                            disabled={installCommandLoading}
                            className="btn btn-secondary text-sm"
                          >
                            {installCommandLoading ? (
                              <Loader2 className="w-4 h-4 animate-spin" />
                            ) : (
                              <RefreshCw className="w-4 h-4" />
                            )}
                          </button>
                        </div>

                        {installCommand ? (
                          <div className="bg-gray-900 rounded-md p-4">
                            <div className="flex items-center justify-between mb-2">
                              <span className="text-xs text-gray-400">Install Command</span>
                              <button
                                onClick={() =>
                                  handleCopyWithFeedback(installCommand.command, 'install-command')
                                }
                                className="text-xs px-2 py-1 rounded bg-gray-700 text-gray-200 hover:bg-gray-600"
                              >
                                {copiedItem === 'install-command' ? (
                                  <>
                                    <Check className="w-3 h-3 inline mr-1" />
                                    Copied
                                  </>
                                ) : (
                                  <>
                                    <Copy className="w-3 h-3 inline mr-1" />
                                    Copy
                                  </>
                                )}
                              </button>
                            </div>
                            <pre className="text-xs text-gray-100 font-mono whitespace-pre-wrap break-words">
                              {installCommand.command}
                            </pre>
                            {installCommand.notes.length > 0 && (
                              <div className="mt-3 pt-3 border-t border-gray-700">
                                <span className="text-xs text-gray-400">Notes:</span>
                                <ul className="mt-1 space-y-1">
                                  {installCommand.notes.map((note, i) => (
                                    <li key={i} className="text-xs text-gray-400 list-disc list-inside">
                                      {note}
                                    </li>
                                  ))}
                                </ul>
                              </div>
                            )}
                          </div>
                        ) : (
                          <div className="bg-gray-50 rounded-md p-4 text-center text-sm text-gray-500">
                            Click "Refresh" to generate an install command
                          </div>
                        )}
                      </div>
                    )}

                    {onboardingStatus.troubleshooting_hints.length > 0 &&
                      onboardingStatus.status !== 'online' && (
                        <div className="bg-yellow-50 border border-yellow-200 rounded-md p-3">
                          <div className="flex items-center gap-2 text-yellow-800 text-sm font-medium mb-2">
                            <AlertCircle className="w-4 h-4" />
                            Troubleshooting
                          </div>
                          <ul className="space-y-1">
                            {onboardingStatus.troubleshooting_hints.map((hint, i) => (
                              <li key={i} className="text-xs text-yellow-700 list-disc list-inside">
                                {hint}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                  </div>
                ) : (
                  <div className="text-center py-6 text-gray-500 text-sm">
                    Unable to load onboarding status
                  </div>
                )}
              </div>
            </div>

            <AgentPrecheckPanel projectId={projectId} />

            <div>
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
                  <Terminal className="w-5 h-5" />
                  Agent Bootstrap
                </h2>
              </div>
              <div className="card p-4 space-y-4">
                <div>
                  <span className="text-gray-500 text-xs block mb-2">Install Agent</span>
                  <div className="flex items-center gap-2">
                    <pre className="bg-gray-900 text-gray-100 rounded-md p-3 text-xs font-mono flex-1 overflow-x-auto">
                      pip install shipsmith-agent
                    </pre>
                    <button
                      onClick={() => copyToClipboard('pip install shipsmith-agent')}
                      className="btn btn-secondary text-xs px-3 py-1"
                    >
                      <Copy className="w-3 h-3" />
                    </button>
                  </div>
                </div>

                <div>
                  <span className="text-gray-500 text-xs block mb-2">Start Command</span>
                  <div className="flex items-center gap-2">
                    <pre className="bg-gray-900 text-gray-100 rounded-md p-3 text-xs font-mono flex-1 overflow-x-auto">
{`export SHIPSMITH_CORE_URL="http://your-core-host:8000/api/v1"
export SHIPSMITH_AGENT_TOKEN="${project.agent_token || '<your-token>'}"
export SHIPSMITH_WORKDIR="${project.deploy_workdir}"
shipsmith-agent`}
                    </pre>
                    <button
                      onClick={() =>
                        copyToClipboard(
                          `export SHIPSMITH_CORE_URL="http://your-core-host:8000/api/v1"\nexport SHIPSMITH_AGENT_TOKEN="${project.agent_token || '<your-token>'}"\nexport SHIPSMITH_WORKDIR="${project.deploy_workdir}"\nshipsmith-agent`,
                        )
                      }
                      className="btn btn-secondary text-xs px-3 py-1"
                    >
                      <Copy className="w-3 h-3" />
                    </button>
                  </div>
                </div>

                <div>
                  <span className="text-gray-500 text-xs block mb-2">
                    Self-Check Command (verify setup first)
                  </span>
                  <div className="flex items-center gap-2">
                    <pre className="bg-gray-900 text-gray-100 rounded-md p-3 text-xs font-mono flex-1 overflow-x-auto">
                      shipsmith-agent selfcheck
                    </pre>
                    <button
                      onClick={() => copyToClipboard('shipsmith-agent selfcheck')}
                      className="btn btn-secondary text-xs px-3 py-1"
                    >
                      <Copy className="w-3 h-3" />
                    </button>
                  </div>
                </div>

                <div>
                  <span className="text-gray-500 text-xs block mb-2">
                    <FileCode className="w-3 h-3 inline mr-1" />
                    shipsmith.yaml (optional)
                  </span>
                  <pre className="bg-gray-900 text-gray-100 rounded-md p-3 text-xs font-mono overflow-x-auto">
{`# shipsmith.yaml - Place in your workdir
core_url: "http://your-core-host:8000/api/v1"
agent_token: "your-agent-token"
workdir: "${project.deploy_workdir}"

# Polling intervals (optional, defaults shown)
poll_interval_seconds: 30
heartbeat_interval_seconds: 30
flags_sync_interval_seconds: 30`}
                  </pre>
                </div>

                <div className="border-t pt-4">
                  <div className="flex items-center gap-2 text-gray-600 text-xs font-medium mb-2">
                    <HelpCircle className="w-3 h-3" />
                    Common Troubleshooting
                  </div>
                  <ul className="text-xs text-gray-500 space-y-1 list-disc list-inside">
                    <li>
                      Ensure <code className="bg-gray-100 px-1">git</code> and{' '}
                      <code className="bg-gray-100 px-1">docker</code> are installed
                    </li>
                    <li>
                      Run <code className="bg-gray-100 px-1">shipsmith-agent selfcheck</code> to verify
                    </li>
                    <li>
                      Check workdir has write permissions:{' '}
                      <code className="bg-gray-100 px-1">
                        {project.deploy_workdir}
                      </code>
                    </li>
                    <li>
                      User must be in <code className="bg-gray-100 px-1">docker</code> group
                    </li>
                  </ul>
                </div>
              </div>
            </div>

            <div>
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
                  <Webhook className="w-5 h-5" />
                  Webhook
                </h2>
              </div>
              <div className="card p-4">
                {project.webhook_endpoint_id ? (
                  <>
                    <div className="mb-4">
                      <span className="text-gray-500 text-xs block">
                        GitHub Webhook URL
                      </span>
                      <div className="flex items-center gap-2 mt-1">
                        <code className="font-mono text-sm bg-gray-100 px-2 py-1 rounded flex-1 truncate">
                          /api/v1/webhooks/{project.webhook_endpoint_id}/github
                        </code>
                        <button
                          onClick={() =>
                            copyToClipboard(
                              `/api/v1/webhooks/${project.webhook_endpoint_id}/github`,
                            )
                          }
                          className="btn btn-secondary text-xs px-3 py-1"
                        >
                          <Copy className="w-3 h-3" />
                        </button>
                      </div>
                    </div>
                    <div className="mb-4">
                      <span className="text-gray-500 text-xs block">
                        GitLab Webhook URL
                      </span>
                      <div className="flex items-center gap-2 mt-1">
                        <code className="font-mono text-sm bg-gray-100 px-2 py-1 rounded flex-1 truncate">
                          /api/v1/webhooks/{project.webhook_endpoint_id}/gitlab
                        </code>
                        <button
                          onClick={() =>
                            copyToClipboard(
                              `/api/v1/webhooks/${project.webhook_endpoint_id}/gitlab`,
                            )
                          }
                          className="btn btn-secondary text-xs px-3 py-1"
                        >
                          <Copy className="w-3 h-3" />
                        </button>
                      </div>
                    </div>
                    <div className="mb-4 p-3 bg-blue-50 rounded-md text-xs text-blue-700">
                      <p className="font-medium mb-1">Configuration Tips:</p>
                      <ul className="list-disc list-inside space-y-1">
                        <li>
                          GitHub: Set Content-Type to
                          <code className="bg-blue-100 px-1">application/json</code>
                        </li>
                        <li>
                          GitHub: Enable
                          <code className="bg-blue-100 px-1">Just the push event</code>
                        </li>
                        <li>GitLab: Enter the secret in "Secret Token" field</li>
                      </ul>
                    </div>
                  </>
                ) : (
                  <p className="text-gray-500 text-sm mb-4">
                    No webhook configured yet. Generate a secret to enable
                    webhooks.
                  </p>
                )}

                <button
                  onClick={handleGenerateWebhookSecret}
                  disabled={generatingWebhookSecret}
                  className="btn btn-secondary text-sm w-full"
                >
                  <Key className="w-4 h-4 mr-2" />
                  {project.webhook_endpoint_id
                    ? 'Regenerate Webhook Secret'
                    : 'Generate Webhook Secret'}
                </button>
              </div>
            </div>
          </div>

          <div className="space-y-8">
            <div>
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold text-gray-900">
                  Deploy History
                </h2>
                {deployments.length > 5 && (
                  <button
                    type="button"
                    onClick={() => setShowAllDeployments((current) => !current)}
                    className="text-sm text-blue-600 hover:text-blue-700"
                  >
                    {showAllDeployments ? 'Show less' : `Show more (${deployments.length - 5})`}
                  </button>
                )}
              </div>

              {deployments.length === 0 ? (
                <div className="card p-8 text-center">
                  <Clock className="w-10 h-10 text-gray-400 mx-auto mb-3" />
                  <p className="text-gray-600">No deployments yet.</p>
                </div>
              ) : (
                <div className="card divide-y divide-gray-100 overflow-hidden">
                  {(showAllDeployments ? deployments : deployments.slice(0, 5)).map((deployment) => (
                    <Link
                      key={deployment.id}
                      href={`/deployments/${deployment.id}`}
                      className="block px-4 py-3 hover:bg-gray-50 transition-colors"
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div className="flex items-center gap-2">
                          <StatusBadge
                            status={deployment.status}
                            small
                          />
                          <span className="text-sm font-medium text-gray-900">
                            #{deployment.id}
                          </span>
                          <span className="text-xs text-gray-500 uppercase">
                            {deployment.kind}
                          </span>
                        </div>
                        <span className="text-xs text-gray-500">
                          {formatDate(deployment.queued_at)}
                        </span>
                      </div>
                      <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-gray-600">
                        {deployment.commit_hash && (
                          <span className="flex items-center gap-1">
                            <GitCommit className="w-3 h-3" />
                            {deployment.commit_hash.substring(0, 8)}
                          </span>
                        )}
                        {deployment.triggered_by && (
                          <span className="flex items-center gap-1">
                            <User className="w-3 h-3" />
                            {deployment.triggered_by}
                          </span>
                        )}
                      </div>
                      {deployment.failure_phase && (
                        <div className="mt-2 text-xs text-red-600">
                          Failed at: {deployment.failure_phase}
                        </div>
                      )}
                    </Link>
                  ))}
                </div>
              )}
            </div>

            <div>
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
                  <Notebook className="w-5 h-5" />
                  Runbook
                </h2>
                <button
                  onClick={handleOpenRunbookEdit}
                  className="btn btn-secondary text-sm"
                >
                  <FileEdit className="w-4 h-4 mr-2" />
                  Edit
                </button>
              </div>
              <div className="card p-4 space-y-4">
                <div className="space-y-4">
                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <Notebook className="w-4 h-4 text-gray-500" />
                      <span className="text-sm font-medium text-gray-700">Notes</span>
                    </div>
                    {project?.notes ? (
                      <div className="text-sm text-gray-600 whitespace-pre-wrap bg-gray-50 rounded-md p-3">
                        {project.notes}
                      </div>
                    ) : (
                      <div className="text-sm text-gray-400 italic bg-gray-50 rounded-md p-3">
                        No notes yet
                      </div>
                    )}
                  </div>

                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <FileEdit className="w-4 h-4 text-gray-500" />
                      <span className="text-sm font-medium text-gray-700">Release Notes Hint</span>
                    </div>
                    {project?.release_notes_hint ? (
                      <div className="text-sm text-gray-600 whitespace-pre-wrap bg-gray-50 rounded-md p-3">
                        {project.release_notes_hint}
                      </div>
                    ) : (
                      <div className="text-sm text-gray-400 italic bg-gray-50 rounded-md p-3">
                        No release notes hint
                      </div>
                    )}
                  </div>

                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <AlertCircle className="w-4 h-4 text-orange-500" />
                      <span className="text-sm font-medium text-gray-700">Troubleshooting</span>
                    </div>
                    {project?.troubleshooting_hint ? (
                      <div className="text-sm text-gray-600 whitespace-pre-wrap bg-orange-50 rounded-md p-3">
                        {project.troubleshooting_hint}
                      </div>
                    ) : (
                      <div className="text-sm text-gray-400 italic bg-gray-50 rounded-md p-3">
                        No troubleshooting guide
                      </div>
                    )}
                  </div>
                </div>

                <div className="pt-2 border-t border-gray-200">
                  <div className="text-sm font-medium text-gray-700 mb-2">Quick Links</div>
                  <div className="grid grid-cols-1 gap-2">
                    {project?.admin_url && (
                      <a
                        href={project.admin_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center gap-2 text-sm text-blue-600 hover:text-blue-800 hover:underline"
                      >
                        <Database className="w-4 h-4" />
                        <span>Admin Dashboard</span>
                        <ExternalLink className="w-3 h-3" />
                      </a>
                    )}
                    {project?.metrics_url && (
                      <a
                        href={project.metrics_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center gap-2 text-sm text-blue-600 hover:text-blue-800 hover:underline"
                      >
                        <BarChart3 className="w-4 h-4" />
                        <span>Metrics</span>
                        <ExternalLink className="w-3 h-3" />
                      </a>
                    )}
                    {project?.logs_url && (
                      <a
                        href={project.logs_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center gap-2 text-sm text-blue-600 hover:text-blue-800 hover:underline"
                      >
                        <FileSearch className="w-4 h-4" />
                        <span>Logs</span>
                        <ExternalLink className="w-3 h-3" />
                      </a>
                    )}
                    {project?.ssh_hint && (
                      <div className="flex items-start gap-2 text-sm text-gray-600">
                        <ShieldCheck className="w-4 h-4 mt-0.5 text-gray-500" />
                        <span className="whitespace-pre-wrap">{project.ssh_hint}</span>
                      </div>
                    )}
                    {!project?.admin_url &&
                      !project?.metrics_url &&
                      !project?.logs_url &&
                      !project?.ssh_hint && (
                        <div className="text-sm text-gray-400 italic">
                          No quick links configured
                        </div>
                      )}
                  </div>
                </div>
              </div>
            </div>

            <div>
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold text-gray-900">
                  Feature Flags
                </h2>
                <div className="flex items-center gap-2">
                  <label className="flex items-center gap-2 text-xs text-gray-600">
                    <input
                      type="checkbox"
                      checked={includeArchivedFlags}
                      onChange={(e) =>
                        setIncludeArchivedFlags(e.target.checked)
                      }
                      className="w-3 h-3"
                    />
                    Show archived
                  </label>
                  <button
                    onClick={() => setShowFlagForm(true)}
                    className="btn btn-secondary text-sm"
                  >
                    <Plus className="w-4 h-4 mr-2" />
                    New Flag
                  </button>
                </div>
              </div>

              {showFlagForm && (
                <div className="card p-4 mb-4">
                  <h3 className="font-medium text-gray-900 mb-3">Create Flag</h3>
                  <form
                    onSubmit={handleCreateFlag}
                    className="space-y-3"
                  >
                    <div>
                      <label className="label">Key</label>
                      <input
                        type="text"
                        className="input"
                        value={flagFormData.key}
                        onChange={(e) =>
                          setFlagFormData({
                            ...flagFormData,
                            key: e.target.value,
                          })
                        }
                        placeholder="new_feature"
                        required
                      />
                    </div>
                    <div>
                      <label className="label">Description (optional)</label>
                      <input
                        type="text"
                        className="input"
                        value={flagFormData.description}
                        onChange={(e) =>
                          setFlagFormData({
                            ...flagFormData,
                            description: e.target.value,
                          })
                        }
                        placeholder="Describe this flag"
                      />
                    </div>
                    <div className="flex items-center">
                      <input
                        type="checkbox"
                        id="flag-enabled"
                        className="w-4 h-4 mr-2"
                        checked={flagFormData.enabled}
                        onChange={(e) =>
                          setFlagFormData({
                            ...flagFormData,
                            enabled: e.target.checked,
                          })
                        }
                      />
                      <label
                        htmlFor="flag-enabled"
                        className="text-sm text-gray-700"
                      >
                        Enabled
                      </label>
                    </div>
                    <div className="flex gap-2">
                      <button
                        type="button"
                        onClick={() => setShowFlagForm(false)}
                        className="btn btn-secondary text-sm"
                      >
                        Cancel
                      </button>
                      <button
                        type="submit"
                        className="btn btn-primary text-sm"
                        disabled={savingFlag}
                      >
                        {savingFlag ? 'Creating...' : 'Create'}
                      </button>
                    </div>
                  </form>
                </div>
              )}

              {flags.length === 0 ? (
                <div className="card p-8 text-center">
                  <Flag className="w-10 h-10 text-gray-400 mx-auto mb-3" />
                  <p className="text-gray-600">No flags yet.</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {flags.map((flag) => (
                    <div
                      key={flag.id}
                      className={`card p-4 flex items-center justify-between ${
                        flag.archived ? 'opacity-60' : ''
                      }`}
                    >
                      <div className="flex-1">
                        <div className="flex items-center gap-3">
                          <span className="font-mono text-sm font-medium text-gray-900">
                            {flag.key}
                          </span>
                          {flag.archived ? (
                            <span className="text-xs text-gray-500 bg-gray-100 px-2 py-0.5 rounded">
                              Archived
                            </span>
                          ) : (
                            <StatusBadge
                              status={flag.enabled ? 'healthy' : 'unknown'}
                              small
                            />
                          )}
                        </div>
                        {flag.description && (
                          <p className="text-xs text-gray-500 mt-1">
                            {flag.description}
                          </p>
                        )}
                        <p className="text-xs text-gray-400 mt-1">
                          Updated at {formatDate(flag.updated_at)}
                          {flag.updated_by && ` by ${flag.updated_by}`}
                        </p>
                      </div>
                      <div className="flex items-center gap-2">
                        {!flag.archived && (
                          <button
                            onClick={() => handleToggleFlag(flag)}
                            className={`relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out ${
                              flag.enabled ? 'bg-green-600' : 'bg-gray-200'
                            }`}
                          >
                            <span
                              className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                                flag.enabled
                                  ? 'translate-x-5'
                                  : 'translate-x-0'
                              }`}
                            />
                          </button>
                        )}
                        {flag.archived ? (
                          <button
                            onClick={() => handleUnarchiveFlag(flag)}
                            className="btn btn-secondary text-xs px-2 py-1"
                            title="Unarchive"
                          >
                            <ArchiveRestore className="w-3 h-3" />
                          </button>
                        ) : (
                          <button
                            onClick={() => handleArchiveFlag(flag)}
                            className="btn btn-secondary text-xs px-2 py-1"
                            title="Archive"
                          >
                            <Archive className="w-3 h-3" />
                          </button>
                        )}
                        <button
                          onClick={() => handleDeleteFlag(flag)}
                          className="btn btn-secondary text-xs px-2 py-1 text-red-600 hover:bg-red-50"
                          title="Delete"
                        >
                          <Trash2 className="w-3 h-3" />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div>
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
                  <History className="w-5 h-5" />
                  Timeline
                </h2>
                <div className="relative">
                  <button
                    onClick={() => setShowTimelineFilter(!showTimelineFilter)}
                    className="btn btn-secondary text-sm flex items-center gap-2"
                  >
                    <Filter className="w-4 h-4" />
                    {timelineFilter
                      ? TIMELINE_FILTER_OPTIONS.find(o => o.value === timelineFilter)?.label || 'Filter'
                      : 'All Events'}
                    <ChevronDown className="w-4 h-4" />
                  </button>
                  
                  {showTimelineFilter && (
                    <>
                      <div 
                        className="fixed inset-0 z-10" 
                        onClick={() => setShowTimelineFilter(false)}
                      />
                      <div className="absolute right-0 top-full mt-1 bg-white border border-gray-200 rounded-md shadow-lg z-20 min-w-[200px] max-h-[400px] overflow-y-auto">
                        {TIMELINE_FILTER_OPTIONS.map((option) => (
                          <button
                            key={String(option.value)}
                            onClick={() => {
                              setTimelineFilter(option.value);
                              setShowTimelineFilter(false);
                            }}
                            className={`w-full text-left px-4 py-2 text-sm hover:bg-gray-50 ${
                              timelineFilter === option.value ? 'text-primary-700 bg-primary-50 font-medium' : 'text-gray-700'
                            }`}
                          >
                            {option.label}
                          </button>
                        ))}
                      </div>
                    </>
                  )}
                </div>
              </div>

              {timelineLoading ? (
                <div className="card p-8 text-center">
                  <Loader2 className="w-8 h-8 text-gray-400 mx-auto animate-spin" />
                  <p className="text-gray-500 mt-2">Loading timeline...</p>
                </div>
              ) : timelineEvents.length === 0 ? (
                <div className="card p-8 text-center">
                  <History className="w-10 h-10 text-gray-400 mx-auto mb-3" />
                  <p className="text-gray-600">
                    {timelineFilter ? 'No matching events' : 'No events yet'}
                  </p>
                </div>
              ) : (
                <div className="mt-2">
                  {timelineEvents.slice(0, 20).map((event) => (
                    <TimelineEventItem key={event.id} event={event} />
                  ))}
                  {timelineTotal > 20 && (
                    <div className="text-center text-sm text-gray-500 pt-2">
                      Showing 20 of {timelineTotal} events
                    </div>
                  )}
                </div>
              )}
            </div>

            <div>
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
                  <Bell className="w-5 h-5" />
                  Notifications
                </h2>
                <button
                  onClick={() => setShowNewChannelForm(true)}
                  className="btn btn-secondary text-sm"
                >
                  <Plus className="w-4 h-4 mr-2" />
                  New Channel
                </button>
              </div>

              {notificationsLoading ? (
                <div className="card p-8 text-center">
                  <Loader2 className="w-8 h-8 text-gray-400 mx-auto animate-spin" />
                  <p className="text-gray-500 mt-2">Loading notifications...</p>
                </div>
              ) : (
                <div className="space-y-6">
                  <div className="card p-4">
                    <h3 className="font-medium text-gray-900 mb-4">Notification Channels</h3>

                    {showNewChannelForm && (
                      <div className="mb-4 p-4 bg-gray-50 rounded-md border border-gray-200">
                        <h4 className="text-sm font-medium text-gray-700 mb-3">Create New Channel</h4>
                        <form onSubmit={handleCreateChannel} className="space-y-3">
                          <div className="grid grid-cols-2 gap-3">
                            <div>
                              <label className="label text-xs">Name</label>
                              <input
                                type="text"
                                className="input text-sm"
                                value={newChannelFormData.name}
                                onChange={(e) => setNewChannelFormData({ ...newChannelFormData, name: e.target.value })}
                                placeholder="My Channel"
                                required
                              />
                            </div>
                            <div>
                              <label className="label text-xs">Type</label>
                              <select
                                className="input text-sm"
                                value={newChannelFormData.channel_type}
                                onChange={(e) => setNewChannelFormData({ ...newChannelFormData, channel_type: e.target.value as ChannelType })}
                              >
                                <option value="webhook">Webhook</option>
                                <option value="feishu">飞书</option>
                                <option value="slack">Slack</option>
                              </select>
                            </div>
                          </div>

                          {newChannelFormData.channel_type === 'webhook' && (
                            <div>
                              <label className="label text-xs">URL</label>
                              <input
                                type="url"
                                className="input text-sm"
                                value={newChannelFormData.config?.url || ''}
                                onChange={(e) => setNewChannelFormData({ ...newChannelFormData, config: { ...newChannelFormData.config, url: e.target.value } })}
                                placeholder="https://example.com/webhook"
                                required
                              />
                            </div>
                          )}

                          {newChannelFormData.channel_type === 'feishu' && (
                            <div>
                              <label className="label text-xs">Webhook URL</label>
                              <input
                                type="url"
                                className="input text-sm"
                                value={newChannelFormData.config?.webhook_url || ''}
                                onChange={(e) => setNewChannelFormData({ ...newChannelFormData, config: { ...newChannelFormData.config, webhook_url: e.target.value } })}
                                placeholder="https://open.feishu.cn/open-apis/bot/v2/hook/xxx"
                                required
                              />
                            </div>
                          )}

                          {newChannelFormData.channel_type === 'slack' && (
                            <div>
                              <label className="label text-xs">Webhook URL</label>
                              <input
                                type="url"
                                className="input text-sm"
                                value={newChannelFormData.config?.webhook_url || ''}
                                onChange={(e) => setNewChannelFormData({ ...newChannelFormData, config: { ...newChannelFormData.config, webhook_url: e.target.value } })}
                                placeholder="https://hooks.slack.com/services/xxx"
                                required
                              />
                            </div>
                          )}

                          <div className="flex gap-2 justify-end">
                            <button
                              type="button"
                              onClick={() => setShowNewChannelForm(false)}
                              className="btn btn-secondary text-xs py-2 px-3"
                            >
                              Cancel
                            </button>
                            <button
                              type="submit"
                              disabled={savingChannel}
                              className="btn btn-primary text-xs py-2 px-3"
                            >
                              {savingChannel ? 'Creating...' : 'Create'}
                            </button>
                          </div>
                        </form>
                      </div>
                    )}

                    {notificationChannels.length === 0 ? (
                      <div className="text-center py-6 text-gray-500 text-sm">
                        <Bell className="w-8 h-8 mx-auto mb-2 text-gray-300" />
                        No notification channels configured yet.
                      </div>
                    ) : (
                      <div className="space-y-2">
                        {notificationChannels.map((channel) => (
                          <div
                            key={channel.id}
                            className="flex items-center justify-between p-3 border border-gray-200 rounded-md hover:border-gray-300 transition-colors"
                          >
                            <div className="flex items-center gap-3">
                              <StatusBadge
                                status={channel.is_active ? 'healthy' : 'unknown'}
                                small
                              />
                              <div>
                                <div className="text-sm font-medium text-gray-900">
                                  {channel.name}
                                </div>
                                <div className="text-xs text-gray-500">
                                  {getChannelTypeName(channel.channel_type)}
                                </div>
                              </div>
                            </div>
                            <div className="flex items-center gap-2">
                              <button
                                onClick={() => handleTestChannel(channel)}
                                disabled={testingChannelId === channel.id || !channel.is_active}
                                className="btn btn-secondary text-xs px-2 py-1"
                                title="Test notification"
                              >
                                {testingChannelId === channel.id ? (
                                  <Loader2 className="w-3 h-3 animate-spin" />
                                ) : (
                                  <Send className="w-3 h-3" />
                                )}
                              </button>
                              <button
                                onClick={() => handleToggleChannel(channel)}
                                className="btn btn-secondary text-xs px-2 py-1"
                                title={channel.is_active ? 'Disable' : 'Enable'}
                              >
                                {channel.is_active ? (
                                  <BellOff className="w-3 h-3" />
                                ) : (
                                  <Bell className="w-3 h-3" />
                                )}
                              </button>
                              <button
                                onClick={() => handleDeleteChannel(channel)}
                                className="btn btn-secondary text-xs px-2 py-1 text-red-600 hover:bg-red-50"
                                title="Delete"
                              >
                                <Trash2 className="w-3 h-3" />
                              </button>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  <div className="card p-4">
                    <h3 className="font-medium text-gray-900 mb-4">Event Settings</h3>
                    <p className="text-xs text-gray-500 mb-4">
                      Configure which events trigger notifications and set noise reduction options.
                    </p>

                    {notificationSettings.length === 0 ? (
                      <div className="text-center py-6 text-gray-500 text-sm">
                        <Settings className="w-8 h-8 mx-auto mb-2 text-gray-300" />
                        Loading settings...
                      </div>
                    ) : (
                      <div className="space-y-2">
                        {notificationSettings.map((setting) => {
                          const isExpanded = expandedSettingId === setting.id;
                          const isErrorEvent = ['agent_offline', 'health_degraded', 'health_unhealthy', 'deployment_failed'].includes(setting.event_type);

                          return (
                            <div
                              key={setting.id}
                              className={`border rounded-md transition-colors ${setting.enabled ? 'border-gray-200' : 'border-gray-100 bg-gray-50'}`}
                            >
                              <div className="flex items-center justify-between p-3">
                                <div className="flex items-center gap-3">
                                  <button
                                    onClick={() => handleUpdateSetting(setting, { enabled: !setting.enabled })}
                                    className={`relative inline-flex h-5 w-9 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out ${setting.enabled ? 'bg-green-600' : 'bg-gray-200'}`}
                                  >
                                    <span
                                      className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${setting.enabled ? 'translate-x-4' : 'translate-x-0'}`}
                                    />
                                  </button>
                                  <div>
                                    <div className="text-sm font-medium text-gray-900">
                                      {getEventTypeName(setting.event_type as NotificationEventType)}
                                    </div>
                                    <div className="text-xs text-gray-500">
                                      {setting.channel_ids.length > 0
                                        ? `${setting.channel_ids.length} channel(s)`
                                        : 'No channels'}
                                    </div>
                                  </div>
                                </div>
                                <div className="flex items-center gap-2">
                                  {isErrorEvent && setting.enabled && (
                                    <span className="flex items-center gap-1 text-xs text-orange-600 bg-orange-50 px-2 py-0.5 rounded">
                                      <Zap className="w-3 h-3" />
                                      Cooldown: {setting.cooldown_seconds}s
                                    </span>
                                  )}
                                  <button
                                    onClick={() => setExpandedSettingId(isExpanded ? null : setting.id)}
                                    className="btn btn-secondary text-xs px-2 py-1"
                                  >
                                    <ChevronDown className={`w-3 h-3 transition-transform ${isExpanded ? 'rotate-180' : ''}`} />
                                  </button>
                                </div>
                              </div>

                              {isExpanded && (
                                <div className="px-4 pb-4 pt-0 space-y-3 border-t border-gray-100 mt-2 pt-3">
                                  <div>
                                    <label className="label text-xs">Channels</label>
                                    <div className="space-y-1">
                                      {notificationChannels.length === 0 ? (
                                        <p className="text-xs text-gray-400">No channels available</p>
                                      ) : (
                                        notificationChannels.map((channel) => {
                                          const isSelected = setting.channel_ids.includes(channel.id);
                                          return (
                                            <label
                                              key={channel.id}
                                              className="flex items-center gap-2 text-sm cursor-pointer p-1 rounded hover:bg-gray-50"
                                            >
                                              <input
                                                type="checkbox"
                                                checked={isSelected}
                                                onChange={() => {
                                                  const newChannelIds = isSelected
                                                    ? setting.channel_ids.filter((id) => id !== channel.id)
                                                    : [...setting.channel_ids, channel.id];
                                                  handleUpdateSetting(setting, { channel_ids: newChannelIds });
                                                }}
                                                className="w-3 h-3"
                                              />
                                              <span className={isSelected ? 'text-gray-900' : 'text-gray-500'}>
                                                {channel.name}
                                              </span>
                                            </label>
                                          );
                                        })
                                      )}
                                    </div>
                                  </div>

                                  {isErrorEvent && (
                                    <>
                                      <div>
                                        <label className="label text-xs">
                                          Cooldown Window (seconds)
                                        </label>
                                        <p className="text-xs text-gray-400 mb-1">
                                          Suppress duplicate notifications within this window
                                        </p>
                                        <input
                                          type="number"
                                          min="0"
                                          max="86400"
                                          value={setting.cooldown_seconds}
                                          onChange={(e) =>
                                            handleUpdateSetting(setting, {
                                              cooldown_seconds: Math.max(0, Math.min(86400, Number(e.target.value))),
                                            })
                                          }
                                          className="input text-sm"
                                        />
                                        <div className="flex gap-2 mt-2">
                                          {[60, 300, 600, 1800].map((seconds) => (
                                            <button
                                              key={seconds}
                                              type="button"
                                              onClick={() => handleUpdateSetting(setting, { cooldown_seconds: seconds })}
                                              className={`text-xs px-2 py-1 rounded border ${setting.cooldown_seconds === seconds ? 'bg-primary-100 border-primary-300 text-primary-700' : 'bg-gray-50 border-gray-200 text-gray-600 hover:bg-gray-100'}`}
                                            >
                                              {seconds < 60 ? `${seconds}s` : `${seconds / 60}m`}
                                            </button>
                                          ))}
                                        </div>
                                      </div>

                                      <div>
                                        <label className="flex items-center gap-2 text-sm cursor-pointer">
                                          <input
                                            type="checkbox"
                                            checked={setting.send_recovery}
                                            onChange={(e) =>
                                              handleUpdateSetting(setting, { send_recovery: e.target.checked })
                                            }
                                            className="w-3 h-3"
                                          />
                                          <span className="text-gray-700">Send recovery notifications</span>
                                        </label>
                                        <p className="text-xs text-gray-400 ml-5">
                                          Send a notification when the service recovers from this error
                                        </p>
                                      </div>
                                    </>
                                  )}
                                </div>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>

                  <div className="card p-4">
                    <div className="flex items-center justify-between mb-4">
                      <h3 className="font-medium text-gray-900">Recent Deliveries</h3>
                      <button
                        onClick={loadNotifications}
                        className="btn btn-secondary text-xs"
                      >
                        <RefreshCw className="w-3 h-3 mr-1" />
                        Refresh
                      </button>
                    </div>

                    {notificationDeliveries.length === 0 ? (
                      <div className="text-center py-6 text-gray-500 text-sm">
                        <Clock className="w-8 h-8 mx-auto mb-2 text-gray-300" />
                        No notification deliveries yet.
                      </div>
                    ) : (
                      <div className="space-y-2 max-h-80 overflow-y-auto">
                        {notificationDeliveries.slice(0, 20).map((delivery) => (
                          <div
                            key={delivery.id}
                            className="flex items-start gap-3 p-2 rounded-md hover:bg-gray-50"
                          >
                            <div className="mt-0.5">
                              {delivery.status === 'success' && (
                                <CheckCircle2 className="w-4 h-4 text-green-500" />
                              )}
                              {delivery.status === 'failed' && (
                                <XCircle className="w-4 h-4 text-red-500" />
                              )}
                              {delivery.status === 'suppressed' && (
                                <BellOff className="w-4 h-4 text-gray-400" />
                              )}
                              {delivery.status === 'queued' && (
                                <Clock className="w-4 h-4 text-blue-400" />
                              )}
                            </div>
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2 flex-wrap">
                                <span className="text-sm font-medium text-gray-900">
                                  {getEventTypeName(delivery.event_type as NotificationEventType)}
                                </span>
                                {delivery.is_recovery && (
                                  <span className="text-xs bg-green-100 text-green-700 px-1.5 py-0.5 rounded">
                                    Recovery
                                  </span>
                                )}
                                {delivery.is_suppressed && (
                                  <span className="text-xs bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded">
                                    Suppressed
                                  </span>
                                )}
                              </div>
                              <div className="text-xs text-gray-500">
                                {formatDate(delivery.sent_at || delivery.created_at)}
                                {delivery.error_message && (
                                  <span className="ml-2 text-red-500 truncate">
                                    • {delivery.error_message}
                                  </span>
                                )}
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>

        {showEditForm && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
            <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
              <div className="p-6 border-b border-gray-200">
                <h2 className="text-xl font-semibold text-gray-900 flex items-center gap-2">
                  <Settings className="w-5 h-5" />
                  Edit Project Configuration
                </h2>
                <p className="text-sm text-gray-500 mt-1">
                  调整项目配置。修改后，下次部署将使用新配置。
                </p>
              </div>
              <form
                onSubmit={handleSaveEdit}
                className="p-6 space-y-6"
              >
                <div className="border-t border-gray-200 pt-4 first:border-t-0 first:pt-0">
                  <h3 className="text-sm font-medium text-gray-900 mb-3 flex items-center gap-2">
                    <FolderGit2 className="w-4 h-4 text-gray-500" />
                    基本信息
                  </h3>
                  <div className="space-y-4">
                    <div>
                      <label className="label flex items-center justify-between">
                        <span>Project Name</span>
                        <span className="text-xs text-gray-400 font-normal">项目标识名称</span>
                      </label>
                      <input
                        type="text"
                        className="input"
                        value={editFormData.name || ''}
                        onChange={(e) =>
                          setEditFormData({
                            ...editFormData,
                            name: e.target.value,
                          })
                        }
                        placeholder="my-saas-app"
                      />
                      <p className="text-xs text-gray-400 mt-1">
                        仅用于标识，支持字母、数字、点、横杠和下划线
                      </p>
                    </div>

                    <div>
                      <label className="label flex items-center justify-between">
                        <span>Environment</span>
                        <span className="text-xs text-gray-400 font-normal">环境</span>
                      </label>
                      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                        <button
                          type="button"
                          onClick={() => setEditFormData({ ...editFormData, environment: null })}
                          className={`px-3 py-2 text-sm rounded-md border transition-colors ${
                            !editFormData.environment
                              ? 'bg-primary-50 border-primary-300 text-primary-700'
                              : 'bg-white border-gray-200 text-gray-600 hover:bg-gray-50'
                          }`}
                        >
                          不指定
                        </button>
                        {[
                          { value: 'production', label: '生产环境', color: 'bg-red-100 text-red-800 border-red-200' },
                          { value: 'staging', label: '预发环境', color: 'bg-orange-100 text-orange-800 border-orange-200' },
                          { value: 'development', label: '开发环境', color: 'bg-green-100 text-green-800 border-green-200' },
                          { value: 'testing', label: '测试环境', color: 'bg-blue-100 text-blue-800 border-blue-200' },
                          { value: 'other', label: '其他', color: 'bg-gray-100 text-gray-800 border-gray-200' },
                        ].map((opt) => (
                          <button
                            key={opt.value}
                            type="button"
                            onClick={() => setEditFormData({ ...editFormData, environment: opt.value as any })}
                            className={`px-3 py-2 text-sm rounded-md border transition-colors ${
                              editFormData.environment === opt.value
                                ? `${opt.color} font-medium border-2`
                                : 'bg-white border-gray-200 text-gray-600 hover:bg-gray-50'
                            }`}
                          >
                            {opt.label}
                          </button>
                        ))}
                      </div>
                      <p className="text-xs text-gray-400 mt-1">
                        用于在项目列表中过滤和区分不同环境
                      </p>
                    </div>
                  </div>
                </div>

                <div className="border-t border-gray-200 pt-4">
                  <h3 className="text-sm font-medium text-gray-900 mb-3 flex items-center gap-2">
                    <GitCommit className="w-4 h-4 text-gray-500" />
                    Git 配置
                  </h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label className="label flex items-center justify-between">
                        <span>Git Repository</span>
                        <span className="text-xs text-gray-400 font-normal">代码仓库</span>
                      </label>
                      <input
                        type="text"
                        className="input"
                        value={editFormData.git_repo || ''}
                        onChange={(e) =>
                          setEditFormData({
                            ...editFormData,
                            git_repo: e.target.value,
                          })
                        }
                        placeholder="git@github.com:user/repo.git"
                      />
                      <p className="text-xs text-gray-400 mt-1">
                        支持 SSH 或 HTTPS 协议
                      </p>
                    </div>
                    <div>
                      <label className="label flex items-center justify-between">
                        <span>Git Credentials</span>
                        <span className="text-xs text-gray-400 font-normal">私有仓库访问</span>
                      </label>
                      <select
                        className="input"
                        value={(editFormData.git_credential_type as GitCredentialType) || 'none'}
                        onChange={(e) =>
                          setEditFormData({
                            ...editFormData,
                            git_credential_type: e.target.value as GitCredentialType,
                          })
                        }
                      >
                        <option value="none">No credentials</option>
                        <option value="http_token">HTTP token</option>
                        <option value="ssh_key">SSH private key</option>
                      </select>
                      <p className="text-xs text-gray-400 mt-1">
                        {project?.git_credential_configured ? '已配置凭据。敏感字段留空表示保持不变。' : '当前未配置仓库凭据。'}
                      </p>
                    </div>
                    <div>
                      <label className="label flex items-center justify-between">
                        <span>Branch</span>
                        <span className="text-xs text-gray-400 font-normal">部署分支</span>
                      </label>
                      <input
                        type="text"
                        className="input"
                        value={editFormData.git_branch || ''}
                        onChange={(e) =>
                          setEditFormData({
                            ...editFormData,
                            git_branch: e.target.value,
                          })
                        }
                        placeholder="main"
                      />
                      <p className="text-xs text-gray-400 mt-1">
                        默认从该分支拉取最新代码
                      </p>
                    </div>
                  </div>

                  {(editFormData.git_credential_type || 'none') === 'http_token' ? (
                    <div className="grid grid-cols-1 gap-4 mt-4">
                      <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-3 text-xs text-amber-900">
                        <p className="font-medium">HTTP Token 说明</p>
                        <p className="mt-1">`Git Username` 一般填代码托管平台用户名，`Access Token` 填平台后台生成的个人访问令牌。</p>
                        <p className="mt-1">GitHub: Settings → Developer settings → Personal access tokens。</p>
                        <p className="mt-1">GitLab: User Settings → Access Tokens。Gitee: 设置 → 私人令牌。</p>
                        <p className="mt-1">如果你是长期部署环境，优先使用 `SSH private key`。</p>
                      </div>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div>
                          <label className="label">Git Username</label>
                          <input
                            type="text"
                            className="input"
                            value={(editFormData.git_credential_username as string) || ''}
                            onChange={(e) =>
                              setEditFormData({
                                ...editFormData,
                                git_credential_username: e.target.value,
                              })
                            }
                            placeholder="GitHub 用户名 / x-access-token / GitLab 用户名"
                          />
                          <p className="text-xs text-gray-400 mt-1">
                            GitHub 常见填法：你的用户名，或 `x-access-token`
                          </p>
                        </div>
                        <div>
                          <label className="label">Access Token</label>
                          <input
                            type="password"
                            className="input"
                            value={(editFormData.git_credential_token as string) || ''}
                            onChange={(e) =>
                              setEditFormData({
                                ...editFormData,
                                git_credential_token: e.target.value,
                              })
                            }
                            placeholder="留空则保持现有 token"
                          />
                          <p className="text-xs text-gray-400 mt-1">
                            需要具备读取仓库权限
                          </p>
                        </div>
                      </div>
                    </div>
                  ) : null}

                  {(editFormData.git_credential_type || 'none') === 'ssh_key' ? (
                    <div className="grid grid-cols-1 gap-4 mt-4">
                      <div>
                        <label className="label">SSH Private Key</label>
                        <textarea
                          className="input min-h-[160px]"
                          value={(editFormData.git_credential_ssh_private_key as string) || ''}
                          onChange={(e) =>
                            setEditFormData({
                              ...editFormData,
                              git_credential_ssh_private_key: e.target.value,
                            })
                          }
                          placeholder="留空则保持现有私钥"
                        />
                        <p className="text-xs text-gray-400 mt-1">
                          推荐使用只读 Deploy Key，或专门用于部署的 SSH 私钥
                        </p>
                      </div>
                      <div>
                        <label className="label">Known Hosts</label>
                        <textarea
                          className="input min-h-[96px]"
                          value={(editFormData.git_credential_ssh_known_hosts as string) || ''}
                          onChange={(e) =>
                            setEditFormData({
                              ...editFormData,
                              git_credential_ssh_known_hosts: e.target.value,
                            })
                          }
                          placeholder="留空则保持现有 known_hosts"
                        />
                      </div>
                    </div>
                  ) : null}
                </div>

                <div className="border-t border-gray-200 pt-4">
                  <h3 className="text-sm font-medium text-gray-900 mb-3 flex items-center gap-2">
                    <Server className="w-4 h-4 text-gray-500" />
                    部署配置
                  </h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label className="label flex items-center justify-between">
                        <span>Deploy Workdir</span>
                        <span className="text-xs text-gray-400 font-normal">工作目录</span>
                      </label>
                      <input
                        type="text"
                        className="input"
                        value={editFormData.deploy_workdir || ''}
                        onChange={(e) =>
                          setEditFormData({
                            ...editFormData,
                            deploy_workdir: e.target.value,
                          })
                        }
                        placeholder="/opt/my-saas-app"
                      />
                      <p className="text-xs text-gray-400 mt-1">
                        Agent 执行部署的目录，必须是绝对路径
                      </p>
                    </div>
                    <div>
                      <label className="label flex items-center justify-between">
                        <span>Compose File</span>
                        <span className="text-xs text-gray-400 font-normal">Compose 文件</span>
                      </label>
                      <input
                        type="text"
                        className="input"
                        value={editFormData.compose_file || ''}
                        onChange={(e) =>
                          setEditFormData({
                            ...editFormData,
                            compose_file: e.target.value,
                          })
                        }
                        placeholder="docker-compose.yml"
                      />
                      <p className="text-xs text-gray-400 mt-1">
                        相对于工作目录的 docker-compose.yml 路径
                      </p>
                    </div>
                    <div>
                      <label className="label flex items-center justify-between">
                        <span>Compose Service</span>
                        <span className="text-xs text-gray-400 font-normal">主服务名</span>
                      </label>
                      <input
                        type="text"
                        className="input"
                        value={editFormData.compose_service || ''}
                        onChange={(e) =>
                          setEditFormData({
                            ...editFormData,
                            compose_service: e.target.value,
                          })
                        }
                        placeholder="app"
                      />
                      <p className="text-xs text-gray-400 mt-1">
                        docker-compose.yml 中定义的主要应用服务
                      </p>
                    </div>
                    <div>
                      <label className="label flex items-center justify-between">
                        <span>Deploy Strategy</span>
                        <span className="text-xs text-gray-400 font-normal">部署策略</span>
                      </label>
                      <select
                        className="input"
                        value={editFormData.deploy_strategy || ''}
                        onChange={(e) =>
                          setEditFormData({
                            ...editFormData,
                            deploy_strategy: e.target.value,
                          })
                        }
                      >
                        <option value="compose-build">compose-build (构建镜像)</option>
                        <option value="compose-pull">compose-pull (拉取镜像)</option>
                      </select>
                      <p className="text-xs text-gray-400 mt-1">
                        compose-build: 在服务器上构建 | compose-pull: 直接拉取镜像
                      </p>
                    </div>
                    <div>
                      <label className="label flex items-center justify-between">
                        <span>Build Timeout (seconds)</span>
                        <span className="text-xs text-gray-400 font-normal">构建超时</span>
                      </label>
                      <input
                        type="number"
                        className="input"
                        min="60"
                        max="10800"
                        value={editFormData.build_timeout_seconds || 1800}
                        onChange={(e) =>
                          setEditFormData({
                            ...editFormData,
                            build_timeout_seconds: Number(e.target.value),
                          })
                        }
                      />
                      <p className="text-xs text-gray-400 mt-1">
                        依赖下载较慢时可调大，默认 1800 秒
                      </p>
                    </div>
                    <div>
                      <label className="label flex items-center justify-between">
                        <span>Pull Timeout (seconds)</span>
                        <span className="text-xs text-gray-400 font-normal">拉取超时</span>
                      </label>
                      <input
                        type="number"
                        className="input"
                        min="60"
                        max="7200"
                        value={editFormData.pull_timeout_seconds || 900}
                        onChange={(e) =>
                          setEditFormData({
                            ...editFormData,
                            pull_timeout_seconds: Number(e.target.value),
                          })
                        }
                      />
                      <p className="text-xs text-gray-400 mt-1">
                        镜像拉取超时，默认 900 秒
                      </p>
                    </div>
                    <div className="md:col-span-2 flex items-center gap-2">
                      <input
                        type="checkbox"
                        id="edit-build-no-cache"
                        className="h-4 w-4 rounded border-gray-300 text-primary-600"
                        checked={editFormData.build_no_cache ?? false}
                        onChange={(e) =>
                          setEditFormData({
                            ...editFormData,
                            build_no_cache: e.target.checked,
                          })
                        }
                      />
                      <label htmlFor="edit-build-no-cache" className="text-sm text-gray-700">
                        Build without cache（--no-cache；默认使用 Docker 层缓存）
                      </label>
                    </div>
                  </div>
                </div>

                <div className="border-t border-gray-200 pt-4">
                  <h3 className="text-sm font-medium text-gray-900 mb-3 flex items-center gap-2">
                    <Activity className="w-4 h-4 text-gray-500" />
                    健康检查
                  </h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label className="label flex items-center justify-between">
                        <span>Health Check URL</span>
                        <span className="text-xs text-gray-400 font-normal">健康检查地址</span>
                      </label>
                      <input
                        type="text"
                        className="input"
                        value={editFormData.healthcheck_url || ''}
                        onChange={(e) =>
                          setEditFormData({
                            ...editFormData,
                            healthcheck_url: e.target.value || null,
                          })
                        }
                        placeholder="http://127.0.0.1:3000/api/health"
                      />
                      <p className="text-xs text-gray-400 mt-1">
                        Agent 调用此端点判断应用是否正常，建议返回 200 OK
                      </p>
                    </div>
                    <div>
                      <label className="label flex items-center justify-between">
                        <span>Health Check Timeout (seconds)</span>
                        <span className="text-xs text-gray-400 font-normal">超时时间</span>
                      </label>
                      <input
                        type="number"
                        className="input"
                        min="1"
                        max="300"
                        value={editFormData.healthcheck_timeout_seconds || 30}
                        onChange={(e) =>
                          setEditFormData({
                            ...editFormData,
                            healthcheck_timeout_seconds: Number(e.target.value),
                          })
                        }
                      />
                      <p className="text-xs text-gray-400 mt-1">
                        建议根据应用启动时间调整，默认 10 秒
                      </p>
                    </div>
                    <div>
                      <label className="label flex items-center justify-between">
                        <span>Health Check Expected Status</span>
                        <span className="text-xs text-gray-400 font-normal">期望状态码</span>
                      </label>
                      <input
                        type="number"
                        className="input"
                        min="100"
                        max="599"
                        value={editFormData.healthcheck_expected_status || 200}
                        onChange={(e) =>
                          setEditFormData({
                            ...editFormData,
                            healthcheck_expected_status: Number(e.target.value),
                          })
                        }
                      />
                      <p className="text-xs text-gray-400 mt-1">
                        /ready 通常返回 200；如需其他状态码可在此调整
                      </p>
                    </div>
                  </div>
                </div>

                <div className="border-t border-gray-200 pt-4">
                  <h3 className="text-sm font-medium text-gray-900 mb-3 flex items-center gap-2">
                    <Database className="w-4 h-4 text-gray-500" />
                    迁移与 Compose Profiles
                  </h3>
                  <div className="space-y-4">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div>
                        <label className="label flex items-center justify-between">
                          <span>Migration Service</span>
                          <span className="text-xs text-gray-400 font-normal">迁移服务</span>
                        </label>
                        <input
                          type="text"
                          className="input"
                          value={editFormData.migration_service || ''}
                          onChange={(e) =>
                            setEditFormData({
                              ...editFormData,
                              migration_service: e.target.value,
                            })
                          }
                          placeholder="api"
                        />
                        <p className="text-xs text-gray-400 mt-1">
                          执行迁移的 Compose 服务名，配置 Migration Command 时必填
                        </p>
                      </div>
                      <div>
                        <label className="label flex items-center justify-between">
                          <span>Migration Timeout (seconds)</span>
                          <span className="text-xs text-gray-400 font-normal">迁移超时</span>
                        </label>
                        <input
                          type="number"
                          className="input"
                          min="1"
                          max="7200"
                          value={editFormData.migration_timeout_seconds || 600}
                          onChange={(e) =>
                            setEditFormData({
                              ...editFormData,
                              migration_timeout_seconds: Number(e.target.value),
                            })
                          }
                        />
                      </div>
                    </div>
                    <div>
                      <label className="label flex items-center justify-between">
                        <span>Migration Command</span>
                        <span className="text-xs text-gray-400 font-normal">迁移命令</span>
                      </label>
                      <textarea
                        className="input min-h-[72px]"
                        value={editFormData.migration_command || ''}
                        onChange={(e) =>
                          setEditFormData({
                            ...editFormData,
                            migration_command: e.target.value,
                          })
                        }
                        placeholder="alembic upgrade head"
                      />
                      <p className="text-xs text-gray-400 mt-1">
                        在构建后、启动前执行；按 argv 拆分，不走 shell。留空则不执行迁移
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        id="edit-migration-no-deps"
                        className="h-4 w-4 rounded border-gray-300 text-primary-600"
                        checked={editFormData.migration_no_deps ?? true}
                        onChange={(e) =>
                          setEditFormData({
                            ...editFormData,
                            migration_no_deps: e.target.checked,
                          })
                        }
                      />
                      <label htmlFor="edit-migration-no-deps" className="text-sm text-gray-700">
                        Migration without dependencies（--no-deps，默认不拉起依赖服务）
                      </label>
                    </div>
                    <div>
                      <label className="label flex items-center justify-between">
                        <span>Compose Profiles</span>
                        <span className="text-xs text-gray-400 font-normal">显式启用</span>
                      </label>
                      <input
                        type="text"
                        className="input"
                        value={editComposeProfilesText}
                        onChange={(e) => setEditComposeProfilesText(e.target.value)}
                        placeholder="data-sync, sync"
                      />
                      <p className="text-xs text-gray-400 mt-1">
                        逗号分隔；留空表示不启用任何 profile
                      </p>
                    </div>
                  </div>
                </div>

                <div className="border-t border-gray-200 pt-4">
                  <h3 className="text-sm font-medium text-gray-900 mb-3 flex items-center gap-2">
                    <Flag className="w-4 h-4 text-gray-500" />
                    功能开关
                  </h3>
                  <div>
                    <label className="label flex items-center justify-between">
                      <span>Flags File Path</span>
                      <span className="text-xs text-gray-400 font-normal">开关文件</span>
                    </label>
                    <input
                      type="text"
                      className="input"
                      value={editFormData.flags_file_path || ''}
                      onChange={(e) =>
                        setEditFormData({
                          ...editFormData,
                          flags_file_path: e.target.value,
                        })
                      }
                      placeholder="/var/lib/shipsmith/my-saas-app/flags.json"
                    />
                    <p className="text-xs text-gray-400 mt-1">
                      功能开关 JSON 文件路径，应用可读取此文件控制功能开关
                    </p>
                  </div>
                </div>
              </form>
              <div className="p-6 border-t border-gray-200 flex justify-end gap-3">
                <button
                  type="button"
                  onClick={() => setShowEditForm(false)}
                  className="btn btn-secondary"
                >
                  Cancel
                </button>
                <button
                  onClick={handleSaveEdit}
                  className="btn btn-primary"
                  disabled={savingEdit}
                >
                  {savingEdit ? 'Saving...' : 'Save Changes'}
                </button>
              </div>
            </div>
          </div>
        )}

        {showRunbookForm && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
            <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
              <div className="p-6 border-b border-gray-200">
                <h2 className="text-xl font-semibold text-gray-900 flex items-center gap-2">
                  <Notebook className="w-5 h-5" />
                  Edit Runbook
                </h2>
              </div>
              <form
                onSubmit={handleSaveRunbook}
                className="p-6 space-y-4"
              >
                <div>
                  <label className="label flex items-center gap-2">
                    <Notebook className="w-4 h-4 text-gray-500" />
                    Notes
                  </label>
                  <textarea
                    className="input min-h-[80px]"
                    value={runbookFormData.notes || ''}
                    onChange={(e) =>
                      setRunbookFormData({
                        ...runbookFormData,
                        notes: e.target.value,
                      })
                    }
                    placeholder="General notes about this project, architecture decisions, etc."
                  />
                </div>

                <div>
                  <label className="label flex items-center gap-2">
                    <FileEdit className="w-4 h-4 text-gray-500" />
                    Release Notes Hint
                  </label>
                  <textarea
                    className="input min-h-[60px]"
                    value={runbookFormData.release_notes_hint || ''}
                    onChange={(e) =>
                      setRunbookFormData({
                        ...runbookFormData,
                        release_notes_hint: e.target.value,
                      })
                    }
                    placeholder="What to check before release, smoke tests, etc."
                  />
                </div>

                <div>
                  <label className="label flex items-center gap-2">
                    <AlertCircle className="w-4 h-4 text-orange-500" />
                    Troubleshooting Hint
                  </label>
                  <textarea
                    className="input min-h-[80px]"
                    value={runbookFormData.troubleshooting_hint || ''}
                    onChange={(e) =>
                      setRunbookFormData({
                        ...runbookFormData,
                        troubleshooting_hint: e.target.value,
                      })
                    }
                    placeholder="Common issues and how to fix them, emergency procedures"
                  />
                </div>

                <div className="pt-2 border-t border-gray-200">
                  <div className="text-sm font-medium text-gray-700 mb-3">Quick Links</div>
                  <div className="grid grid-cols-1 gap-3">
                    <div>
                      <label className="label flex items-center gap-2">
                        <Database className="w-4 h-4 text-gray-500" />
                        Admin URL
                      </label>
                      <input
                        type="text"
                        className="input"
                        value={runbookFormData.admin_url || ''}
                        onChange={(e) =>
                          setRunbookFormData({
                            ...runbookFormData,
                            admin_url: e.target.value,
                          })
                        }
                        placeholder="https://admin.example.com"
                      />
                    </div>

                    <div>
                      <label className="label flex items-center gap-2">
                        <BarChart3 className="w-4 h-4 text-gray-500" />
                        Metrics URL
                      </label>
                      <input
                        type="text"
                        className="input"
                        value={runbookFormData.metrics_url || ''}
                        onChange={(e) =>
                          setRunbookFormData({
                            ...runbookFormData,
                            metrics_url: e.target.value,
                          })
                        }
                        placeholder="https://grafana.example.com/d/app-dashboard"
                      />
                    </div>

                    <div>
                      <label className="label flex items-center gap-2">
                        <FileSearch className="w-4 h-4 text-gray-500" />
                        Logs URL
                      </label>
                      <input
                        type="text"
                        className="input"
                        value={runbookFormData.logs_url || ''}
                        onChange={(e) =>
                          setRunbookFormData({
                            ...runbookFormData,
                            logs_url: e.target.value,
                          })
                        }
                        placeholder="https://logs.example.com/app/app-name"
                      />
                    </div>

                    <div>
                      <label className="label flex items-center gap-2">
                        <ShieldCheck className="w-4 h-4 text-gray-500" />
                        SSH Hint
                      </label>
                      <input
                        type="text"
                        className="input"
                        value={runbookFormData.ssh_hint || ''}
                        onChange={(e) =>
                          setRunbookFormData({
                            ...runbookFormData,
                            ssh_hint: e.target.value,
                          })
                        }
                        placeholder="ssh user@server.example.com -p 2222"
                      />
                    </div>
                  </div>
                </div>
              </form>
              <div className="p-6 border-t border-gray-200 flex justify-end gap-3">
                <button
                  type="button"
                  onClick={() => setShowRunbookForm(false)}
                  className="btn btn-secondary"
                >
                  Cancel
                </button>
                <button
                  onClick={handleSaveRunbook}
                  className="btn btn-primary"
                  disabled={savingRunbook}
                >
                  {savingRunbook ? 'Saving...' : 'Save Changes'}
                </button>
              </div>
            </div>
          </div>
        )}

        {showDeployModal && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
            <div className="bg-white rounded-lg shadow-xl max-w-lg w-full">
              <div className="p-6 border-b border-gray-200">
                <h2 className="text-xl font-semibold text-gray-900 flex items-center gap-2">
                  <Play className="w-5 h-5" />
                  Deploy Project
                </h2>
                <p className="text-sm text-gray-500 mt-1">
                  选择部署模式，然后开始部署到所有目标。
                </p>
              </div>

              <div className="p-6 space-y-6">
                {targets.length > 0 && (
                  <div>
                    <h3 className="text-sm font-medium text-gray-700 mb-3">
                      Targets ({targets.length})
                    </h3>
                    <div className="space-y-2">
                      {targets
                        .filter((t) => t.enabled)
                        .map((target) => (
                          <div
                            key={target.id}
                            className="flex items-center justify-between p-2 bg-gray-50 rounded-md"
                          >
                            <div className="flex items-center gap-2">
                              <Server className="w-4 h-4 text-gray-500" />
                              <span className="text-sm font-medium">
                                {target.name}
                              </span>
                              <span className="text-xs text-gray-500">
                                #{target.order_index}
                              </span>
                            </div>
                            <span className="text-xs text-gray-500 font-mono">
                              {target.agent_id.substring(0, 12)}...
                            </span>
                          </div>
                        ))}
                    </div>
                  </div>
                )}

                <div>
                  <h3 className="text-sm font-medium text-gray-700 mb-3">
                    Deployment Mode
                  </h3>
                  <div className="grid grid-cols-1 gap-3">
                    <button
                      type="button"
                      onClick={() => setDeployMode('all-at-once')}
                      className={`p-4 rounded-lg border text-left transition-colors ${
                        deployMode === 'all-at-once'
                          ? 'border-primary-500 bg-primary-50'
                          : 'border-gray-200 hover:bg-gray-50'
                      }`}
                    >
                      <div className="flex items-center gap-3">
                        <div
                          className={`w-10 h-10 rounded-full flex items-center justify-center ${
                            deployMode === 'all-at-once'
                              ? 'bg-primary-500 text-white'
                              : 'bg-gray-100 text-gray-600'
                          }`}
                        >
                          <Zap className="w-5 h-5" />
                        </div>
                        <div>
                          <div className="font-medium text-gray-900">
                            All at once
                          </div>
                          <div className="text-xs text-gray-500 mt-0.5">
                            所有目标同时开始部署。适用于无状态服务。
                          </div>
                        </div>
                      </div>
                    </button>

                    <button
                      type="button"
                      onClick={() => setDeployMode('rolling')}
                      className={`p-4 rounded-lg border text-left transition-colors ${
                        deployMode === 'rolling'
                          ? 'border-primary-500 bg-primary-50'
                          : 'border-gray-200 hover:bg-gray-50'
                      }`}
                    >
                      <div className="flex items-center gap-3">
                        <div
                          className={`w-10 h-10 rounded-full flex items-center justify-center ${
                            deployMode === 'rolling'
                              ? 'bg-primary-500 text-white'
                              : 'bg-gray-100 text-gray-600'
                          }`}
                        >
                          <Activity className="w-5 h-5" />
                        </div>
                        <div>
                          <div className="font-medium text-gray-900">
                            Rolling
                          </div>
                          <div className="text-xs text-gray-500 mt-0.5">
                            按顺序逐个部署，前一个成功后再开始下一个。适用于有状态服务。
                          </div>
                        </div>
                      </div>
                    </button>
                  </div>
                </div>
              </div>

              <div className="p-6 border-t border-gray-200 flex justify-end gap-3">
                <button
                  onClick={() => setShowDeployModal(false)}
                  className="btn btn-secondary"
                  disabled={deploying}
                >
                  Cancel
                </button>
                <button
                  onClick={() => handleDeploy()}
                  className="btn btn-primary"
                  disabled={deploying}
                >
                  {deploying ? (
                    <>
                      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      Deploying...
                    </>
                  ) : (
                    <>
                      <Play className="w-4 h-4 mr-2" />
                      Deploy
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </AppLayout>
  );
}
