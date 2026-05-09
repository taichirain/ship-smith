'use client';

import {
  X,
  Sparkles,
  FileText,
  ArrowRight,
} from 'lucide-react';

interface ProjectCreateModeSelectorProps {
  onClose: () => void;
  onSelectWizard: () => void;
  onSelectForm: () => void;
}

export default function ProjectCreateModeSelector({
  onClose,
  onSelectWizard,
  onSelectForm,
}: ProjectCreateModeSelectorProps) {
  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-2xl">
        <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900">创建新项目</h2>
          <button
            type="button"
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600"
          >
            <X className="w-6 h-6" />
          </button>
        </div>

        <div className="p-6">
          <p className="text-gray-600 mb-6">
            选择适合您的创建方式。两种方式创建的项目完全相同，只是用户体验不同。
          </p>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <button
              type="button"
              onClick={onSelectWizard}
              className="group text-left p-6 border-2 border-primary-200 rounded-lg hover:border-primary-400 hover:bg-primary-50/50 transition-all"
            >
              <div className="flex items-start justify-between">
                <div className="w-12 h-12 bg-primary-100 rounded-lg flex items-center justify-center mb-4">
                  <Sparkles className="w-6 h-6 text-primary-600" />
                </div>
                <ArrowRight className="w-5 h-5 text-gray-300 group-hover:text-primary-500 transition-colors" />
              </div>
              <h3 className="text-lg font-semibold text-gray-900 mb-2">
                向导式创建
                <span className="ml-2 inline-block px-2 py-0.5 text-xs font-medium bg-primary-100 text-primary-700 rounded">
                  推荐
                </span>
              </h3>
              <p className="text-sm text-gray-600 mb-3">
                分步引导，逐步填写配置，适合新手或首次使用的用户
              </p>
              <ul className="text-xs text-gray-500 space-y-1">
                <li className="flex items-center gap-1">
                  <span className="text-primary-500">✓</span> 分步指导，降低理解成本
                </li>
                <li className="flex items-center gap-1">
                  <span className="text-primary-500">✓</span> 每步都有说明和示例
                </li>
                <li className="flex items-center gap-1">
                  <span className="text-primary-500">✓</span> 配置预览和 shipsmith.yaml 导出
                </li>
              </ul>
            </button>

            <button
              type="button"
              onClick={onSelectForm}
              className="group text-left p-6 border-2 border-gray-200 rounded-lg hover:border-gray-300 hover:bg-gray-50/50 transition-all"
            >
              <div className="flex items-start justify-between">
                <div className="w-12 h-12 bg-gray-100 rounded-lg flex items-center justify-center mb-4">
                  <FileText className="w-6 h-6 text-gray-600" />
                </div>
                <ArrowRight className="w-5 h-5 text-gray-300 group-hover:text-gray-500 transition-colors" />
              </div>
              <h3 className="text-lg font-semibold text-gray-900 mb-2">
                高级表单
              </h3>
              <p className="text-sm text-gray-600 mb-3">
                传统单页表单，适合熟悉 ShipSmith 配置的高级用户
              </p>
              <ul className="text-xs text-gray-500 space-y-1">
                <li className="flex items-center gap-1">
                  <span className="text-gray-400">✓</span> 所有字段一目了然
                </li>
                <li className="flex items-center gap-1">
                  <span className="text-gray-400">✓</span> 快速填写，无需分步
                </li>
                <li className="flex items-center gap-1">
                  <span className="text-gray-400">✓</span> 适合已有项目模板的用户
                </li>
              </ul>
            </button>
          </div>
        </div>

        <div className="px-6 py-4 border-t border-gray-200 bg-gray-50 rounded-b-lg">
          <p className="text-xs text-gray-500 text-center">
            💡 提示：选择后仍然可以在项目详情页随时修改配置
          </p>
        </div>
      </div>
    </div>
  );
}
