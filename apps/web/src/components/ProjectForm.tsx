'use client';

import { useState, useEffect, useCallback } from 'react';
import {
  FolderGit2,
  GitCommit,
  Server,
  Activity,
  Flag,
  X,
  RefreshCw,
  Loader2,
  Database,
} from 'lucide-react';
import { api, Project, EnvironmentType, GitBranchInfo, GitCredentialType, ComposeServiceInfo } from '@/lib/api';

const ENVIRONMENT_OPTIONS: { value: EnvironmentType; label: string; color: string }[] = [
  { value: 'production', label: '生产环境', color: 'bg-red-100 text-red-800 border-red-200' },
  { value: 'staging', label: '预发环境', color: 'bg-orange-100 text-orange-800 border-orange-200' },
  { value: 'development', label: '开发环境', color: 'bg-green-100 text-green-800 border-green-200' },
  { value: 'testing', label: '测试环境', color: 'bg-blue-100 text-blue-800 border-blue-200' },
  { value: 'other', label: '其他', color: 'bg-gray-100 text-gray-800 border-gray-200' },
];

const PROJECT_FORM_DRAFT_KEY = 'shipsmith_project_form_draft_v1';

const FORM_DEFAULTS: Partial<FormData> = {
  environment: null,
  git_branch: 'main',
  compose_file: 'docker-compose.yml',
  compose_service: 'app',
  deploy_strategy: 'compose-build',
  healthcheck_url: '',
  healthcheck_timeout_seconds: 10,
  healthcheck_expected_status: 200,
  migration_service: '',
  migration_command: '',
  migration_timeout_seconds: 600,
  migration_no_deps: true,
  compose_profiles: '',
  build_timeout_seconds: 1800,
  pull_timeout_seconds: 900,
  build_no_cache: false,
  service_scope: 'app',
};

function isFormEmpty(data: FormData): boolean {
  return !Object.entries(data).some(([key, value]) => {
    const defaultValue = FORM_DEFAULTS[key as keyof FormData];
    if (defaultValue === undefined) {
      if (typeof value === 'string') return value.trim() !== '';
      return value !== null && value !== undefined;
    }
    if (typeof value === 'string') return value.trim() !== String(defaultValue).trim();
    return value !== defaultValue;
  });
}

interface FormData {
  name: string;
  environment: EnvironmentType | null;
  git_repo: string;
  git_branch: string;
  git_credential_type: GitCredentialType;
  git_credential_username: string;
  git_credential_token: string;
  git_credential_ssh_private_key: string;
  git_credential_ssh_known_hosts: string;
  deploy_workdir: string;
  compose_file: string;
  compose_service: string;
  deploy_strategy: string;
  healthcheck_url: string;
  healthcheck_timeout_seconds: number;
  healthcheck_expected_status: number;
  flags_file_path: string;
  migration_service: string;
  migration_command: string;
  migration_timeout_seconds: number;
  migration_no_deps: boolean;
  compose_profiles: string;
  build_timeout_seconds: number;
  pull_timeout_seconds: number;
  build_no_cache: boolean;
  service_scope: string;
}

interface ProjectFormProps {
  onClose: () => void;
  onSuccess: (project: Project) => void;
  onError: (error: string) => void;
}

function generateFlagsPath(name: string): string {
  return `/var/lib/shipsmith/${name}/flags.json`;
}

function generateWorkdir(name: string): string {
  return `/opt/${name}`;
}

