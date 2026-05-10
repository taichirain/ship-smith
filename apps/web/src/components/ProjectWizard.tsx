'use client';

import { useState, useMemo, useEffect, useCallback } from 'react';
import {
  ChevronLeft,
  ChevronRight,
  CheckCircle2,
  FolderGit2,
  Server,
  FileCode,
  Activity,
  Copy,
  Download,
  Info,
  X,
  Loader2,
} from 'lucide-react';
import { api, Project, EnvironmentType, GitBranchInfo, GitCredentialType, ComposeServiceInfo } from '@/lib/api';

const STEPS = [
  {
    id: 'basic',
    title: '基本信息',
    icon: FolderGit2,
    description: '设置项目的基本标识信息和环境',
  },
  {
    id: 'deploy',
    title: '部署配置',
    icon: Server,
    description: '配置服务器部署环境',
  },
  {
    id: 'compose',
    title: 'Compose 配置',
    icon: FileCode,
    description: '指定 Docker Compose 文件和服务',
  },
  {
    id: 'health',
    title: '健康检查',
    icon: Activity,
    description: '设置应用健康检查（可选）',
  },
  {
    id: 'preview',
    title: '配置预览',
    icon: CheckCircle2,
    description: '确认配置并创建项目',
  },
];

const ENVIRONMENT_OPTIONS: { value: EnvironmentType; label: string; color: string }[] = [
  { value: 'production', label: '生产环境', color: 'bg-red-100 text-red-800 border-red-200' },
  { value: 'staging', label: '预发环境', color: 'bg-orange-100 text-orange-800 border-orange-200' },
  { value: 'development', label: '开发环境', color: 'bg-green-100 text-green-800 border-green-200' },
  { value: 'testing', label: '测试环境', color: 'bg-blue-100 text-blue-800 border-blue-200' },
  { value: 'other', label: '其他', color: 'bg-gray-100 text-gray-800 border-gray-200' },
];

const PROJECT_WIZARD_DRAFT_KEY = 'shipsmith_project_wizard_draft_v1';

interface WizardFormData {
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
  flags_file_path: string;
  compose_file: string;
  compose_service: string;
  healthcheck_url: string;
  healthcheck_timeout_seconds: number;
}

