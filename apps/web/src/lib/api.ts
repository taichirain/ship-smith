const API_BASE = '/api';

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export type EnvironmentType = 'production' | 'staging' | 'development' | 'testing' | 'other';
export type GitCredentialType = 'none' | 'http_token' | 'ssh_key';

export interface Project {
  id: number;
  name: string;
  environment?: EnvironmentType | null;
  git_repo: string;
  git_branch: string;
  git_credential_type: GitCredentialType;
  git_credential_username?: string | null;
  git_credential_token?: string | null;
  git_credential_ssh_private_key?: string | null;
  git_credential_ssh_known_hosts?: string | null;
  git_credential_configured?: boolean;
  deploy_workdir: string;
  compose_file: string;
  compose_service: string;
  deploy_strategy: string;
  healthcheck_url: string | null;
  healthcheck_timeout_seconds: number;
  healthcheck_expected_status: number;
  flags_file_path: string;
  migration_service: string;
  migration_command: string | null;
  migration_timeout_seconds: number;
  migration_no_deps: boolean;
  compose_profiles: string[];
  build_timeout_seconds: number;
  pull_timeout_seconds: number;
  build_no_cache: boolean;
  agent_id: string;
  agent_token?: string;
  webhook_endpoint_id?: string;
  webhook_secret?: string;
  health_status?: string;
  agent_last_seen_at?: string | null;
  current_commit_hash?: string | null;
  last_deployment_status?: string | null;
  last_deployment_at?: string | null;
  agent_version?: string | null;
  agent_version_outdated?: boolean | null;
  notes?: string | null;
  release_notes_hint?: string | null;
  troubleshooting_hint?: string | null;
  admin_url?: string | null;
  metrics_url?: string | null;
  logs_url?: string | null;
  ssh_hint?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ListProjectsParams {
  health_status?: string;
  environment?: string;
  q?: string;
  sort_by?: string;
  sort_order?: string;
}

export interface ProjectUpdate {
  name?: string;
  environment?: EnvironmentType | null;
  git_repo?: string;
  git_branch?: string;
  git_credential_type?: GitCredentialType;
  git_credential_username?: string | null;
  git_credential_token?: string | null;
  git_credential_ssh_private_key?: string | null;
  git_credential_ssh_known_hosts?: string | null;
  deploy_workdir?: string;
  compose_file?: string;
  compose_service?: string;
  deploy_strategy?: string;
  healthcheck_url?: string | null;
  healthcheck_timeout_seconds?: number;
  healthcheck_expected_status?: number;
  flags_file_path?: string;
  migration_service?: string;
  migration_command?: string | null;
  migration_timeout_seconds?: number;
  migration_no_deps?: boolean;
  compose_profiles?: string[];
  build_timeout_seconds?: number;
  pull_timeout_seconds?: number;
  build_no_cache?: boolean;
  webhook_secret?: string;
  notes?: string | null;
  release_notes_hint?: string | null;
  troubleshooting_hint?: string | null;
  admin_url?: string | null;
  metrics_url?: string | null;
  logs_url?: string | null;
  ssh_hint?: string | null;
}

export interface Deployment {
  id: number;
  project_id: number;
  kind: string;
  status: string;
  trigger_source: string;
  commit_hash: string | null;
  target_deployment_id: number | null;
  log_excerpt: string | null;
  error_code: string | null;
  failure_phase?: string | null;
  triggered_by: string | null;
  queued_at: string;
  started_at: string | null;
  finished_at: string | null;
  last_heartbeat_at?: string | null;
  lease_expires_at?: string | null;
}

export interface DeploymentLog {
  id: number;
  deployment_id: number;
  seq: number;
  phase: string | null;
  content: string;
  created_at: string;
}

export interface FeatureFlag {
  id: number;
  project_id: number;
  key: string;
  enabled: boolean;
  description: string | null;
  version: number;
  updated_by: string | null;
  updated_at: string;
  archived?: boolean;
}

export interface ProjectStatus {
  project_id: number;
  agent_last_seen_at: string | null;
  health_status: string;
  current_commit_hash: string | null;
  last_deployment_id: number | null;
  updated_at: string;
  cpu_percent?: number;
  mem_used_mb?: number;
  mem_total_mb?: number;
  disk_used_percent?: number;
  containers?: Array<{
    service: string;
    status: string;
    image?: string;
    ports?: string[];
  }>;
  app_health?: {
    status: string;
    response_ms?: number;
    http_status?: number;
    error?: string;
  };
  runtime?: {
    os_name?: string | null;
    os_release?: string | null;
    os_version?: string | null;
    platform?: string | null;
    machine?: string | null;
    python_version?: string | null;
    shell?: string | null;
    path_separator?: string | null;
    docker_compose_command?: string | null;
  };
  agent_version?: string | null;
  agent_version_outdated?: boolean | null;
  intentionally_stopped?: boolean;
}

export interface GenerateDeployCommandsRequest {
  user_goal?: string;
  preferred_shell?: string;
  extra_context?: string;
}

export interface DeployCommandPlan {
  title: string;
  command: string;
  purpose: string;
}

export interface GenerateDeployCommandsResponse {
  project_id: number;
  source_files: string[];
  system_summary: Record<string, any>;
  assumptions: string[];
  prechecks: string[];
  commands: DeployCommandPlan[];
  verification: string[];
  explanation: string;
  llm_provider?: string | null;
  llm_model?: string | null;
  llm_duration_ms?: number | null;
}

export type AnomalyType = 'agent_offline' | 'health_unhealthy' | 'health_degraded' | 'last_deploy_failed';
export type EventCategory = 'deployment' | 'rollback' | 'flag_audit' | 'webhook' | 'operation';

export interface DashboardSummary {
  total_projects: number;
  healthy_projects: number;
  degraded_projects: number;
  unhealthy_projects: number;
  offline_projects: number;
  stopped_projects: number;
  last_24h_deployments_success: number;
  last_24h_deployments_failed: number;
}

export interface AnomalyProject {
  project_id: number;
  project_name: string;
  anomaly_types: AnomalyType[];
  health_status: string | null;
  agent_last_seen_at: string | null;
  last_deployment_status: string | null;
  last_deployment_id: number | null;
  last_deployment_at: string | null;
}

export interface ChangeEvent {
  event_category: EventCategory;
  event_type: string;
  occurred_at: string;
  project_id: number;
  project_name: string;
  title: string;
  summary: string | null;
  actor: string | null;
  deployment_id: number | null;
  flag_key: string | null;
}

export interface DashboardSummaryResponse {
  summary: DashboardSummary;
  anomaly_projects: AnomalyProject[];
  recent_changes: ChangeEvent[];
}

export type TimelineEventType =
  | 'deployment_queued'
  | 'deployment_running'
  | 'deployment_success'
  | 'deployment_failed'
  | 'rollback_queued'
  | 'rollback_running'
  | 'rollback_success'
  | 'rollback_failed'
  | 'flag_created'
  | 'flag_updated'
  | 'flag_archived'
  | 'flag_unarchived'
  | 'config_updated'
  | 'webhook_accepted'
  | 'webhook_ignored'
  | 'agent_offline'
  | 'agent_recovered'
  | 'operation_queued'
  | 'operation_running'
  | 'operation_success'
  | 'operation_failed';

export interface TimelineEvent {
  id: string;
  type: TimelineEventType;
  occurred_at: string;
  title: string;
  summary: string | null;
  actor: string | null;
  metadata: Record<string, any>;
}

export interface TimelineResponse {
  events: TimelineEvent[];
  total: number;
}

export interface ListTimelineParams {
  limit?: number;
  offset?: number;
  event_type?: TimelineEventType;
}

export interface HealthHistoryRecord {
  timestamp: string;
  health_status: string;
  response_ms?: number | null;
  heartbeat_present: boolean;
}

export interface DeploymentMarker {
  timestamp: string;
  deployment_id: number;
  status: string;
  kind: string;
  commit_hash?: string | null;
}

export interface HealthHistoryResponse {
  records: HealthHistoryRecord[];
  deployment_markers: DeploymentMarker[];
}

export interface ProjectTarget {
  id: number;
  project_id: number;
  agent_id: string;
  name: string;
  role: string;
  enabled: boolean;
  order_index: number;
  created_at: string;
  updated_at: string;
}

export interface ProjectTargetCreate {
  agent_id: string;
  name?: string;
  role?: string;
  enabled?: boolean;
  order_index?: number;
}

export interface ProjectTargetUpdate {
  name?: string;
  role?: string;
  enabled?: boolean;
  order_index?: number;
}

export interface DeploymentTarget {
  id: number;
  deployment_id: number;
  project_target_id: number | null;
  agent_id: string;
  status: string;
  commit_hash: string | null;
  started_at: string | null;
  finished_at: string | null;
  error_code: string | null;
  error_message: string | null;
  last_heartbeat_at: string | null;
  target_name?: string;
  target_role?: string;
  target_order_index?: number;
}

export interface DeploymentDetailWithTargets extends Deployment {
  total_logs?: number;
  last_log_seq?: number;
  targets?: DeploymentTarget[];
  target_stats?: {
    total: number;
    success: number;
    failed: number;
    running: number;
    queued: number;
    blocked: number;
    cancelled: number;
  };
}

export type InstallMode = 'standard' | 'dry-run';
export type TargetPlatform = 'linux-systemd' | 'linux-docker' | 'manual';
export type AgentOnboardingStatus = 'waiting' | 'online' | 'failed' | 'expired';

export interface InstallCommandRequest {
  install_mode?: InstallMode;
  target_platform?: TargetPlatform;
  core_url?: string;
  workdir?: string;
}

export interface InstallCommandResponse {
  project_id: number;
  install_mode: string;
  target_platform: string;
  command: string;
  expires_at: string | null;
  manual_install_url: string | null;
  notes: string[];
  agent_id: string;
  core_url: string;
  workdir: string;
}

export interface OnboardingStatusResponse {
  project_id: number;
  agent_id: string;
  core_url: string;
  workdir: string;
  status: AgentOnboardingStatus;
  agent_first_seen_at: string | null;
  agent_last_seen_at: string | null;
  health_status: string | null;
  install_command: string | null;
  install_command_expires_at: string | null;
  manual_steps_available: boolean;
  troubleshooting_hints: string[];
}

export interface GitBranchInfo {
  name: string;
  is_default: boolean;
}

export interface GitBranchesResponse {
  branches: GitBranchInfo[];
  repo: string;
  success: boolean;
  error: string | null;
}

export interface ComposeServiceInfo {
  name: string;
  is_default: boolean;
}

export interface ComposeServicesRequest extends GitBranchesRequest {
  git_branch: string;
  compose_file: string;
}

export interface ComposeServicesResponse {
  services: ComposeServiceInfo[];
  compose_file: string;
  success: boolean;
  error: string | null;
}

export interface GitBranchesRequest {
  git_repo: string;
  git_credential_type?: GitCredentialType;
  git_credential_username?: string | null;
  git_credential_token?: string | null;
  git_credential_ssh_private_key?: string | null;
  git_credential_ssh_known_hosts?: string | null;
}

export type TimeRange = '24h' | '7d';

class ApiError extends Error {
  status: number;
  data: any;

