'use client';

import { useState, useEffect } from 'react';
import {
  AlertTriangle,
  Loader2,
  CheckCircle2,
  Terminal,
  Lightbulb,
  ChevronDown,
  ChevronUp,
  AlertCircle,
  Sparkles,
} from 'lucide-react';
import { api } from '@/lib/api';

interface LLMAnalysis {
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
}

interface FailureExplanation {
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
  llm_analysis?: LLMAnalysis;
}

const CATEGORY_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  git: { bg: 'bg-orange-50', text: 'text-orange-700', border: 'border-orange-200' },
  docker: { bg: 'bg-blue-50', text: 'text-blue-700', border: 'border-blue-200' },
  hook: { bg: 'bg-purple-50', text: 'text-purple-700', border: 'border-purple-200' },
  app: { bg: 'bg-green-50', text: 'text-green-700', border: 'border-green-200' },
  system: { bg: 'bg-gray-50', text: 'text-gray-700', border: 'border-gray-200' },
  unknown: { bg: 'bg-gray-50', text: 'text-gray-700', border: 'border-gray-200' },
};

const CATEGORY_LABELS: Record<string, string> = {
  git: 'Git',
  docker: 'Docker',
  hook: '钩子',
  app: '应用',
  system: '系统',
  unknown: '未知',
};

interface DeploymentFailurePanelProps {
  deploymentId: number;
}

