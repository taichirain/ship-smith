'use client';

import { useState } from 'react';
import {
  BookOpen,
  Edit2,
  Save,
  X,
  Rocket,
  AlertTriangle,
  Globe,
  Terminal,
  ChevronDown,
  ChevronUp,
  Sparkles,
  Copy,
} from 'lucide-react';
import { api, Project, GenerateDeployCommandsResponse } from '@/lib/api';

interface ProjectRunbookProps {
  project: Project;
  onUpdate?: () => void;
}

const RUNBOOK_SECTIONS = [
  {
    key: 'notes',
    label: '项目说明',
    icon: BookOpen,
    placeholder: '记录项目的基本信息、用途、技术栈等...',
  },
  {
    key: 'releaseNotesHint',
    label: '发布注意事项',
    icon: Rocket,
    placeholder: '发布前需要检查的事项、发布流程、回滚方案等...',
  },
  {
    key: 'troubleshootingHint',
    label: '常见故障',
    icon: AlertTriangle,
    placeholder: '记录常见的故障现象、原因和解决方法...',
  },
  {
    key: 'sshHint',
    label: 'SSH 访问',
    icon: Terminal,
    placeholder: '服务器 SSH 连接信息、跳板机配置等...',
  },
];

const URL_SECTIONS = [
  {
    key: 'adminUrl',
    label: '管理后台',
    icon: Globe,
    placeholder: 'https://admin.example.com',
  },
  {
    key: 'metricsUrl',
    label: '监控面板',
    icon: Globe,
    placeholder: 'https://grafana.example.com/d/app',
  },
  {
    key: 'logsUrl',
    label: '日志系统',
    icon: Globe,
    placeholder: 'https://logs.example.com/app',
  },
];