  constructor(message: string, status: number, data?: any) {
    super(message);
    this.status = status;
    this.data = data;
  }
}

let tokenCache: string | null = null;

export function getToken(): string | null {
  if (tokenCache) return tokenCache;
  if (typeof window !== 'undefined') {
    tokenCache = localStorage.getItem('shipsmith_token');
  }
  return tokenCache;
}

export function setToken(token: string): void {
  tokenCache = token;
  if (typeof window !== 'undefined') {
    localStorage.setItem('shipsmith_token', token);
  }
}

export function clearToken(): void {
  tokenCache = null;
  if (typeof window !== 'undefined') {
    localStorage.removeItem('shipsmith_token');
  }
}

async function request<T>(
  method: 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE',
  path: string,
  data?: any,
  requiresAuth: boolean = true,
): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };

  if (requiresAuth) {
    const token = getToken();
    if (!token) {
      throw new ApiError('Not authenticated', 401);
    }
    headers['Authorization'] = `Bearer ${token}`;
  }

  const options: RequestInit = {
    method,
    headers,
  };

  if (data) {
    options.body = JSON.stringify(data);
  }

  const response = await fetch(`${API_BASE}${path}`, options);

  let responseData: any = null;
  try {
    responseData = await response.json();
  } catch {}

  if (!response.ok) {
    if (response.status === 401) {
      clearToken();
    }
    throw new ApiError(
      responseData?.detail || response.statusText,
      response.status,
      responseData,
    );
  }

  return responseData as T;
}