export default function ProjectForm({ onClose, onSuccess, onError }: ProjectFormProps) {
  const [saving, setSaving] = useState(false);
  const [formData, setFormData] = useState<FormData>({
    name: '',
    environment: null,
    git_repo: '',
    git_branch: 'main',
    git_credential_type: 'none',
    git_credential_username: '',
    git_credential_token: '',
    git_credential_ssh_private_key: '',
    git_credential_ssh_known_hosts: '',
    deploy_workdir: '',
    compose_file: 'docker-compose.yml',
    compose_service: 'app',
    deploy_strategy: 'compose-build',
    healthcheck_url: '',
    healthcheck_timeout_seconds: 10,
    healthcheck_expected_status: 200,
    flags_file_path: '',
    migration_service: '',
    migration_command: '',
    migration_timeout_seconds: 600,
    migration_no_deps: true,
    compose_profiles: '',
    build_timeout_seconds: 1800,
    pull_timeout_seconds: 900,
    build_no_cache: false,
    service_scope: 'app',
  });

  const [gitBranches, setGitBranches] = useState<GitBranchInfo[]>([]);
  const [loadingBranches, setLoadingBranches] = useState(false);
  const [branchError, setBranchError] = useState<string | null>(null);
  const [composeServices, setComposeServices] = useState<ComposeServiceInfo[]>([]);
  const [loadingComposeServices, setLoadingComposeServices] = useState(false);
  const [composeServiceError, setComposeServiceError] = useState<string | null>(null);
  const [hasLoadedDraft, setHasLoadedDraft] = useState(false);

  const loadBranches = useCallback(async (gitRepo: string) => {
    const trimmed = gitRepo.trim();
    if (!trimmed) {
      setGitBranches([]);
      setBranchError(null);
      return;
    }

    try {
      setLoadingBranches(true);
      setBranchError(null);
      const result = await api.listGitBranches({
        git_repo: trimmed,
        git_credential_type: formData.git_credential_type,
        git_credential_username: formData.git_credential_username || null,
        git_credential_token: formData.git_credential_token || null,
        git_credential_ssh_private_key: formData.git_credential_ssh_private_key || null,
        git_credential_ssh_known_hosts: formData.git_credential_ssh_known_hosts || null,
      });

      if (result.success && result.branches.length > 0) {
        setGitBranches(result.branches);
        const defaultBranch = result.branches.find((b) => b.is_default);
        if (defaultBranch && !formData.git_branch) {
          setFormData((prev) => ({ ...prev, git_branch: defaultBranch.name }));
        }
      } else {
        setGitBranches([]);
        setBranchError(result.error || 'No branches found');
      }
    } catch (err: any) {
      setGitBranches([]);
      setBranchError(err.message || 'Failed to load branches');
    } finally {
      setLoadingBranches(false);
    }
  }, [
    formData.git_branch,
    formData.git_credential_type,
    formData.git_credential_username,
    formData.git_credential_token,
    formData.git_credential_ssh_private_key,
    formData.git_credential_ssh_known_hosts,
  ]);

  const loadComposeServices = useCallback(async () => {
    const gitRepo = formData.git_repo.trim();
    const gitBranch = formData.git_branch.trim();
    const composeFile = formData.compose_file.trim();

    if (!gitRepo || !gitBranch || !composeFile) {
      setComposeServices([]);
      setComposeServiceError(null);
      return;
    }

    try {
      setLoadingComposeServices(true);
      setComposeServiceError(null);
      const result = await api.listComposeServices({
        git_repo: gitRepo,
        git_branch: gitBranch,
        compose_file: composeFile,
        git_credential_type: formData.git_credential_type,
        git_credential_username: formData.git_credential_username || null,
        git_credential_token: formData.git_credential_token || null,
        git_credential_ssh_private_key: formData.git_credential_ssh_private_key || null,
        git_credential_ssh_known_hosts: formData.git_credential_ssh_known_hosts || null,
      });

      if (result.success && result.services.length > 0) {
        setComposeServices(result.services);
        const defaultService = result.services.find((item) => item.is_default);
        if (defaultService) {
          setFormData((prev) => ({
            ...prev,
            compose_service:
              !prev.compose_service || prev.compose_service === 'app'
                ? defaultService.name
                : prev.compose_service,
          }));
        }
      } else {
        setComposeServices([]);
        setComposeServiceError(result.error || 'No services found');
      }
    } catch (err: any) {
      setComposeServices([]);
      setComposeServiceError(err.message || 'Failed to inspect compose file');
    } finally {
      setLoadingComposeServices(false);
    }
  }, [
    formData.git_repo,
    formData.git_branch,
    formData.compose_file,
    formData.compose_service,
    formData.git_credential_type,
    formData.git_credential_username,
    formData.git_credential_token,
    formData.git_credential_ssh_private_key,
    formData.git_credential_ssh_known_hosts,
  ]);

  useEffect(() => {
    const trimmed = formData.git_repo.trim();
    if (!trimmed) {
      setGitBranches([]);
      setBranchError(null);
      return;
    }

    const timer = setTimeout(() => {
      loadBranches(trimmed);
    }, 500);

    return () => clearTimeout(timer);
  }, [
    formData.git_repo,
    formData.git_credential_type,
    formData.git_credential_username,
    formData.git_credential_token,
    formData.git_credential_ssh_private_key,
    formData.git_credential_ssh_known_hosts,
    loadBranches,
  ]);

  useEffect(() => {
    if (typeof window === 'undefined' || hasLoadedDraft) return;
    const raw = window.localStorage.getItem(PROJECT_FORM_DRAFT_KEY);
    if (!raw) {
      setHasLoadedDraft(true);
      return;
    }

    try {
      const draft = JSON.parse(raw);
      const shouldRestore = window.confirm('检测到未完成的项目草稿，是否恢复？\n\n注意：Access Token 和 SSH 私钥不会被恢复，需要重新输入。');
      if (shouldRestore) {
        setFormData((prev) => ({
          ...prev,
          ...draft,
          git_credential_token: '',
          git_credential_ssh_private_key: '',
        }));
      }
    } catch {
      window.localStorage.removeItem(PROJECT_FORM_DRAFT_KEY);
    } finally {
      setHasLoadedDraft(true);
    }
  }, [hasLoadedDraft]);

  useEffect(() => {
    const timer = setTimeout(() => {
      loadComposeServices();
    }, 500);
    return () => clearTimeout(timer);
  }, [loadComposeServices]);

  useEffect(() => {
    if (typeof window === 'undefined' || !hasLoadedDraft) return;

    const { git_credential_token, git_credential_ssh_private_key, ...safeDraft } = formData;
    const isEmpty = isFormEmpty(safeDraft as FormData);

    if (isEmpty) {
      window.localStorage.removeItem(PROJECT_FORM_DRAFT_KEY);
      return;
    }

    window.localStorage.setItem(PROJECT_FORM_DRAFT_KEY, JSON.stringify(safeDraft));
  }, [formData, hasLoadedDraft]);

  const clearDraft = () => {
    if (typeof window !== 'undefined') {
      window.localStorage.removeItem(PROJECT_FORM_DRAFT_KEY);
    }
  };

  const isDirty = (): boolean => {
    return !isFormEmpty(formData);
  };

  const handleClose = () => {
    if (isDirty()) {
      const confirmed = window.confirm('当前表单有未保存内容，关闭后将保留草稿但敏感凭据不会保存。确定关闭吗？');
      if (!confirmed) return;
    }
    onClose();
  };

  const draftActive = hasLoadedDraft && isDirty();

  const updateField = <K extends keyof FormData>(
    field: K,
    value: FormData[K]
  ) => {
    const newData = { ...formData, [field]: value };

    if (field === 'name') {
      const name = String(value).toLowerCase().replace(/[^a-z0-9._-]/g, '-');
      if (name && !formData.deploy_workdir) {
        newData.deploy_workdir = generateWorkdir(name);
      }
      if (name && !formData.flags_file_path) {
        newData.flags_file_path = generateFlagsPath(name);
      }
    }

    setFormData(newData);
  };

  const canSubmit = (): boolean => {
    return (
      !!formData.name &&
      !!formData.git_repo &&
      !!formData.deploy_workdir &&
      !!formData.compose_file &&
      !!formData.compose_service &&
      !!formData.flags_file_path
    );
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setSaving(true);
      const project = await api.createProject({
        name: formData.name,
        environment: formData.environment || undefined,
        git_repo: formData.git_repo,
        git_branch: formData.git_branch || 'main',
        git_credential_type: formData.git_credential_type,
        git_credential_username: formData.git_credential_username || null,
        git_credential_token: formData.git_credential_token || null,
        git_credential_ssh_private_key: formData.git_credential_ssh_private_key || null,
        git_credential_ssh_known_hosts: formData.git_credential_ssh_known_hosts || null,
        deploy_workdir: formData.deploy_workdir,
        flags_file_path: formData.flags_file_path,
        healthcheck_url: formData.healthcheck_url || null,
        healthcheck_expected_status: formData.healthcheck_expected_status,
        deploy_strategy: formData.deploy_strategy,
        compose_file: formData.compose_file,
        compose_service: formData.compose_service,
        healthcheck_timeout_seconds: formData.healthcheck_timeout_seconds,
        migration_service: formData.migration_service.trim() || undefined,
        migration_command: formData.migration_command.trim() || undefined,
        migration_timeout_seconds: formData.migration_timeout_seconds,
        migration_no_deps: formData.migration_no_deps,
        compose_profiles: formData.compose_profiles
          .split(',')
          .map((item) => item.trim())
          .filter(Boolean),
        build_timeout_seconds: formData.build_timeout_seconds,
        pull_timeout_seconds: formData.pull_timeout_seconds,
        build_no_cache: formData.build_no_cache,
        service_scope: formData.service_scope,
      });
      clearDraft();
      onSuccess(project);
    } catch (err: any) {
      onError(err.message || '创建项目失败');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-3xl max-h-[90vh] flex flex-col">
        <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900">创建新项目（高级表单）</h2>
          <button
            type="button"
            onClick={handleClose}
            className="text-gray-400 hover:text-gray-600"
          >
            <X className="w-6 h-6" />
          </button>
        </div>

        <form
          onSubmit={handleSubmit}
          className="flex-1 overflow-y-auto p-6 space-y-6"
        >
          <div className="border-t border-gray-200 pt-4 first:border-t-0 first:pt-0">
            <h3 className="text-sm font-medium text-gray-900 mb-3 flex items-center gap-2">
              <FolderGit2 className="w-4 h-4 text-gray-500" />
              基本信息
            </h3>
            <div className="space-y-4">
              <div>
                <label className="label flex items-center justify-between">
                  <span>Project Name <span className="text-red-500">*</span></span>
                  <span className="text-xs text-gray-400 font-normal">项目标识名称</span>
                </label>
                <input
                  type="text"
                  className="input"
                  value={formData.name}
                  onChange={(e) => updateField('name', e.target.value)}
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
                    onClick={() => updateField('environment', null)}
                    className={`px-3 py-2 text-sm rounded-md border transition-colors ${
                      !formData.environment
                        ? 'bg-primary-50 border-primary-300 text-primary-700'
                        : 'bg-white border-gray-200 text-gray-600 hover:bg-gray-50'
                    }`}
                  >
                    不指定
                  </button>
                  {ENVIRONMENT_OPTIONS.map((opt) => (
                    <button
                      key={opt.value}
                      type="button"
                      onClick={() => updateField('environment', opt.value)}
                      className={`px-3 py-2 text-sm rounded-md border transition-colors ${
                        formData.environment === opt.value
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

              <div className="grid grid-cols-1 gap-4">
                <div>
                  <label className="label flex items-center justify-between">
                    <span>Git Credentials</span>
                    <span className="text-xs text-gray-400 font-normal">私有仓库访问方式</span>
                  </label>
                  <select
                    className="input"
                    value={formData.git_credential_type}
                    onChange={(e) => updateField('git_credential_type', e.target.value as GitCredentialType)}
                  >
                    <option value="none">No credentials</option>
                    <option value="http_token">HTTP token</option>
                    <option value="ssh_key">SSH private key</option>
                  </select>
                </div>

                {formData.git_credential_type === 'http_token' ? (
                  <div className="grid grid-cols-1 gap-4">
                    <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-3 text-xs text-amber-900">
                      <p className="font-medium">HTTP Token 说明</p>
                      <p className="mt-1">`Git Username` 通常填代码托管平台用户名，`Access Token` 填平台生成的 Personal Access Token。</p>
                      <p className="mt-1">GitHub: Settings → Developer settings → Personal access tokens。</p>
                      <p className="mt-1">GitLab: User Settings → Access Tokens。Gitee: 设置 → 私人令牌。</p>
                      <p className="mt-1">常见可用用户名：GitHub 用你的用户名或 `x-access-token`，GitLab/Gitee 通常用你的账号名。长期部署更推荐 `SSH private key`。</p>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div>
                        <label className="label">Git Username</label>
                        <input
                          type="text"
                          className="input"
                          value={formData.git_credential_username}
                          onChange={(e) => updateField('git_credential_username', e.target.value)}
                          placeholder="GitHub 用户名 / x-access-token / GitLab 用户名"
                        />
                        <p className="text-xs text-gray-400 mt-1">
                          例：GitHub 可填你的用户名，也可尝试 `x-access-token`
                        </p>
                      </div>
                      <div>
                        <label className="label">Access Token</label>
                        <input
                          type="password"
                          className="input"
                          value={formData.git_credential_token}
                          onChange={(e) => updateField('git_credential_token', e.target.value)}
                          placeholder="平台生成的 PAT / Access Token"
                        />
                        <p className="text-xs text-gray-400 mt-1">
                          需要具备读取仓库分支和拉取代码权限
                        </p>
                      </div>
                    </div>
                  </div>
                ) : null}

                {formData.git_credential_type === 'ssh_key' ? (
                  <div className="grid grid-cols-1 gap-4">
                    <div>
                      <label className="label">SSH Private Key</label>
                      <textarea
                        className="input min-h-[160px]"
                        value={formData.git_credential_ssh_private_key}
                        onChange={(e) => updateField('git_credential_ssh_private_key', e.target.value)}
                        placeholder="-----BEGIN OPENSSH PRIVATE KEY-----"
                      />
                      <p className="text-xs text-gray-400 mt-1">
                        推荐使用只读 Deploy Key，或专门用于 CI/部署的 SSH 私钥
                      </p>
                    </div>
                    <div>
                      <label className="label">Known Hosts</label>
                      <textarea
                        className="input min-h-[96px]"
                        value={formData.git_credential_ssh_known_hosts}
                        onChange={(e) => updateField('git_credential_ssh_known_hosts', e.target.value)}
                        placeholder="github.com ssh-ed25519 AAAA..."
                      />
                      <p className="text-xs text-gray-400 mt-1">
                        留空时 Agent 会使用 `accept-new`
                      </p>
                    </div>
                  </div>
                ) : null}
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
                  <span>Git Repository <span className="text-red-500">*</span></span>
                  <span className="text-xs text-gray-400 font-normal">代码仓库</span>
                </label>
                <input
                  type="text"
                  className="input"
                  value={formData.git_repo}
                  onChange={(e) => updateField('git_repo', e.target.value)}
                  placeholder="git@github.com:user/repo.git"
                />
                <p className="text-xs text-gray-400 mt-1">
                  支持 SSH 或 HTTPS 协议
                </p>
              </div>
              <div>
                <label className="label flex items-center justify-between">
                  <span>Branch</span>
                  <span className="text-xs text-gray-400 font-normal">部署分支</span>
                </label>
                <div className="relative">
                  {gitBranches.length > 0 ? (
                    <select
                      className="input pr-10"
                      value={formData.git_branch}
                      onChange={(e) => updateField('git_branch', e.target.value)}
                    >
                      {gitBranches.map((branch) => (
                        <option key={branch.name} value={branch.name}>
                          {branch.name}
                          {branch.is_default ? ' (default)' : ''}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <input
                      type="text"
                      className="input pr-10"
                      value={formData.git_branch}
                      onChange={(e) => updateField('git_branch', e.target.value)}
                      placeholder="main"
                    />
                  )}
                  <div className="absolute right-3 top-1/2 -translate-y-1/2">
                    {loadingBranches ? (
                      <Loader2 className="w-4 h-4 text-gray-400 animate-spin" />
                    ) : formData.git_repo.trim() && gitBranches.length === 0 && !branchError ? (
                      <Loader2 className="w-4 h-4 text-gray-400 animate-spin" />
                    ) : null}
                  </div>
                </div>
                <p className="text-xs text-gray-400 mt-1">
                  {branchError ? (
                    <span className="text-red-500">{branchError} - 请手动输入</span>
                  ) : gitBranches.length > 0 ? (
                    <>已自动读取 <b>{gitBranches.length}</b> 个分支</>
                  ) : (
                    '默认从该分支拉取最新代码'
                  )}
                </p>
              </div>
            </div>
          </div>

          <div className="border-t border-gray-200 pt-4">
            <h3 className="text-sm font-medium text-gray-900 mb-3 flex items-center gap-2">
              <Server className="w-4 h-4 text-gray-500" />
              部署配置
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="label flex items-center justify-between">
                  <span>Deploy Workdir <span className="text-red-500">*</span></span>
                  <span className="text-xs text-gray-400 font-normal">工作目录</span>
                </label>
                <input
                  type="text"
                  className="input"
                  value={formData.deploy_workdir}
                  onChange={(e) => updateField('deploy_workdir', e.target.value)}
                  placeholder="/opt/my-saas-app"
                />
                <p className="text-xs text-gray-400 mt-1">
                  Agent 执行部署的目录，必须是绝对路径
                </p>
              </div>
              <div>
                <label className="label flex items-center justify-between">
                  <span>Compose File <span className="text-red-500">*</span></span>
                  <span className="text-xs text-gray-400 font-normal">Compose 文件</span>
                </label>
                <input
                  type="text"
                  className="input"
                  value={formData.compose_file}
                  onChange={(e) => updateField('compose_file', e.target.value)}
                  placeholder="docker-compose.yml"
                />
                <p className="text-xs text-gray-400 mt-1">
                  相对于工作目录的 docker-compose.yml 路径
                </p>
              </div>
              <div>
                <label className="label flex items-center justify-between">
                  <span>Compose Service <span className="text-red-500">*</span></span>
                  <span className="text-xs text-gray-400 font-normal">主服务名</span>
                </label>
                {composeServices.length > 0 ? (
                  <select
                    className="input"
                    value={formData.compose_service}
                    onChange={(e) => updateField('compose_service', e.target.value)}
                  >
                    {composeServices.map((service) => (
                      <option key={service.name} value={service.name}>
                        {service.name}
                        {service.is_default ? ' (default)' : ''}
                      </option>
                    ))}
                  </select>
                ) : (
                  <input
                    type="text"
                    className="input"
                    value={formData.compose_service}
                    onChange={(e) => updateField('compose_service', e.target.value)}
                    placeholder="app"
                  />
                )}
                <p className="text-xs text-gray-400 mt-1">
                  {loadingComposeServices
                    ? '正在从仓库探测 compose 服务...'
                    : composeServices.length > 0
                      ? `已自动识别 ${composeServices.length} 个服务`
                      : 'docker-compose.yml 中定义的主要应用服务'}
                </p>
                {composeServiceError ? (
                  <p className="text-xs text-red-500 mt-1">{composeServiceError} - 可手动输入</p>
                ) : null}
              </div>
              <div>
                <label className="label flex items-center justify-between">
                  <span>Deploy Strategy</span>
                  <span className="text-xs text-gray-400 font-normal">部署策略</span>
                </label>
                <select
                  className="input"
                  value={formData.deploy_strategy}
                  onChange={(e) => updateField('deploy_strategy', e.target.value)}
                >
                  <option value="compose-build">compose-build (构建镜像)</option>
                  <option value="compose-pull">compose-pull (拉取镜像)</option>
                </select>
                <p className="text-xs text-gray-400 mt-1">
                  compose-build: 在服务器上构建 | compose-pull: 直接拉取镜像
                </p>
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
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
                  value={formData.build_timeout_seconds}
                  onChange={(e) => updateField('build_timeout_seconds', parseInt(e.target.value) || 1800)}
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
                  value={formData.pull_timeout_seconds}
                  onChange={(e) => updateField('pull_timeout_seconds', parseInt(e.target.value) || 900)}
                />
                <p className="text-xs text-gray-400 mt-1">
                  镜像拉取超时，默认 900 秒
                </p>
              </div>
              <div className="md:col-span-2">
                <label className="label flex items-center justify-between">
                  <span>Service Scope</span>
                  <span className="text-xs text-gray-400 font-normal">操作范围</span>
                </label>
                <select
                  className="input"
                  value={formData.service_scope}
                  onChange={(e) => updateField('service_scope', e.target.value)}
                >
                  <option value="app">app（只作用于应用服务，不影响数据库）</option>
                  <option value="all">all（整份 Compose，含数据库等基础设施）</option>
                </select>
                <p className="text-xs text-gray-400 mt-1">
                  Stop/Start 默认只操作应用服务；数据库等基础设施请选 all（谨慎）
                </p>
              </div>
              <div className="md:col-span-2 flex items-center gap-2">
                <input
                  type="checkbox"
                  id="build-no-cache"
                  className="h-4 w-4 rounded border-gray-300 text-primary-600"
                  checked={formData.build_no_cache}
                  onChange={(e) => updateField('build_no_cache', e.target.checked)}
                />
                <label htmlFor="build-no-cache" className="text-sm text-gray-700">
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
                  value={formData.healthcheck_url}
                  onChange={(e) => updateField('healthcheck_url', e.target.value)}
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
                  value={formData.healthcheck_timeout_seconds}
                  onChange={(e) => updateField('healthcheck_timeout_seconds', parseInt(e.target.value) || 10)}
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
                  value={formData.healthcheck_expected_status}
                  onChange={(e) => updateField('healthcheck_expected_status', parseInt(e.target.value) || 200)}
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
                    value={formData.migration_service}
                    onChange={(e) => updateField('migration_service', e.target.value)}
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
                    value={formData.migration_timeout_seconds}
                    onChange={(e) => updateField('migration_timeout_seconds', parseInt(e.target.value) || 600)}
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
                  value={formData.migration_command}
                  onChange={(e) => updateField('migration_command', e.target.value)}
                  placeholder="alembic upgrade head"
                />
                <p className="text-xs text-gray-400 mt-1">
                  在构建后、启动前执行；按 argv 拆分，不走 shell。留空则不执行迁移
                </p>
              </div>
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="migration-no-deps"
                  className="h-4 w-4 rounded border-gray-300 text-primary-600"
                  checked={formData.migration_no_deps}
                  onChange={(e) => updateField('migration_no_deps', e.target.checked)}
                />
                <label htmlFor="migration-no-deps" className="text-sm text-gray-700">
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
                  value={formData.compose_profiles}
                  onChange={(e) => updateField('compose_profiles', e.target.value)}
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
                <span>Flags File Path <span className="text-red-500">*</span></span>
                <span className="text-xs text-gray-400 font-normal">开关文件</span>
              </label>
              <input
                type="text"
                className="input"
                value={formData.flags_file_path}
                onChange={(e) => updateField('flags_file_path', e.target.value)}
                placeholder="/var/lib/shipsmith/my-saas-app/flags.json"
              />
              <p className="text-xs text-gray-400 mt-1">
                功能开关 JSON 文件路径，应用可读取此文件控制功能开关
              </p>
            </div>
          </div>
        </form>

        {draftActive ? (
          <div className="px-6 pb-3">
            <div className="rounded-md border border-blue-200 bg-blue-50 px-3 py-2 text-xs text-blue-800">
              草稿已自动保存。重新打开可恢复；Access Token 和 SSH 私钥不会被保存。
            </div>
          </div>
        ) : null}

        <div className="px-6 py-4 border-t border-gray-200 flex justify-end gap-3">
          <button
            type="button"
            onClick={handleClose}
            className="btn btn-secondary"
          >
            取消
          </button>
          <button
            type="submit"
            onClick={handleSubmit}
            disabled={saving || !canSubmit()}
            className="btn btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {saving ? '创建中...' : '创建项目'}
          </button>
        </div>
      </div>
    </div>
  );
}
