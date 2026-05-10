'use client';

import { useState, useEffect, useMemo } from 'react';
import Link from 'next/link';
import { 
  Plus, 
  FolderGit2, 
  Search, 
  Clock, 
  AlertTriangle,
  ArrowUpDown,
  GitCommit,
  Radio,
  ChevronDown,
  CheckCircle,
  ChevronRight
} from 'lucide-react';
import AppLayout from '@/components/AppLayout';
import { api, Project } from '@/lib/api';
import StatusBadge from '@/components/StatusBadge';
import ProjectWizard from '@/components/ProjectWizard';
import ProjectForm from '@/components/ProjectForm';
import ProjectCreateModeSelector from '@/components/ProjectCreateModeSelector';

type SortOption = 
  | 'created_at_desc'
  | 'last_deployment_at_desc'
  | 'agent_last_seen_at_desc'
  | 'health_status_priority';

const SORT_OPTIONS: { value: SortOption; label: string }[] = [
  { value: 'created_at_desc', label: '最新创建' },
  { value: 'last_deployment_at_desc', label: '最近部署优先' },
  { value: 'agent_last_seen_at_desc', label: '最近心跳优先' },
  { value: 'health_status_priority', label: '问题优先' },
];

const ENVIRONMENT_OPTIONS: { value: string | null; label: string; color: string }[] = [
  { value: null, label: 'All', color: '' },
  { value: 'production', label: '生产', color: 'bg-red-100 text-red-800 border-red-200' },
  { value: 'staging', label: '预发', color: 'bg-orange-100 text-orange-800 border-orange-200' },
  { value: 'development', label: '开发', color: 'bg-green-100 text-green-800 border-green-200' },
  { value: 'testing', label: '测试', color: 'bg-blue-100 text-blue-800 border-blue-200' },
  { value: 'other', label: '其他', color: 'bg-gray-100 text-gray-800 border-gray-200' },
];

function getEnvironmentBadge(environment: string | null | undefined) {
  if (!environment) return null;
  const env = ENVIRONMENT_OPTIONS.find(e => e.value === environment);
  if (!env) return null;
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium border ${env.color}`}>
      {env.label}
    </span>
  );
}

const STATUS_TABS: { value: string | null; label: string }[] = [
  { value: null, label: 'All' },
  { value: 'unhealthy', label: 'Health Check Failed' },
  { value: 'degraded', label: 'Degraded' },
  { value: 'healthy', label: 'Healthy' },
  { value: 'unknown', label: 'Unknown' },
];

function formatRelativeTime(dateStr: string | null | undefined): string {
  if (!dateStr) return '-';
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSecs = Math.floor(diffMs / 1000);
  
  if (diffSecs < 60) return `${diffSecs}秒前`;
  const diffMins = Math.floor(diffSecs / 60);
  if (diffMins < 60) return `${diffMins}分钟前`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}小时前`;
  const diffDays = Math.floor(diffHours / 24);
  if (diffDays < 30) return `${diffDays}天前`;
  return date.toLocaleDateString('zh-CN');
}