export type ChannelType = 'webhook' | 'feishu' | 'slack';
export type NotificationEventType =
  | 'deployment_success'
  | 'deployment_failed'
  | 'agent_offline'
  | 'health_degraded'
  | 'health_unhealthy'
  | 'health_recovered';

export type AlertStatus = 'open' | 'acknowledged' | 'resolved';
export type AlertType = 'agent_offline' | 'deployment_failed' | 'health_unhealthy';

export interface Alert {
  id: number;
  project_id: number;
  project_name?: string | null;
  alert_type: AlertType;
  fingerprint: string;
  status: AlertStatus;
  title: string;
  message: string | null;
  metadata: Record<string, any>;
  acknowledged_by: string | null;
  acknowledged_at: string | null;
  resolved_by: string | null;
  resolved_at: string | null;
  first_seen_at: string;
  last_seen_at: string;
  created_at: string;
  updated_at: string;
}

export interface AlertListResponse {
  alerts: Alert[];
  total: number;
  open_count: number;
  acknowledged_count: number;
  resolved_count: number;
}

export interface NotificationChannel {
  id: number;
  project_id: number;
  name: string;
  channel_type: ChannelType;
  is_active: boolean;
  config: Record<string, any>;
  created_at: string;
  updated_at: string;
}

export interface NotificationChannelCreate {
  name: string;
  channel_type: ChannelType;
  is_active: boolean;
  config: Record<string, any>;
}