export default function DeploymentFailurePanel({ deploymentId }: DeploymentFailurePanelProps) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [explanation, setExplanation] = useState<FailureExplanation | null>(null);
  const [expandedErrors, setExpandedErrors] = useState(false);

  useEffect(() => {
    async function fetchExplanation() {
      try {
        setLoading(true);
        const data = await api.getDeploymentFailureExplanation(deploymentId);
        setExplanation(data as any);
        setError(null);
      } catch (err: any) {
        setError(err.message || 'Failed to load failure explanation');
      } finally {
        setLoading(false);
      }
    }
    fetchExplanation();
  }, [deploymentId]);

  if (loading) {
    return (
      <div className="card p-6">
        <div className="flex items-center justify-center py-8">
          <Loader2 className="w-8 h-8 animate-spin text-primary-600" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="card p-6">
        <div className="text-center py-8 text-red-600">{error}</div>
      </div>
    );
  }

  if (!explanation) {
    return null;
  }

  const categoryColor = CATEGORY_COLORS[explanation.category] || CATEGORY_COLORS.unknown;
  const categoryLabel = CATEGORY_LABELS[explanation.category] || explanation.category;

  return (
    <div className="card overflow-hidden">
      <div className={`p-6 ${categoryColor.bg} border-b ${categoryColor.border}`}>
        <div className="flex items-start gap-3">
          <AlertTriangle className={`w-6 h-6 ${categoryColor.text} flex-shrink-0 mt-0.5`} />
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${categoryColor.bg} ${categoryColor.text} border ${categoryColor.border}`}>
                {categoryLabel}
              </span>
              <span className="text-xs text-gray-500">
                阶段：{explanation.failure_phase_label}
              </span>
              {explanation.error_code && (
                <code className="text-xs bg-white px-2 py-0.5 rounded border border-gray-200 text-gray-600">
                  {explanation.error_code}
                </code>
              )}
            </div>
            <h3 className={`text-lg font-semibold ${categoryColor.text} mb-2`}>
              {explanation.title}
            </h3>
            <p className="text-sm text-gray-600">
              {explanation.human_explanation}
            </p>
          </div>
        </div>
      </div>

      {explanation.additional_notes && explanation.additional_notes.length > 0 && (
        <div className="p-4 bg-amber-50 border-b border-amber-200">
          <div className="flex items-start gap-2">
            <Lightbulb className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <h4 className="text-sm font-medium text-amber-900 mb-1">日志分析发现</h4>
              <ul className="text-sm text-amber-800 space-y-1">
                {explanation.additional_notes.map((note, index) => (
                  <li key={index}>• {note}</li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}

      <div className="p-6">
        <div className="flex items-center gap-2 mb-4">
          <AlertCircle className="w-5 h-5 text-blue-600" />
          <h4 className="font-semibold text-gray-900">排查检查清单</h4>
        </div>

        <div className="space-y-3 mb-6">
          {explanation.checklist.map((item, index) => (
            <div
              key={index}
              className="flex items-start gap-3 p-3 rounded-lg bg-gray-50"
            >
              <div className="w-6 h-6 rounded-full bg-white border-2 border-gray-200 flex-shrink-0 flex items-center justify-center">
                <span className="text-xs text-gray-400">{index + 1}</span>
              </div>
              <div className="flex-1 min-w-0">
                <div className="font-medium text-gray-900 text-sm">{item.action}</div>
                <p className="text-xs text-gray-500 mt-1">{item.description}</p>
                {item.command && (
                  <code className="mt-2 inline-block text-xs bg-gray-900 text-green-400 px-2 py-1 rounded">
                    {item.command}
                  </code>
                )}
              </div>
            </div>
          ))}
        </div>

        <div className="flex items-center gap-2 mb-4">
          <CheckCircle2 className="w-5 h-5 text-green-600" />
          <h4 className="font-semibold text-gray-900">建议修复步骤</h4>
        </div>

        <ol className="space-y-2 mb-6">
          {explanation.resolution_steps.map((step, index) => (
            <li key={index} className="flex items-start gap-2 text-sm text-gray-700">
              <span className="text-gray-400 mt-0.5">•</span>
              <span>{step}</span>
            </li>
          ))}
        </ol>

        {explanation.log_analysis && explanation.log_analysis.extracted_errors.length > 0 && (
          <div className="border-t pt-6">
            <button
              onClick={() => setExpandedErrors(!expandedErrors)}
              className="flex items-center gap-2 w-full text-left"
            >
              <Terminal className="w-5 h-5 text-gray-500" />
              <h4 className="font-semibold text-gray-900">从日志中提取的错误</h4>
              <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded">
                {explanation.log_analysis.extracted_errors.length} 条
              </span>
              <div className="flex-1" />
              {expandedErrors ? (
                <ChevronUp className="w-5 h-5 text-gray-400" />
              ) : (
                <ChevronDown className="w-5 h-5 text-gray-400" />
              )}
            </button>

            {expandedErrors && (
              <div className="mt-4 space-y-2">
                {explanation.log_analysis.extracted_errors.map((err, index) => (
                  <div
                    key={index}
                    className="p-3 bg-red-50 border border-red-200 rounded font-mono text-xs text-red-800 whitespace-pre-wrap break-all"
                  >
                    {err}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {explanation.log_analysis && explanation.log_analysis.patterns_detected.length > 0 && (
          <div className="border-t pt-6 mt-6">
            <h4 className="font-semibold text-gray-900 mb-4">检测到的问题模式</h4>
            <div className="space-y-3">
              {explanation.log_analysis.patterns_detected.map((pattern, index) => (
                <div key={index} className="p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
                  <div className="font-medium text-yellow-900 text-sm mb-2">
                    {pattern.label}
                  </div>
                  <div className="space-y-1">
                    {pattern.matched_lines.map((line, lineIndex) => (
                      <div
                        key={lineIndex}
                        className="text-xs text-yellow-800 font-mono whitespace-pre-wrap break-all bg-yellow-100 p-2 rounded"
                      >
                        {line}
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {explanation.llm_analysis && (
          <div className="border-t pt-6 mt-6">
            <div className="flex items-center gap-2 mb-4">
              <Sparkles className="w-5 h-5 text-purple-600" />
              <h4 className="font-semibold text-gray-900">AI 智能分析</h4>
              {explanation.llm_analysis.llm_provider && explanation.llm_analysis.llm_model && (
                <span className="text-xs bg-purple-100 text-purple-700 px-2 py-0.5 rounded">
                  {explanation.llm_analysis.llm_provider} / {explanation.llm_analysis.llm_model}
                  {explanation.llm_analysis.llm_duration_ms && ` (${explanation.llm_analysis.llm_duration_ms}ms)`}
                </span>
              )}
            </div>

            {explanation.llm_analysis.llm_analysis_failed ? (
              <div className="p-4 bg-gray-50 border border-gray-200 rounded-lg text-sm text-gray-600">
                <div className="flex items-start gap-2">
                  <AlertCircle className="w-5 h-5 text-gray-400 flex-shrink-0 mt-0.5" />
                  <div>
                    <p className="font-medium text-gray-700">AI 分析不可用</p>
                    <p className="text-xs text-gray-500 mt-1">
                      {explanation.llm_analysis.llm_error || '请检查 LLM 配置'}
                    </p>
                  </div>
                </div>
              </div>
            ) : (
              <div className="space-y-4">
                {explanation.llm_analysis.root_cause && (
                  <div className="p-4 bg-purple-50 border border-purple-200 rounded-lg">
                    <div className="text-sm font-medium text-purple-900 mb-1">
                      根本原因分析
                    </div>
                    <p className="text-sm text-purple-800">
                      {explanation.llm_analysis.root_cause}
                    </p>
                  </div>
                )}

                {explanation.llm_analysis.likely_problem && (
                  <div className="p-4 bg-indigo-50 border border-indigo-200 rounded-lg">
                    <div className="text-sm font-medium text-indigo-900 mb-1">
                      最可能的问题
                    </div>
                    <p className="text-sm text-indigo-800">
                      {explanation.llm_analysis.likely_problem}
                    </p>
                  </div>
                )}

                {explanation.llm_analysis.explanation && (
                  <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
                    <div className="text-sm font-medium text-blue-900 mb-1">
                      详细解释
                    </div>
                    <p className="text-sm text-blue-800 whitespace-pre-wrap">
                      {explanation.llm_analysis.explanation}
                    </p>
                  </div>
                )}

                {explanation.llm_analysis.first_checks && explanation.llm_analysis.first_checks.length > 0 && (
                  <div>
                    <div className="text-sm font-medium text-gray-700 mb-2">
                      AI 建议先检查这些：
                    </div>
                    <ul className="space-y-2">
                      {explanation.llm_analysis.first_checks.map((check, index) => (
                        <li key={index} className="flex items-start gap-2 text-sm">
                          <span className="text-gray-400 mt-0.5">•</span>
                          <span className="text-gray-700">{check}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {explanation.llm_analysis.debug_commands && explanation.llm_analysis.debug_commands.length > 0 && (
                  <div>
                    <div className="text-sm font-medium text-gray-700 mb-2">
                      建议执行的命令：
                    </div>
                    <div className="space-y-2">
                      {explanation.llm_analysis.debug_commands.map((cmd, index) => (
                        <code
                          key={index}
                          className="block text-xs bg-gray-900 text-green-400 px-3 py-2 rounded"
                        >
                          {cmd}
                        </code>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