interface ProjectWizardProps {
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

export default function ProjectWizard({ onClose, onSuccess, onError }: ProjectWizardProps) {
  const [currentStep, setCurrentStep] = useState(0);
  const [saving, setSaving] = useState(false);
  const [copied, setCopied] = useState(false);
  const [formData, setFormData] = useState<WizardFormData>({
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
    flags_file_path: '',
    compose_file: 'docker-compose.yml',
    compose_service: 'app',
    healthcheck_url: '',
    healthcheck_timeout_seconds: 10,
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
    const raw = window.localStorage.getItem(PROJECT_WIZARD_DRAFT_KEY);
    if (!raw) {
      setHasLoadedDraft(true);
      return;
    }

    try {
      const draft = JSON.parse(raw);
      const shouldRestore = window.confirm('检测到未完成的项目草稿，是否恢复？\n\n注意：Access Token 和 SSH 私钥不会被恢复，需要重新输入。');
      if (shouldRestore) {
        if (typeof draft.currentStep === 'number') {
          setCurrentStep(Math.max(0, Math.min(STEPS.length - 1, draft.currentStep)));
        }
        setFormData((prev) => ({
          ...prev,
          ...draft.formData,
          git_credential_token: '',
          git_credential_ssh_private_key: '',
        }));
      }
    } catch {
      window.localStorage.removeItem(PROJECT_WIZARD_DRAFT_KEY);
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

    const { git_credential_token, git_credential_ssh_private_key, ...safeFormData } = formData;
    const isEmpty = !Object.values(safeFormData).some((value) => {
      if (typeof value === 'string') return value.trim() !== '' && value !== 'main' && value !== 'docker-compose.yml' && value !== 'app';
      if (typeof value === 'number') return value !== 10;
      return value !== null && value !== undefined;
    });

    if (isEmpty && currentStep === 0) {
      window.localStorage.removeItem(PROJECT_WIZARD_DRAFT_KEY);
      return;
    }

    window.localStorage.setItem(PROJECT_WIZARD_DRAFT_KEY, JSON.stringify({
      currentStep,
      formData: safeFormData,
    }));
  }, [formData, currentStep, hasLoadedDraft]);

  const clearDraft = () => {
    if (typeof window !== 'undefined') {
      window.localStorage.removeItem(PROJECT_WIZARD_DRAFT_KEY);
    }
  };

  const isDirty = (): boolean => {
    return Object.entries(formData).some(([key, value]) => {
      if (key === 'environment') return value !== null;
      if (typeof value === 'number') return value !== 10;
      if (typeof value === 'string') {
        const trimmed = value.trim();
        if (key === 'git_branch') return trimmed !== '' && trimmed !== 'main';
        if (key === 'compose_file') return trimmed !== '' && trimmed !== 'docker-compose.yml';
        if (key === 'compose_service') return trimmed !== '' && trimmed !== 'app';
        return trimmed !== '';
      }
      return false;
    }) || currentStep > 0;
  };

  const handleClose = () => {
    if (isDirty()) {
      const confirmed = window.confirm('当前向导有未保存内容，关闭后将保留草稿但敏感凭据不会保存。确定关闭吗？');
      if (!confirmed) return;
    }
    onClose();
  };

  const draftActive = hasLoadedDraft && isDirty();

  const updateField = <K extends keyof WizardFormData>(
    field: K,
    value: WizardFormData[K]
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

  const shipsmithYaml = useMemo(() => {
    return `project: ${formData.name}
git:
  repo: ${formData.git_repo || '<git_repo>'}
  branch: ${formData.git_branch || 'main'}
deploy:
  workdir: ${formData.deploy_workdir || '<deploy_workdir>'}
  strategy: compose-build
compose:
  file: ${formData.compose_file || 'docker-compose.yml'}
  service: ${formData.compose_service || 'app'}
flags:
  file: ${formData.flags_file_path || '<flags_file_path>'}
${formData.healthcheck_url ? `health_check:
  type: http
  url: ${formData.healthcheck_url}
  timeout_seconds: ${formData.healthcheck_timeout_seconds}` : ''}`;
  }, [formData]);

  const canProceed = (): boolean => {
    switch (currentStep) {
      case 0:
        return !!formData.name && !!formData.git_repo;
      case 1:
        return !!formData.deploy_workdir && !!formData.flags_file_path;
      case 2:
        return !!formData.compose_file && !!formData.compose_service;
      case 3:
        return true;
      case 4:
        return true;
      default:
        return false;
    }
  };

  const goNext = () => {
    if (currentStep < STEPS.length - 1) {
      setCurrentStep(currentStep + 1);
    }
  };

  const goPrev = () => {
    if (currentStep > 0) {
      setCurrentStep(currentStep - 1);
    }
  };

  const handleCopyYaml = async () => {
    try {
      await navigator.clipboard.writeText(shipsmithYaml);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  const handleDownloadYaml = () => {
    const blob = new Blob([shipsmithYaml], { type: 'text/yaml' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'shipsmith.yaml';
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleCreateProject = async () => {
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
        deploy_strategy: 'compose-build',
        compose_file: formData.compose_file,
        compose_service: formData.compose_service,
        healthcheck_timeout_seconds: formData.healthcheck_timeout_seconds,
      });
      clearDraft();
      onSuccess(project);
    } catch (err: any) {
      onError(err.message || '创建项目失败');
    } finally {
      setSaving(false);
    }
  };

  const renderStepContent = () => {
    switch (currentStep) {
      case 0:
        return (
          <div className="space-y-6">
            <div>
              <label className="label">
                项目名称
                <span className="text-red-500 ml-1">*</span>
              </label>
              <input
                type="text"
                className="input"
                value={formData.name}
                onChange={(e) => updateField('name', e.target.value)}
                placeholder="my-saas-app"
              />
              <p className="text-xs text-gray-500 mt-1">
                用于标识项目，仅支持字母、数字、点、横杠和下划线
              </p>
            </div>

            <div>
              <label className="label">环境</label>
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
              <p className="text-xs text-gray-500 mt-1">
                用于在项目列表中过滤和区分不同环境的项目
              </p>
            </div>

            <div>
              <label className="label">
                Git 仓库地址
                <span className="text-red-500 ml-1">*</span>
              </label>
              <input
                type="text"
                className="input"
                value={formData.git_repo}
                onChange={(e) => updateField('git_repo', e.target.value)}
                placeholder="git@github.com:user/repo.git 或 https://github.com/user/repo.git"
              />
              <p className="text-xs text-gray-500 mt-1">
                支持 SSH 或 HTTPS 协议
              </p>
            </div>

            <div className="space-y-4">
              <div>
                <label className="label">Git 凭据</label>
                <select
                  className="input"
                  value={formData.git_credential_type}
                  onChange={(e) => updateField('git_credential_type', e.target.value as GitCredentialType)}
                >
                  <option value="none">不使用凭据</option>
                  <option value="http_token">HTTP Token</option>
                  <option value="ssh_key">SSH 私钥</option>
                </select>
                <p className="text-xs text-gray-500 mt-1">
                  私有仓库需要配置访问凭据，分支探测和 Agent 部署会共用这套配置
                </p>
              </div>

              {formData.git_credential_type === 'http_token' ? (
                <div className="grid grid-cols-1 gap-4">
                  <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-3 text-xs text-amber-900">
                    <p className="font-medium">HTTP Token 说明</p>
                    <p className="mt-1">`Git 用户名` 一般填代码托管平台用户名，`Access Token` 填平台生成的个人访问令牌。</p>
                    <p className="mt-1">GitHub: Settings → Developer settings → Personal access tokens。</p>
                    <p className="mt-1">GitLab: User Settings → Access Tokens。Gitee: 设置 → 私人令牌。</p>
                    <p className="mt-1">如果是长期部署，优先考虑改用 `SSH 私钥`。</p>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label className="label">Git 用户名</label>
                      <input
                        type="text"
                        className="input"
                        value={formData.git_credential_username}
                        onChange={(e) => updateField('git_credential_username', e.target.value)}
                        placeholder="GitHub 用户名 / x-access-token / GitLab 用户名"
                      />
                      <p className="text-xs text-gray-500 mt-1">
                        GitHub 常见填法：你的用户名，或 `x-access-token`
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
                      <p className="text-xs text-gray-500 mt-1">
                        至少需要仓库读取权限
                      </p>
                    </div>
                  </div>
                </div>
              ) : null}

              {formData.git_credential_type === 'ssh_key' ? (
                <div className="grid grid-cols-1 gap-4">
                  <div>
                    <label className="label">SSH 私钥</label>
                    <textarea
                      className="input min-h-[160px]"
                      value={formData.git_credential_ssh_private_key}
                      onChange={(e) => updateField('git_credential_ssh_private_key', e.target.value)}
                      placeholder="-----BEGIN OPENSSH PRIVATE KEY-----"
                    />
                    <p className="text-xs text-gray-500 mt-1">
                      推荐使用只读 Deploy Key，或专门用于部署的 SSH 私钥
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
                    <p className="text-xs text-gray-500 mt-1">
                      留空时首次连接会采用 `accept-new`
                    </p>
                  </div>
                </div>
              ) : null}
            </div>

            <div>
              <label className="label">Git 分支</label>
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
              <p className="text-xs text-gray-500 mt-1">
                {branchError ? (
                  <span className="text-red-500">{branchError} - 请手动输入</span>
                ) : gitBranches.length > 0 ? (
                  <>已自动读取 <b>{gitBranches.length}</b> 个分支</>
                ) : (
                  '默认部署分支，通常为 main 或 master'
                )}
              </p>
            </div>
          </div>
        );

      case 1:
        return (
          <div className="space-y-6">
            <div>
              <label className="label">
                部署工作目录
                <span className="text-red-500 ml-1">*</span>
              </label>
              <input
                type="text"
                className="input"
                value={formData.deploy_workdir}
                onChange={(e) => updateField('deploy_workdir', e.target.value)}
                placeholder="/opt/my-saas-app"
              />
              <p className="text-xs text-gray-500 mt-1">
                Agent 在服务器上执行部署命令的目录，必须是绝对路径
              </p>
            </div>

            <div>
              <label className="label">
                Feature Flags 文件路径
                <span className="text-red-500 ml-1">*</span>
              </label>
              <input
                type="text"
                className="input"
                value={formData.flags_file_path}
                onChange={(e) => updateField('flags_file_path', e.target.value)}
                placeholder="/var/lib/shipsmith/my-saas-app/flags.json"
              />
              <p className="text-xs text-gray-500 mt-1">
                功能开关 JSON 文件的路径，应用可以读取此文件来控制功能开关
              </p>
            </div>

            <div className="bg-blue-50 border border-blue-200 rounded-md p-4">
              <div className="flex items-start gap-2">
                <Info className="w-5 h-5 text-blue-500 flex-shrink-0 mt-0.5" />
                <div className="text-sm text-blue-800">
                  <p className="font-medium mb-1">关于部署目录</p>
                  <p className="text-blue-700">
                    部署目录需要确保 Agent 进程有读写权限。建议使用
                    <code className="bg-blue-100 px-1 rounded mx-1">/opt/{formData.name || 'your-app'}</code>
                    这样的标准路径。
                  </p>
                </div>
              </div>
            </div>
          </div>
        );

      case 2:
        return (
          <div className="space-y-6">
            <div>
              <label className="label">
                Compose 文件路径
                <span className="text-red-500 ml-1">*</span>
              </label>
              <input
                type="text"
                className="input"
                value={formData.compose_file}
                onChange={(e) => updateField('compose_file', e.target.value)}
                placeholder="docker-compose.yml"
              />
              <p className="text-xs text-gray-500 mt-1">
                相对于部署工作目录的 Docker Compose 文件路径
              </p>
            </div>

            <div>
              <label className="label">
                主服务名称
                <span className="text-red-500 ml-1">*</span>
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
              <p className="text-xs text-gray-500 mt-1">
                {loadingComposeServices
                  ? '正在从仓库探测 compose 服务...'
                  : composeServices.length > 0
                    ? `已自动识别 ${composeServices.length} 个服务`
                    : 'docker-compose.yml 中定义的主要应用服务名称，用于健康检查判定'}
              </p>
              {composeServiceError ? (
                <p className="text-xs text-red-500 mt-1">{composeServiceError} - 可手动输入</p>
              ) : null}
            </div>

            <div className="bg-gray-50 border border-gray-200 rounded-md p-4">
              <div className="flex items-start gap-2">
                <Info className="w-5 h-5 text-gray-500 flex-shrink-0 mt-0.5" />
                <div className="text-sm text-gray-700">
                  <p className="font-medium mb-1">示例 docker-compose.yml</p>
                  <pre className="bg-gray-100 p-3 rounded text-xs font-mono mt-2 overflow-x-auto">
{`services:
  app:
    build: .
    ports:
      - "3000:3000"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3000/api/health"]
      interval: 30s
      timeout: 10s`}
                  </pre>
                  <p className="mt-2 text-gray-600">
                    在此示例中，主服务名称是 <code className="bg-gray-200 px-1 rounded">app</code>
                  </p>
                </div>
              </div>
            </div>
          </div>
        );

      case 3:
        return (
          <div className="space-y-6">
            <div>
              <label className="label">健康检查 URL（可选）</label>
              <input
                type="text"
                className="input"
                value={formData.healthcheck_url}
                onChange={(e) => updateField('healthcheck_url', e.target.value)}
                placeholder="http://127.0.0.1:3000/api/health"
              />
              <p className="text-xs text-gray-500 mt-1">
                Agent 用来检测应用是否正常运行的 HTTP 端点
              </p>
            </div>

            <div>
              <label className="label">健康检查超时时间（秒）</label>
              <input
                type="number"
                className="input"
                min="1"
                max="300"
                value={formData.healthcheck_timeout_seconds}
                onChange={(e) => updateField('healthcheck_timeout_seconds', parseInt(e.target.value) || 10)}
              />
              <p className="text-xs text-gray-500 mt-1">
                默认 10 秒，建议根据应用启动时间调整
              </p>
            </div>

            <div className="bg-yellow-50 border border-yellow-200 rounded-md p-4">
              <div className="flex items-start gap-2">
                <Info className="w-5 h-5 text-yellow-600 flex-shrink-0 mt-0.5" />
                <div className="text-sm text-yellow-800">
                  <p className="font-medium mb-1">为什么需要健康检查？</p>
                  <p className="text-yellow-700">
                    健康检查可以帮助 ShipSmith 判断部署是否真正成功。
                    如果没有健康检查，即使容器启动了，也无法确认应用是否正常工作。
                  </p>
                  <ul className="mt-2 text-yellow-700 list-disc list-inside space-y-1">
                    <li>部署成功后会等待健康检查通过</li>
                    <li>健康检查失败时会标记部署失败</li>
                    <li>可以在 Dashboard 查看健康状态趋势</li>
                  </ul>
                </div>
              </div>
            </div>
          </div>
        );

      case 4:
        return (
          <div className="space-y-6">
            <div>
              <div className="flex items-center justify-between mb-2">
                <h4 className="font-medium text-gray-900">配置预览 (shipsmith.yaml)</h4>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={handleCopyYaml}
                    className="btn btn-secondary text-xs py-1 px-2"
                  >
                    <Copy className="w-3 h-3 mr-1" />
                    {copied ? '已复制' : '复制'}
                  </button>
                  <button
                    type="button"
                    onClick={handleDownloadYaml}
                    className="btn btn-secondary text-xs py-1 px-2"
                  >
                    <Download className="w-3 h-3 mr-1" />
                    下载
                  </button>
                </div>
              </div>
              <pre className="bg-gray-900 text-gray-100 p-4 rounded-lg text-sm font-mono overflow-x-auto">
                {shipsmithYaml}
              </pre>
            </div>

            <div className="bg-green-50 border border-green-200 rounded-md p-4">
              <div className="flex items-start gap-2">
                <CheckCircle2 className="w-5 h-5 text-green-600 flex-shrink-0 mt-0.5" />
                <div className="text-sm text-green-800">
                  <p className="font-medium mb-1">准备就绪</p>
                  <p className="text-green-700">
                    点击下方按钮创建项目。创建成功后，您需要在目标服务器上安装并配置 Agent。
                  </p>
                </div>
              </div>
            </div>

            <div className="border-t border-gray-200 pt-4">
              <h4 className="font-medium text-gray-900 mb-3">配置摘要</h4>
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-gray-500">项目名称：</span>
                  <span className="text-gray-900 font-medium">{formData.name}</span>
                </div>
                <div>
                  <span className="text-gray-500">Git 分支：</span>
                  <span className="text-gray-900 font-medium">{formData.git_branch}</span>
                </div>
                <div>
                  <span className="text-gray-500">部署目录：</span>
                  <span className="text-gray-900 font-medium">{formData.deploy_workdir}</span>
                </div>
                <div>
                  <span className="text-gray-500">服务名称：</span>
                  <span className="text-gray-900 font-medium">{formData.compose_service}</span>
                </div>
                <div>
                  <span className="text-gray-500">健康检查：</span>
                  <span className="text-gray-900 font-medium">
                    {formData.healthcheck_url || '未配置'}
                  </span>
                </div>
              </div>
            </div>
          </div>
        );

      default:
        return null;
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-3xl max-h-[90vh] flex flex-col">
        <div className="px-6 py-4 border-b border-gray-200">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-gray-900">创建新项目</h2>
            <button
              type="button"
              onClick={handleClose}
              className="text-gray-400 hover:text-gray-600"
            >
              <X className="w-6 h-6" />
            </button>
          </div>
        </div>

        <div className="px-6 py-4 border-b border-gray-200">
          <div className="flex items-center gap-2 overflow-x-auto">
            {STEPS.map((step, index) => {
              const StepIcon = step.icon;
              const isActive = index === currentStep;
              const isPast = index < currentStep;
              const isLast = index === STEPS.length - 1;

              return (
                <div key={step.id} className="flex items-center">
                  <button
                    type="button"
                    onClick={() => index < currentStep && setCurrentStep(index)}
                    className={`flex items-center gap-2 px-3 py-2 rounded-md transition-colors ${
                      isActive
                        ? 'bg-primary-100 text-primary-700'
                        : isPast
                        ? 'text-gray-600 hover:bg-gray-100 cursor-pointer'
                        : 'text-gray-400 cursor-not-allowed'
                    }`}
                    disabled={index > currentStep}
                  >
                    {isPast && !isLast ? (
                      <CheckCircle2 className="w-4 h-4 text-green-600" />
                    ) : (
                      <StepIcon className="w-4 h-4" />
                    )}
                    <span className="text-sm font-medium whitespace-nowrap">{step.title}</span>
                  </button>
                  {!isLast && (
                    <div className={`w-8 h-0.5 mx-1 ${isPast ? 'bg-green-500' : 'bg-gray-200'}`} />
                  )}
                </div>
              );
            })}
          </div>
          <p className="text-sm text-gray-500 mt-2">
            {STEPS[currentStep].description}
          </p>
        </div>

        <div className="flex-1 overflow-y-auto p-6">
          {renderStepContent()}
        </div>

        {draftActive ? (
          <div className="px-6 pb-3">
            <div className="rounded-md border border-blue-200 bg-blue-50 px-3 py-2 text-xs text-blue-800">
              草稿已自动保存。重新打开可恢复；Access Token 和 SSH 私钥不会被保存。
            </div>
          </div>
        ) : null}

        <div className="px-6 py-4 border-t border-gray-200 flex items-center justify-between">
          <button
            type="button"
            onClick={currentStep === 0 ? handleClose : goPrev}
            className="btn btn-secondary"
          >
            {currentStep === 0 ? (
              '取消'
            ) : (
              <>
                <ChevronLeft className="w-4 h-4 mr-1" />
                上一步
              </>
            )}
          </button>

          {currentStep === STEPS.length - 1 ? (
            <button
              type="button"
              onClick={handleCreateProject}
              disabled={saving}
              className="btn btn-primary"
            >
              {saving ? '创建中...' : '创建项目'}
            </button>
          ) : (
            <button
              type="button"
              onClick={goNext}
              disabled={!canProceed()}
              className="btn btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
            >
              下一步
              <ChevronRight className="w-4 h-4 ml-1" />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