export interface NotificationSetting {
  id: number;
  project_id: number;
  event_type: NotificationEventType;
  enabled: boolean;
  channel_ids: number[];
  cooldown_seconds: number;
  send_recovery: boolean;
  created_at: string;
  updated_at: string;
}

export interface NotificationSettingUpdate {
  enabled?: boolean;
  channel_ids?: number[];
  cooldown_seconds?: number;
  send_recovery?: boolean;
}

export interface NotificationDelivery {
  id: number;
  channel_id: number;
  project_id: number;
  event_type: string;
  fingerprint: string | null;
  is_recovery: boolean;
  is_suppressed: boolean;
  status: string;
  error_message: string | null;
  sent_at: string | null;
  created_at: string;
}

export const api = {
  getToken,
  async login(username: string, password: string): Promise<TokenResponse> {
    const formData = new URLSearchParams();
    formData.append('username', username);
    formData.append('password', password);

    const response = await fetch(`${API_BASE}/v1/auth/login`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: formData.toString(),
    });

    if (!response.ok) {
      throw new ApiError('Invalid credentials', response.status);
    }

    const data = await response.json();
    return data;
  },

  async listNotificationChannels(projectId?: number): Promise<NotificationChannel[]> {
    const path = projectId !== undefined
      ? `/v1/notifications/channels?project_id=${projectId}`
      : '/v1/notifications/channels';
    return request<NotificationChannel[]>('GET', path);
  },

  async createNotificationChannel(projectId: number, data: NotificationChannelCreate): Promise<NotificationChannel> {
    return request<NotificationChannel>('POST', `/v1/notifications/channels?project_id=${projectId}`, data);
  },

  async updateNotificationChannel(channelId: number, data: Partial<NotificationChannelCreate>): Promise<NotificationChannel> {
    return request<NotificationChannel>('PATCH', `/v1/notifications/channels/${channelId}`, data);
  },

  async deleteNotificationChannel(channelId: number): Promise<void> {
    return request<void>('DELETE', `/v1/notifications/channels/${channelId}`);
  },

  async listNotificationSettings(projectId: number): Promise<NotificationSetting[]> {
    return request<NotificationSetting[]>('GET', `/v1/notifications/settings?project_id=${projectId}`);
  },

  async updateNotificationSetting(settingId: number, data: NotificationSettingUpdate): Promise<NotificationSetting> {
    return request<NotificationSetting>('PATCH', `/v1/notifications/settings/${settingId}`, data);
  },

  async listNotificationDeliveries(projectId: number, channelId?: number, eventType?: NotificationEventType, limit: number = 50): Promise<NotificationDelivery[]> {
    const query = new URLSearchParams();
    query.append('project_id', projectId.toString());
    if (channelId !== undefined) query.append('channel_id', channelId.toString());
    if (eventType) query.append('event_type', eventType);
    query.append('limit', limit.toString());
    return request<NotificationDelivery[]>('GET', `/v1/notifications/deliveries?${query.toString()}`);
  },

  async testNotificationChannel(channelId: number, eventType?: NotificationEventType): Promise<{ success: boolean; message: string }> {
    return request<{ success: boolean; message: string }>('POST', '/v1/notifications/test', {
      channel_id: channelId,
      event_type: eventType,
    });
  },

  async listProjects(params?: ListProjectsParams): Promise<Project[]> {
    const query = new URLSearchParams();
    if (params?.health_status) query.append('health_status', params.health_status);
    if (params?.environment) query.append('environment', params.environment);
    if (params?.q) query.append('q', params.q);
    if (params?.sort_by) query.append('sort_by', params.sort_by);
    if (params?.sort_order) query.append('sort_order', params.sort_order);
    const queryString = query.toString();
    const path = queryString ? `/v1/projects?${queryString}` : '/v1/projects';
    return request<Project[]>('GET', path);
  },

  async getProject(id: number): Promise<Project> {
    return request<Project>('GET', `/v1/projects/${id}`);
  },

  async createProject(project: Partial<Project> & { name: string; git_repo: string; deploy_workdir: string; flags_file_path: string }): Promise<Project> {
    return request<Project>('POST', '/v1/projects', project);
  },

  async updateProject(projectId: number, updates: ProjectUpdate): Promise<Project> {
    return request<Project>('PATCH', `/v1/projects/${projectId}`, updates);
  },

  async rotateAgentToken(projectId: number): Promise<{ agent_id: string; agent_token: string }> {
    return request<{ agent_id: string; agent_token: string }>('POST', `/v1/projects/${projectId}/rotate-agent-token`);
  },

  async getProjectStatus(projectId: number): Promise<ProjectStatus> {
    return request<ProjectStatus>('GET', `/v1/projects/${projectId}/status`);
  },

  async generateDeployCommands(
    projectId: number,
    data?: GenerateDeployCommandsRequest,
  ): Promise<GenerateDeployCommandsResponse> {
    return request<GenerateDeployCommandsResponse>(
      'POST',
      `/v1/projects/${projectId}/generate-deploy-commands`,
      data || {},
    );
  },

  async triggerAgentPrecheck(projectId: number): Promise<{
    ok: boolean;
    deployment_id: number;
    status: string;
    message: string;
  }> {
    return request<{
      ok: boolean;
      deployment_id: number;
      status: string;
      message: string;
    }>('POST', `/v1/projects/${projectId}/precheck`);
  },

  async getLatestPrecheck(projectId: number): Promise<{
    pending_task: {
      id: number;
      status: string;
      started_at: string | null;
      queued_at: string | null;
    } | null;
    latest_precheck: {
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
      result_json: any;
      started_at: string | null;
      finished_at: string | null;
      created_at: string | null;
    } | null;
  }> {
    return request<{
      pending_task: {
        id: number;
        status: string;
        started_at: string | null;
        queued_at: string | null;
      } | null;
      latest_precheck: {
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
        result_json: any;
        started_at: string | null;
        finished_at: string | null;
        created_at: string | null;
      } | null;
    }>('GET', `/v1/projects/${projectId}/prechecks/latest`);
  },

  async listPrechecks(projectId: number, limit: number = 10): Promise<{
    total: number;
    prechecks: Array<{
      id: number;
      project_id: number;
      agent_id: string;
      overall_status: string;
      summary: any;
      result_json: any;
      started_at: string | null;
      finished_at: string | null;
      created_at: string | null;
    }>;
  }> {
    return request<{
      total: number;
      prechecks: Array<{
        id: number;
        project_id: number;
        agent_id: string;
        overall_status: string;
        summary: any;
        result_json: any;
        started_at: string | null;
        finished_at: string | null;
        created_at: string | null;
      }>;
    }>('GET', `/v1/projects/${projectId}/prechecks?limit=${limit}`);
  },

  async generateWebhookSecret(projectId: number): Promise<{ ok: boolean; webhook_secret: string; webhook_endpoint: string }> {
    return request<{ ok: boolean; webhook_secret: string; webhook_endpoint: string }>('POST', `/v1/projects/${projectId}/generate-webhook-secret`);
  },

  async listGitBranches(data: GitBranchesRequest): Promise<GitBranchesResponse> {
    return request<GitBranchesResponse>('POST', `/v1/projects/git-branches`, data);
  },

  async listComposeServices(data: ComposeServicesRequest): Promise<ComposeServicesResponse> {
    return request<ComposeServicesResponse>('POST', `/v1/projects/compose-services`, data);
  },

  async listProjectTargets(projectId: number): Promise<ProjectTarget[]> {
    return request<ProjectTarget[]>('GET', `/v1/projects/${projectId}/targets`);
  },

  async createProjectTarget(projectId: number, data: ProjectTargetCreate): Promise<ProjectTarget> {
    return request<ProjectTarget>('POST', `/v1/projects/${projectId}/targets`, data);
  },

  async updateProjectTarget(projectId: number, targetId: number, data: ProjectTargetUpdate): Promise<ProjectTarget> {
    return request<ProjectTarget>('PATCH', `/v1/projects/${projectId}/targets/${targetId}`, data);
  },

  async deleteProjectTarget(projectId: number, targetId: number): Promise<void> {
    return request<void>('DELETE', `/v1/projects/${projectId}/targets/${targetId}`);
  },

  async getOnboardingStatus(projectId: number): Promise<OnboardingStatusResponse> {
    return request<OnboardingStatusResponse>('GET', `/v1/projects/${projectId}/onboarding`);
  },

  async getProjectOnboarding(projectId: number): Promise<OnboardingStatusResponse> {
    return request<OnboardingStatusResponse>('GET', `/v1/projects/${projectId}/onboarding`);
  },

  async generateInstallCommand(
    projectId: number,
    data?: InstallCommandRequest,
  ): Promise<InstallCommandResponse> {
    return request<InstallCommandResponse>(
      'POST',
      `/v1/projects/${projectId}/install-command`,
      data || {},
    );
  },

  async deployProject(projectId: number, commitHash?: string, deployMode?: 'all-at-once' | 'rolling'): Promise<Deployment> {
    return request<Deployment>('POST', `/v1/projects/${projectId}/deploy`, {
      commit_hash: commitHash || null,
      trigger_source: 'manual',
      deploy_mode: deployMode || 'all-at-once',
    });
  },

  async rollbackProject(projectId: number, targetDeploymentId: number): Promise<Deployment> {
    return request<Deployment>('POST', `/v1/projects/${projectId}/rollback`, {
      target_deployment_id: targetDeploymentId,
    });
  },

  async rollbackToLastSuccess(projectId: number): Promise<Deployment> {
    return request<Deployment>('POST', `/v1/projects/${projectId}/rollback-to-last-success`);
  },

  async stopProject(projectId: number): Promise<Deployment> {
    return request<Deployment>('POST', `/v1/projects/${projectId}/stop`);
  },

  async startProject(projectId: number): Promise<Deployment> {
    return request<Deployment>('POST', `/v1/projects/${projectId}/start`);
  },

  async listDeployments(projectId: number, limit: number = 50): Promise<Deployment[]> {
    return request<Deployment[]>('GET', `/v1/projects/${projectId}/deployments?limit=${limit}`);
  },

  async getDeployment(id: number): Promise<Deployment> {
    return request<Deployment>('GET', `/v1/deployments/${id}`);
  },

  async getDeploymentDetail(id: number): Promise<DeploymentDetailWithTargets> {
    return request<DeploymentDetailWithTargets>('GET', `/v1/deployments/${id}/detail`);
  },

  async getDeploymentLogs(id: number, afterSeq?: number): Promise<DeploymentLog[]> {
    const path = afterSeq !== undefined && afterSeq >= 0
      ? `/v1/deployments/${id}/logs?after_seq=${afterSeq}`
      : `/v1/deployments/${id}/logs`;
    return request<DeploymentLog[]>('GET', path);
  },

  async retryDeployment(deploymentId: number): Promise<Deployment> {
    return request<Deployment>('POST', `/v1/deployments/${deploymentId}/retry`);
  },

  async getDeploymentFailureExplanation(deploymentId: number): Promise<{
    error_code: string | null;
    failure_phase: string | null;
    failure_phase_label: string;
    title: string;
    category: string;
    human_explanation: string;
    checklist: Array<{
      action: string;
      command?: string;
      description: string;
    }>;
    resolution_steps: string[];
    log_analysis: {
      extracted_errors: string[];
      patterns_detected: Array<{
        key: string;
        label: string;
        matched_lines: string[];
      }>;
    };
    additional_notes?: string[];
    llm_analysis?: {
      root_cause?: string;
      likely_problem?: string;
      first_checks?: string[];
      debug_commands?: string[];
      explanation?: string;
      llm_provider?: string;
      llm_model?: string;
      llm_duration_ms?: number;
      llm_analysis_failed?: boolean;
      llm_error?: string;
    };
  }> {
    return request<{
      error_code: string | null;
      failure_phase: string | null;
      failure_phase_label: string;
      title: string;
      category: string;
      human_explanation: string;
      checklist: Array<{
        action: string;
        command?: string;
        description: string;
      }>;
      resolution_steps: string[];
      log_analysis: {
        extracted_errors: string[];
        patterns_detected: Array<{
          key: string;
          label: string;
          matched_lines: string[];
        }>;
      };
      additional_notes?: string[];
      llm_analysis?: {
        root_cause?: string;
        likely_problem?: string;
        first_checks?: string[];
        debug_commands?: string[];
        explanation?: string;
        llm_provider?: string;
        llm_model?: string;
        llm_duration_ms?: number;
        llm_analysis_failed?: boolean;
        llm_error?: string;
      };
    }>('GET', `/v1/deployments/${deploymentId}/failure-explanation`);
  },

  getDeploymentLogsDownloadUrl(deploymentId: number): string {
    return `${API_BASE}/v1/deployments/${deploymentId}/logs/download`;
  },

  async listFlags(projectId: number, includeArchived: boolean = false): Promise<FeatureFlag[]> {
    return request<FeatureFlag[]>('GET', `/v1/projects/${projectId}/flags?include_archived=${includeArchived}`);
  },

  async getFlagsSnapshot(projectId: number): Promise<{
    project_id: number;
    version: number;
    flags_count: number;
    flags: Record<string, boolean>;
    updated_at: string | null;
  }> {
    return request<{
      project_id: number;
      version: number;
      flags_count: number;
      flags: Record<string, boolean>;
      updated_at: string | null;
    }>('GET', `/v1/projects/${projectId}/flags/snapshot`);
  },

  async createFlag(projectId: number, flag: { key: string; enabled: boolean; description?: string }): Promise<FeatureFlag> {
    return request<FeatureFlag>('POST', `/v1/projects/${projectId}/flags`, flag);
  },

  async updateFlag(flagId: number, updates: { enabled?: boolean; description?: string }): Promise<FeatureFlag> {
    return request<FeatureFlag>('PATCH', `/v1/flags/${flagId}`, updates);
  },

  async archiveFlag(flagId: number): Promise<{ ok: boolean; flag_id: number; flag_key: string; archived: boolean }> {
    return request<{ ok: boolean; flag_id: number; flag_key: string; archived: boolean }>('POST', `/v1/flags/${flagId}/archive`);
  },

  async unarchiveFlag(flagId: number): Promise<{ ok: boolean; flag_id: number; flag_key: string; archived: boolean }> {
    return request<{ ok: boolean; flag_id: number; flag_key: string; archived: boolean }>('POST', `/v1/flags/${flagId}/unarchive`);
  },

  async deleteFlag(flagId: number): Promise<{ ok: boolean; flag_id: number; deleted: boolean }> {
    return request<{ ok: boolean; flag_id: number; deleted: boolean }>('DELETE', `/v1/flags/${flagId}`);
  },

  async getDashboardSummary(): Promise<DashboardSummaryResponse> {
    return request<DashboardSummaryResponse>('GET', '/v1/dashboard/summary');
  },

  async getProjectTimeline(projectId: number, params?: ListTimelineParams): Promise<TimelineResponse> {
    const query = new URLSearchParams();
    if (params?.limit !== undefined) query.append('limit', params.limit.toString());
    if (params?.offset !== undefined) query.append('offset', params.offset.toString());
    if (params?.event_type) query.append('event_type', params.event_type);
    const queryString = query.toString();
    const path = queryString
      ? `/v1/projects/${projectId}/timeline?${queryString}`
      : `/v1/projects/${projectId}/timeline`;
    return request<TimelineResponse>('GET', path);
  },

  async getProjectHealthHistory(projectId: number, timeRange: TimeRange = '24h'): Promise<HealthHistoryResponse> {
    return request<HealthHistoryResponse>('GET', `/v1/projects/${projectId}/health-history?time_range=${timeRange}`);
  },

  async listAlerts(params?: {
    project_id?: number;
    status?: AlertStatus[];
    alert_type?: AlertType;
    limit?: number;
    offset?: number;
  }): Promise<AlertListResponse> {
    const query = new URLSearchParams();
    if (params?.project_id !== undefined) query.append('project_id', params.project_id.toString());
    if (params?.status) params.status.forEach(s => query.append('status', s));
    if (params?.alert_type) query.append('alert_type', params.alert_type);
    if (params?.limit !== undefined) query.append('limit', params.limit.toString());
    if (params?.offset !== undefined) query.append('offset', params.offset.toString());
    const queryString = query.toString();
    const path = queryString ? `/v1/alerts?${queryString}` : '/v1/alerts';
    return request<AlertListResponse>('GET', path);
  },

  async acknowledgeAlert(alertId: number): Promise<Alert> {
    return request<Alert>('POST', `/v1/alerts/${alertId}/acknowledge`);
  },

  async resolveAlert(alertId: number): Promise<Alert> {
    return request<Alert>('POST', `/v1/alerts/${alertId}/resolve`);
  },
};