export default function ProjectRunbook({ project, onUpdate }: ProjectRunbookProps) {
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set(['notes']));
  const [isGeneratingCommands, setIsGeneratingCommands] = useState(false);
  const [deployCommandResult, setDeployCommandResult] = useState<GenerateDeployCommandsResponse | null>(null);
  const [deployCommandError, setDeployCommandError] = useState<string | null>(null);
  const [formData, setFormData] = useState({
    notes: project.notes || '',
    releaseNotesHint: project.release_notes_hint || '',
    troubleshootingHint: project.troubleshooting_hint || '',
    sshHint: project.ssh_hint || '',
    adminUrl: project.admin_url || '',
    metricsUrl: project.metrics_url || '',
    logsUrl: project.logs_url || '',
  });

  const toggleSection = (section: string) => {
    const newExpanded = new Set(expandedSections);
    if (newExpanded.has(section)) {
      newExpanded.delete(section);
    } else {
      newExpanded.add(section);
    }
    setExpandedSections(newExpanded);
  };

  const startEditing = () => {
    setFormData({
      notes: project.notes || '',
      releaseNotesHint: project.release_notes_hint || '',
      troubleshootingHint: project.troubleshooting_hint || '',
      sshHint: project.ssh_hint || '',
      adminUrl: project.admin_url || '',
      metricsUrl: project.metrics_url || '',
      logsUrl: project.logs_url || '',
    });
    setEditing(true);
  };

  const cancelEditing = () => {
    setEditing(false);
  };

  const saveRunbook = async () => {
    try {
      setSaving(true);
      await api.updateProject(project.id, {
        notes: formData.notes || null,
        release_notes_hint: formData.releaseNotesHint || null,
        troubleshooting_hint: formData.troubleshootingHint || null,
        ssh_hint: formData.sshHint || null,
        admin_url: formData.adminUrl || null,
        metrics_url: formData.metricsUrl || null,
        logs_url: formData.logsUrl || null,
      });
      setEditing(false);
      if (onUpdate) {
        onUpdate();
      }
    } catch (err) {
      console.error('Failed to save runbook:', err);
    } finally {
      setSaving(false);
    }
  };

  const hasContent = !!(
    project.notes ||
    project.release_notes_hint ||
    project.troubleshooting_hint ||
    project.ssh_hint ||
    project.admin_url ||
    project.metrics_url ||
    project.logs_url
  );

  const generateDeployCommands = async () => {
    try {
      setIsGeneratingCommands(true);
      setDeployCommandError(null);
      const result = await api.generateDeployCommands(project.id, {
        user_goal: '为当前项目生成可执行的部署命令',
      });
      setDeployCommandResult(result);
    } catch (err: any) {
      const detail = err?.data?.detail;
      if (typeof detail === 'string') {
        setDeployCommandError(detail);
      } else if (detail?.message) {
        setDeployCommandError(detail.message);
      } else {
        setDeployCommandError('生成部署命令失败');
      }
    } finally {
      setIsGeneratingCommands(false);
    }
  };

  const copyCommand = async (command: string) => {
    try {
      await navigator.clipboard.writeText(command);
    } catch (err) {
      console.error('Failed to copy command:', err);
    }
  };

  return (
    <div className="card">
      <div className="p-4 border-b border-gray-100 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <BookOpen className="w-5 h-5 text-primary-600" />
          <h3 className="font-semibold text-gray-900">运行手册</h3>
        </div>
        {!editing && (
          <button
            onClick={startEditing}
            className="btn btn-secondary text-sm"
          >
            <Edit2 className="w-4 h-4 mr-2" />
            编辑
          </button>
        )}
        {editing && (
          <div className="flex gap-2">
            <button
              onClick={cancelEditing}
              disabled={saving}
              className="btn btn-secondary text-sm"
            >
              <X className="w-4 h-4 mr-2" />
              取消
            </button>
            <button
              onClick={saveRunbook}
              disabled={saving}
              className="btn btn-primary text-sm"
            >
              <Save className="w-4 h-4 mr-2" />
              {saving ? '保存中...' : '保存'}
            </button>
          </div>
        )}
      </div>

      <div className="px-4 pt-4">
        <div className="rounded-lg border border-primary-100 bg-primary-50/60 p-4">
          <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div>
              <div className="flex items-center gap-2 text-sm font-medium text-primary-900">
                <Sparkles className="w-4 h-4" />
                AI 部署命令生成
              </div>
              <p className="mt-1 text-xs text-primary-800/80">
                结合 README、docs、项目配置和 Agent 最近心跳，生成更贴近目标环境的部署命令。
              </p>
            </div>
            <button
              onClick={generateDeployCommands}
              disabled={isGeneratingCommands}
              className="btn btn-primary text-sm"
            >
              <Sparkles className="w-4 h-4 mr-2" />
              {isGeneratingCommands ? '生成中...' : '生成部署命令'}
            </button>
          </div>

          {deployCommandError && (
            <div className="mt-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
              {deployCommandError}
            </div>
          )}

          {deployCommandResult && (
            <div className="mt-4 space-y-4">
              <div className="grid gap-2 text-xs text-gray-600 md:grid-cols-3">
                <div className="rounded-md bg-white px-3 py-2 border border-gray-100">
                  <div className="text-gray-400">系统</div>
                  <div className="mt-1 font-medium text-gray-800">
                    {deployCommandResult.system_summary.os_name || 'Unknown'} {deployCommandResult.system_summary.os_release || ''}
                  </div>
                </div>
                <div className="rounded-md bg-white px-3 py-2 border border-gray-100">
                  <div className="text-gray-400">Shell</div>
                  <div className="mt-1 font-medium text-gray-800">
                    {deployCommandResult.system_summary.shell || 'Unknown'}
                  </div>
                </div>
                <div className="rounded-md bg-white px-3 py-2 border border-gray-100">
                  <div className="text-gray-400">Compose</div>
                  <div className="mt-1 font-medium text-gray-800">
                    {deployCommandResult.system_summary.docker_compose_command || 'Unknown'}
                  </div>
                </div>
              </div>

              {deployCommandResult.assumptions.length > 0 && (
                <div>
                  <div className="text-sm font-medium text-gray-800 mb-2">假设</div>
                  <div className="space-y-2">
                    {deployCommandResult.assumptions.map((item, index) => (
                      <div key={index} className="rounded-md bg-white px-3 py-2 text-sm text-gray-700 border border-gray-100">
                        {item}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {deployCommandResult.prechecks.length > 0 && (
                <div>
                  <div className="text-sm font-medium text-gray-800 mb-2">前置检查</div>
                  <div className="space-y-2">
                    {deployCommandResult.prechecks.map((item, index) => (
                      <pre key={index} className="rounded-md bg-gray-950 text-gray-100 p-3 text-xs overflow-x-auto whitespace-pre-wrap">
                        {item}
                      </pre>
                    ))}
                  </div>
                </div>
              )}

              <div>
                <div className="text-sm font-medium text-gray-800 mb-2">部署命令</div>
                <div className="space-y-3">
                  {deployCommandResult.commands.map((item, index) => (
                    <div key={`${item.title}-${index}`} className="rounded-lg border border-gray-200 bg-white">
                      <div className="flex items-center justify-between px-3 py-2 border-b border-gray-100">
                        <div>
                          <div className="text-sm font-medium text-gray-900">{item.title}</div>
                          <div className="text-xs text-gray-500">{item.purpose}</div>
                        </div>
                        <button
                          onClick={() => copyCommand(item.command)}
                          className="btn btn-secondary text-xs"
                        >
                          <Copy className="w-3.5 h-3.5 mr-1" />
                          复制
                        </button>
                      </div>
                      <pre className="bg-gray-950 text-gray-100 p-3 text-xs overflow-x-auto whitespace-pre-wrap rounded-b-lg">
                        {item.command}
                      </pre>
                    </div>
                  ))}
                </div>
              </div>

              {deployCommandResult.verification.length > 0 && (
                <div>
                  <div className="text-sm font-medium text-gray-800 mb-2">验证</div>
                  <div className="space-y-2">
                    {deployCommandResult.verification.map((item, index) => (
                      <div key={index} className="rounded-md bg-white px-3 py-2 text-sm text-gray-700 border border-gray-100">
                        {item}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {deployCommandResult.explanation && (
                <div className="rounded-md bg-white px-3 py-3 text-sm text-gray-700 border border-gray-100 whitespace-pre-wrap">
                  {deployCommandResult.explanation}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {!editing && !hasContent && (
        <div className="p-8 text-center">
          <BookOpen className="w-12 h-12 text-gray-300 mx-auto mb-3" />
          <p className="text-gray-500 text-sm mb-3">还没有运行手册</p>
          <p className="text-gray-400 text-xs mb-4">
            记录项目说明、发布注意事项、常见故障等信息，方便后续维护
          </p>
          <button
            onClick={startEditing}
            className="btn btn-primary text-sm"
          >
            <Edit2 className="w-4 h-4 mr-2" />
            创建运行手册
          </button>
        </div>
      )}

      {!editing && hasContent && (
        <div className="divide-y divide-gray-100">
          {RUNBOOK_SECTIONS.map((section) => {
            const Icon = section.icon;
            const value = (project as any)[section.key];
            const isExpanded = expandedSections.has(section.key);
            if (!value) return null;

            return (
              <div key={section.key}>
                <button
                  onClick={() => toggleSection(section.key)}
                  className="w-full p-4 flex items-center gap-3 text-left hover:bg-gray-50 transition-colors"
                >
                  <Icon className="w-5 h-5 text-gray-400 flex-shrink-0" />
                  <span className="font-medium text-gray-700 flex-1">
                    {section.label}
                  </span>
                  {isExpanded ? (
                    <ChevronUp className="w-5 h-5 text-gray-400" />
                  ) : (
                    <ChevronDown className="w-5 h-5 text-gray-400" />
                  )}
                </button>
                {isExpanded && (
                  <div className="px-4 pb-4">
                    <div className="p-3 bg-gray-50 rounded-lg text-sm text-gray-700 whitespace-pre-wrap">
                      {value}
                    </div>
                  </div>
                )}
              </div>
            );
          })}

          {URL_SECTIONS.some((section) => (project as any)[section.key]) && (
            <div className="p-4">
              <div className="flex items-center gap-2 mb-3">
                <Globe className="w-5 h-5 text-gray-400" />
                <span className="font-medium text-gray-700">常用链接</span>
              </div>
              <div className="space-y-2">
                {URL_SECTIONS.map((section) => {
                  const Icon = section.icon;
                  const value = (project as any)[section.key];
                  if (!value) return null;

                  return (
                    <div key={section.key} className="flex items-center gap-2 text-sm">
                      <Icon className="w-4 h-4 text-gray-400" />
                      <span className="text-gray-500 w-20">{section.label}:</span>
                      <a
                        href={value}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-primary-600 hover:text-primary-700 truncate flex-1"
                      >
                        {value}
                      </a>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}

      {editing && (
        <div className="p-4 space-y-4">
          {RUNBOOK_SECTIONS.map((section) => {
            const Icon = section.icon;
            return (
              <div key={section.key}>
                <label className="flex items-center gap-2 text-sm font-medium text-gray-700 mb-2">
                  <Icon className="w-4 h-4 text-gray-400" />
                  {section.label}
                </label>
                <textarea
                  value={formData[section.key as keyof typeof formData]}
                  onChange={(e) =>
                    setFormData({ ...formData, [section.key]: e.target.value })
                  }
                  placeholder={section.placeholder}
                  rows={4}
                  className="input resize-none"
                />
              </div>
            );
          })}

          <div>
            <label className="flex items-center gap-2 text-sm font-medium text-gray-700 mb-2">
              <Globe className="w-4 h-4 text-gray-400" />
              常用链接
            </label>
            <div className="space-y-3">
              {URL_SECTIONS.map((section) => {
                const Icon = section.icon;
                return (
                  <div key={section.key} className="flex items-center gap-2">
                    <Icon className="w-4 h-4 text-gray-400 w-6" />
                    <span className="text-sm text-gray-500 w-24">{section.label}</span>
                    <input
                      type="url"
                      value={formData[section.key as keyof typeof formData]}
                      onChange={(e) =>
                        setFormData({ ...formData, [section.key]: e.target.value })
                      }
                      placeholder={section.placeholder}
                      className="input flex-1 text-sm"
                    />
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