function getDeploymentStatusBadge(status: string | null | undefined) {
  if (!status) return null;
  const styles: Record<string, string> = {
    success: 'bg-green-100 text-green-800',
    failed: 'bg-red-100 text-red-800',
    running: 'bg-blue-100 text-blue-800',
    queued: 'bg-yellow-100 text-yellow-800',
  };
  const labels: Record<string, string> = {
    success: 'Deployed',
    failed: 'Deploy Failed',
    running: 'Running',
    queued: 'Queued',
  };
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${styles[status] || 'bg-gray-100 text-gray-800'}`}>
      {labels[status] || status}
    </span>
  );
}

function ProjectCard({ project }: { project: Project }) {
  return (
    <Link
      href={`/projects/${project.id}`}
      className="card p-6 hover:border-primary-300 hover:shadow-md transition-all group block"
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3 flex-wrap">
            <h3 className="text-lg font-semibold text-gray-900 group-hover:text-primary-700 truncate">
              {project.name}
            </h3>
            {getEnvironmentBadge(project.environment)}
            <StatusBadge status={project.health_status || 'unknown'} small />
            {getDeploymentStatusBadge(project.last_deployment_status)}
            {project.agent_version_outdated && (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-orange-100 text-orange-800">
                <AlertTriangle className="w-3 h-3" />
                Agent v{project.agent_version || '?'} 落后
              </span>
            )}
          </div>
          
          <div className="mt-3 flex items-center gap-4 text-sm text-gray-600 flex-wrap">
            <code className="bg-gray-100 px-2 py-0.5 rounded text-xs">
              {project.deploy_strategy}
            </code>
            <span className="flex items-center gap-1 truncate">
              <FolderGit2 className="w-4 h-4 flex-shrink-0" />
              <span className="truncate">{project.git_repo}</span>
            </span>
          </div>
          
          <div className="mt-3 grid grid-cols-2 md:grid-cols-3 gap-3 text-sm">
            {project.current_commit_hash && (
              <div className="flex items-center gap-1.5 text-gray-600">
                <GitCommit className="w-4 h-4 flex-shrink-0 text-gray-400" />
                <span className="truncate font-mono text-xs">
                  {project.current_commit_hash.substring(0, 8)}
                </span>
              </div>
            )}
            
            {project.last_deployment_at && (
              <div className="flex items-center gap-1.5 text-gray-600">
                <Radio className="w-4 h-4 flex-shrink-0 text-gray-400" />
                <span>上次部署 {formatRelativeTime(project.last_deployment_at)}</span>
              </div>
            )}
            
            <div className="flex items-center gap-1.5 text-gray-600">
              <Clock className="w-4 h-4 flex-shrink-0 text-gray-400" />
              <span>心跳 {formatRelativeTime(project.agent_last_seen_at)}</span>
            </div>
          </div>
        </div>
        
        <ChevronRight className="w-5 h-5 text-gray-400 group-hover:text-primary-500 flex-shrink-0 transition-colors" />
      </div>
    </Link>
  );
}

export default function ProjectsPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showModeSelector, setShowModeSelector] = useState(false);
  const [showWizard, setShowWizard] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<string | null>(null);
  const [environmentFilter, setEnvironmentFilter] = useState<string | null>(null);
  const [agentOutdatedFilter, setAgentOutdatedFilter] = useState<boolean | null>(null);
  const [sortBy, setSortBy] = useState<SortOption>('created_at_desc');
  const [showSortDropdown, setShowSortDropdown] = useState(false);

  const apiParams = useMemo(() => {
    const params: Record<string, string> = {};
    if (statusFilter) params.health_status = statusFilter;
    if (environmentFilter) params.environment = environmentFilter;
    if (searchQuery.trim()) params.q = searchQuery.trim();
    
    switch (sortBy) {
      case 'created_at_desc':
        params.sort_by = 'created_at';
        params.sort_order = 'desc';
        break;
      case 'last_deployment_at_desc':
        params.sort_by = 'last_deployment_at';
        params.sort_order = 'desc';
        break;
      case 'agent_last_seen_at_desc':
        params.sort_by = 'agent_last_seen_at';
        params.sort_order = 'desc';
        break;
      case 'health_status_priority':
        params.sort_by = 'health_status_priority';
        params.sort_order = 'asc';
        break;
    }
    
    return params;
  }, [searchQuery, statusFilter, environmentFilter, sortBy]);

  async function loadProjects() {
    try {
      setLoading(true);
      const data = await api.listProjects(apiParams);
      setProjects(data);
      setError(null);
    } catch (err: any) {
      setError(err.message || 'Failed to load projects');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadProjects();
  }, [apiParams]);

  function handleWizardSuccess(project: Project) {
    setShowWizard(false);
    setSuccessMessage(`项目 "${project.name}" 创建成功！请在服务器上安装 Agent 并配置 token。`);
    loadProjects();
    setTimeout(() => setSuccessMessage(null), 5000);
  }

  function handleWizardError(error: string) {
    setError(error);
  }

  function handleFormSuccess(project: Project) {
    setShowForm(false);
    setSuccessMessage(`项目 "${project.name}" 创建成功！请在服务器上安装 Agent 并配置 token。`);
    loadProjects();
    setTimeout(() => setSuccessMessage(null), 5000);
  }

  function handleFormError(error: string) {
    setError(error);
  }

  function handleSelectWizard() {
    setShowModeSelector(false);
    setShowWizard(true);
  }

  function handleSelectForm() {
    setShowModeSelector(false);
    setShowForm(true);
  }

  const currentSortLabel = SORT_OPTIONS.find(o => o.value === sortBy)?.label || '排序';

  const filteredProjects = useMemo(() => {
    if (agentOutdatedFilter === null) return projects;
    return projects.filter(p => p.agent_version_outdated === agentOutdatedFilter);
  }, [projects, agentOutdatedFilter]);

  return (
    <AppLayout>
      {showModeSelector && (
        <ProjectCreateModeSelector
          onClose={() => setShowModeSelector(false)}
          onSelectWizard={handleSelectWizard}
          onSelectForm={handleSelectForm}
        />
      )}

      {showWizard && (
        <ProjectWizard
          onClose={() => setShowWizard(false)}
          onSuccess={handleWizardSuccess}
          onError={handleWizardError}
        />
      )}

      {showForm && (
        <ProjectForm
          onClose={() => setShowForm(false)}
          onSuccess={handleFormSuccess}
          onError={handleFormError}
        />
      )}

      <div className="p-8 max-w-6xl">
        <div className="flex items-center justify-between mb-8 flex-wrap gap-4">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Projects</h1>
            <p className="text-gray-600 mt-1">管理您的部署和功能开关</p>
          </div>
          <button
            onClick={() => setShowModeSelector(true)}
            className="btn btn-primary"
          >
            <Plus className="w-4 h-4 mr-2" />
            创建项目
          </button>
        </div>

        {successMessage && (
          <div className="mb-6 bg-green-50 border border-green-200 text-green-800 px-4 py-3 rounded-md flex items-center gap-2">
            <CheckCircle className="w-5 h-5 flex-shrink-0" />
            <span>{successMessage}</span>
          </div>
        )}

        {error && (
          <div className="mb-6 text-red-600 text-sm bg-red-50 px-4 py-3 rounded-md">
            {error}
          </div>
        )}

        {!loading && filteredProjects.length === 0 && !searchQuery && !statusFilter && !environmentFilter && !agentOutdatedFilter ? (
          <div className="card p-12 text-center">
            <FolderGit2 className="w-16 h-16 text-gray-300 mx-auto mb-6" />
            <h2 className="text-xl font-semibold text-gray-900 mb-2">开始管理您的项目</h2>
            <p className="text-gray-600 mb-6 max-w-md mx-auto">
              ShipSmith 帮助您简化部署流程，从代码到生产环境只需几步。
              创建您的第一个项目开始体验。
            </p>
            <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
              <button
                onClick={() => setShowWizard(true)}
                className="btn btn-primary"
              >
                <Plus className="w-4 h-4 mr-2" />
                创建第一个项目
              </button>
              <div className="text-sm text-gray-500 flex items-center gap-2">
                <span className="w-6 h-6 rounded-full bg-primary-100 text-primary-700 flex items-center justify-center text-xs font-medium">1</span>
                创建项目
                <span className="text-gray-300">→</span>
                <span className="w-6 h-6 rounded-full bg-gray-100 text-gray-500 flex items-center justify-center text-xs font-medium">2</span>
                安装 Agent
                <span className="text-gray-300">→</span>
                <span className="w-6 h-6 rounded-full bg-gray-100 text-gray-500 flex items-center justify-center text-xs font-medium">3</span>
                开始部署
              </div>
            </div>
          </div>
        ) : (
          <>
            <div className="mb-6 space-y-4">
              <div className="flex items-center gap-3 flex-wrap">
                <div className="relative flex-1 min-w-[240px]">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                  <input
                    type="text"
                    placeholder="搜索项目名或仓库..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="input pl-10"
                  />
                </div>
                
                <div className="relative">
                  <button
                    onClick={() => setShowSortDropdown(!showSortDropdown)}
                    className="btn btn-secondary flex items-center gap-2"
                  >
                    <ArrowUpDown className="w-4 h-4" />
                    {currentSortLabel}
                    <ChevronDown className="w-4 h-4" />
                  </button>
                  
                  {showSortDropdown && (
                    <>
                      <div 
                        className="fixed inset-0 z-10" 
                        onClick={() => setShowSortDropdown(false)}
                      />
                      <div className="absolute right-0 top-full mt-1 bg-white border border-gray-200 rounded-md shadow-lg z-20 min-w-[180px]">
                        {SORT_OPTIONS.map((option) => (
                          <button
                            key={option.value}
                            onClick={() => {
                              setSortBy(option.value);
                              setShowSortDropdown(false);
                            }}
                            className={`w-full text-left px-4 py-2 text-sm hover:bg-gray-50 ${
                              sortBy === option.value ? 'text-primary-700 bg-primary-50 font-medium' : 'text-gray-700'
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

              <div className="flex items-center gap-2 overflow-x-auto pb-1">
                <span className="text-xs font-medium text-gray-500 whitespace-nowrap">环境:</span>
                {ENVIRONMENT_OPTIONS.map((tab) => {
                  const isActive = environmentFilter === tab.value;
                  return (
                    <button
                      key={tab.value || 'all'}
                      onClick={() => setEnvironmentFilter(tab.value)}
                      className={`px-3 py-1.5 text-xs font-medium rounded-md whitespace-nowrap transition-colors border ${
                        isActive
                          ? tab.color
                          : 'bg-white border-gray-200 text-gray-600 hover:bg-gray-50'
                      }`}
                    >
                      {tab.label}
                    </button>
                  );
                })}
              </div>

              <div className="flex items-center gap-2 overflow-x-auto pb-1">
                <span className="text-xs font-medium text-gray-500 whitespace-nowrap">Agent:</span>
                <button
                  onClick={() => setAgentOutdatedFilter(null)}
                  className={`px-3 py-1.5 text-xs font-medium rounded-md whitespace-nowrap transition-colors border ${
                    agentOutdatedFilter === null
                      ? 'bg-primary-50 border-primary-300 text-primary-700'
                      : 'bg-white border-gray-200 text-gray-600 hover:bg-gray-50'
                  }`}
                >
                  全部
                </button>
                <button
                  onClick={() => setAgentOutdatedFilter(true)}
                  className={`px-3 py-1.5 text-xs font-medium rounded-md whitespace-nowrap transition-colors border ${
                    agentOutdatedFilter === true
                      ? 'bg-orange-100 border-orange-300 text-orange-700'
                      : 'bg-white border-gray-200 text-gray-600 hover:bg-gray-50'
                  }`}
                >
                  版本落后
                </button>
                <button
                  onClick={() => setAgentOutdatedFilter(false)}
                  className={`px-3 py-1.5 text-xs font-medium rounded-md whitespace-nowrap transition-colors border ${
                    agentOutdatedFilter === false
                      ? 'bg-green-100 border-green-300 text-green-700'
                      : 'bg-white border-gray-200 text-gray-600 hover:bg-gray-50'
                  }`}
                >
                  最新版本
                </button>
              </div>

              <div className="flex items-center gap-1 overflow-x-auto pb-1">
                {STATUS_TABS.map((tab) => {
                  const isActive = statusFilter === tab.value;
                  return (
                    <button
                      key={tab.value || 'all'}
                      onClick={() => setStatusFilter(tab.value)}
                      className={`px-4 py-2 text-sm font-medium rounded-md whitespace-nowrap transition-colors ${
                        isActive
                          ? 'bg-primary-100 text-primary-700'
                          : 'text-gray-600 hover:bg-gray-100'
                      }`}
                    >
                      {tab.label}
                    </button>
                  );
                })}
              </div>
            </div>

            {loading ? (
              <div className="text-center py-12 text-gray-500">Loading...</div>
            ) : filteredProjects.length === 0 ? (
              <div className="card p-12 text-center">
                <FolderGit2 className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                <p className="text-gray-600">没有匹配的项目</p>
              </div>
            ) : (
              <div className="grid gap-4">
                {filteredProjects.map((project) => (
                  <ProjectCard key={project.id} project={project} />
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </AppLayout>
  );
}
