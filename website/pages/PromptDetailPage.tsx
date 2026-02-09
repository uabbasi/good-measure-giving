import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useLandingTheme } from '../contexts/LandingThemeContext';
import {
  ArrowLeft,
  Copy,
  Check,
  CheckCircle2,
  Clock,
  FileCode2,
  ChevronDown,
  ChevronRight,
  Info
} from 'lucide-react';

interface Annotation {
  section: string;
  lines: string;
  explanation: string;
}

interface PromptDetail {
  id: string;
  name: string;
  category: string;
  description: string;
  status: 'active' | 'planned';
  source_file: string;
  content: string;
  annotations: Annotation[];
}

const categoryLabels: Record<string, string> = {
  quality_validation: 'Quality Validation',
  data_extraction: 'Data Extraction',
  narrative_generation: 'Narrative Generation',
  category_calibration: 'Category Calibration',
};

export const PromptDetailPage: React.FC = () => {
  const { isDark } = useLandingTheme();
  const { promptId } = useParams<{ promptId: string }>();
  const [prompt, setPrompt] = useState<PromptDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [expandedAnnotations, setExpandedAnnotations] = useState<Set<number>>(new Set([0]));

  useEffect(() => {
    if (!promptId) return;

    fetch(`/data/prompts/${promptId}.json`)
      .then(res => {
        if (!res.ok) throw new Error('Prompt not found');
        return res.json();
      })
      .then(setPrompt)
      .catch(err => setError(err.message))
      .finally(() => setLoading(false));
  }, [promptId]);

  const copyToClipboard = async () => {
    if (!prompt) return;
    try {
      await navigator.clipboard.writeText(prompt.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  const toggleAnnotation = (index: number) => {
    setExpandedAnnotations(prev => {
      const next = new Set(prev);
      if (next.has(index)) {
        next.delete(index);
      } else {
        next.add(index);
      }
      return next;
    });
  };

  if (loading) {
    return (
      <div className={`min-h-screen flex items-center justify-center ${isDark ? 'bg-slate-950' : 'bg-slate-50'}`}>
        <div className={isDark ? 'text-slate-400' : 'text-slate-600'}>Loading prompt...</div>
      </div>
    );
  }

  if (error || !prompt) {
    return (
      <div className={`min-h-screen ${isDark ? 'bg-slate-950' : 'bg-slate-50'}`}>
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
          <Link
            to="/prompts"
            className={`inline-flex items-center gap-2 mb-8 ${isDark ? 'text-slate-400 hover:text-white' : 'text-slate-600 hover:text-slate-900'}`}
          >
            <ArrowLeft className="w-4 h-4" />
            Back to all prompts
          </Link>
          <div className={`rounded-xl p-8 text-center ${isDark ? 'bg-slate-900' : 'bg-white border border-slate-200'}`}>
            <h1 className={`text-2xl font-bold mb-2 ${isDark ? 'text-white' : 'text-slate-900'}`}>
              Prompt Not Found
            </h1>
            <p className={isDark ? 'text-slate-400' : 'text-slate-600'}>
              The prompt you're looking for doesn't exist or may have been removed.
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={`min-h-screen transition-colors duration-300 ${isDark ? 'bg-slate-950' : 'bg-slate-50'}`}>
      {/* Header */}
      <div className={`border-b ${isDark ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200'}`}>
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <Link
            to="/prompts"
            className={`inline-flex items-center gap-2 mb-4 text-sm ${isDark ? 'text-slate-400 hover:text-white' : 'text-slate-600 hover:text-slate-900'}`}
          >
            <ArrowLeft className="w-4 h-4" />
            Back to all prompts
          </Link>

          <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-4">
            <div>
              <div className="flex items-center gap-3 mb-2">
                <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${isDark ? 'bg-emerald-900/30' : 'bg-emerald-100'}`}>
                  <FileCode2 className={`w-5 h-5 ${isDark ? 'text-emerald-400' : 'text-emerald-600'}`} />
                </div>
                <h1 className={`text-2xl font-bold font-merriweather ${isDark ? 'text-white' : 'text-slate-900'}`}>
                  {prompt.name}
                </h1>
              </div>
              <p className={`text-sm mb-3 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                {prompt.description}
              </p>
              <div className="flex flex-wrap gap-2">
                <span className={`px-2 py-1 rounded text-xs font-medium ${
                  isDark ? 'bg-slate-800 text-slate-300' : 'bg-slate-100 text-slate-700'
                }`}>
                  {categoryLabels[prompt.category] || prompt.category}
                </span>
                {prompt.status === 'active' ? (
                  <span className={`flex items-center gap-1 px-2 py-1 rounded text-xs font-medium ${
                    isDark ? 'bg-emerald-900/30 text-emerald-400' : 'bg-emerald-100 text-emerald-700'
                  }`}>
                    <CheckCircle2 className="w-3 h-3" />
                    Active
                  </span>
                ) : (
                  <span className={`flex items-center gap-1 px-2 py-1 rounded text-xs font-medium ${
                    isDark ? 'bg-amber-900/30 text-amber-400' : 'bg-amber-100 text-amber-700'
                  }`}>
                    <Clock className="w-3 h-3" />
                    Planned
                  </span>
                )}
              </div>
            </div>

            <button
              onClick={copyToClipboard}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                copied
                  ? isDark
                    ? 'bg-emerald-600 text-white'
                    : 'bg-emerald-600 text-white'
                  : isDark
                    ? 'bg-slate-800 text-slate-300 hover:bg-slate-700'
                    : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
              }`}
            >
              {copied ? (
                <>
                  <Check className="w-4 h-4" />
                  Copied!
                </>
              ) : (
                <>
                  <Copy className="w-4 h-4" />
                  Copy Prompt
                </>
              )}
            </button>
          </div>
        </div>
      </div>

      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="grid lg:grid-cols-3 gap-8">
          {/* Main Content - Prompt */}
          <div className="lg:col-span-2">
            <div className={`rounded-xl border overflow-hidden ${isDark ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200'}`}>
              <div className={`px-4 py-3 border-b flex items-center justify-between ${isDark ? 'bg-slate-800/50 border-slate-700' : 'bg-slate-50 border-slate-200'}`}>
                <span className={`text-sm font-medium ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
                  Prompt Content
                </span>
                <span className={`text-xs ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
                  {prompt.source_file}
                </span>
              </div>
              <pre className={`p-4 text-sm overflow-x-auto max-h-[600px] overflow-y-auto ${
                isDark ? 'text-slate-300' : 'text-slate-800'
              }`}>
                <code className="whitespace-pre-wrap break-words font-mono">
                  {prompt.content}
                </code>
              </pre>
            </div>
          </div>

          {/* Sidebar - Annotations */}
          <div className="lg:col-span-1">
            <div className={`rounded-xl border sticky top-4 ${isDark ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200'}`}>
              <div className={`px-4 py-3 border-b ${isDark ? 'border-slate-800' : 'border-slate-200'}`}>
                <h2 className={`text-sm font-bold ${isDark ? 'text-white' : 'text-slate-900'}`}>
                  Annotations
                </h2>
                <p className={`text-xs mt-1 ${isDark ? 'text-slate-500' : 'text-slate-500'}`}>
                  Human-readable explanations of key sections
                </p>
              </div>

              {prompt.annotations.length === 0 ? (
                <div className={`p-4 text-sm ${isDark ? 'text-slate-500' : 'text-slate-500'}`}>
                  No annotations available for this prompt.
                </div>
              ) : (
                <div className="divide-y divide-slate-800">
                  {prompt.annotations.map((annotation, index) => (
                    <div key={index} className="p-4">
                      <button
                        onClick={() => toggleAnnotation(index)}
                        className="w-full flex items-start gap-2 text-left"
                      >
                        <span className={`mt-0.5 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
                          {expandedAnnotations.has(index) ? (
                            <ChevronDown className="w-4 h-4" />
                          ) : (
                            <ChevronRight className="w-4 h-4" />
                          )}
                        </span>
                        <div className="flex-grow">
                          <h3 className={`text-sm font-semibold ${isDark ? 'text-white' : 'text-slate-900'}`}>
                            {annotation.section}
                          </h3>
                          {annotation.lines && (
                            <span className={`text-xs ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
                              Lines {annotation.lines}
                            </span>
                          )}
                        </div>
                      </button>

                      {expandedAnnotations.has(index) && (
                        <div className={`mt-3 ml-6 p-3 rounded-lg text-sm ${
                          isDark ? 'bg-slate-800 text-slate-300' : 'bg-slate-50 text-slate-700'
                        }`}>
                          <Info className={`w-4 h-4 mb-2 ${isDark ? 'text-emerald-400' : 'text-emerald-600'}`} />
                          {annotation.explanation}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Related Prompts - Could be added later */}
        <div className={`mt-12 pt-8 border-t ${isDark ? 'border-slate-800' : 'border-slate-200'}`}>
          <div className="flex items-center justify-between mb-4">
            <h2 className={`text-lg font-bold ${isDark ? 'text-white' : 'text-slate-900'}`}>
              About This Prompt
            </h2>
          </div>
          <div className={`rounded-xl p-6 ${isDark ? 'bg-slate-900 border border-slate-800' : 'bg-white border border-slate-200'}`}>
            <div className="grid sm:grid-cols-2 gap-6">
              <div>
                <h3 className={`text-xs font-bold uppercase tracking-wider mb-2 ${isDark ? 'text-slate-500' : 'text-slate-500'}`}>
                  Category
                </h3>
                <p className={isDark ? 'text-white' : 'text-slate-900'}>
                  {categoryLabels[prompt.category] || prompt.category}
                </p>
              </div>
              <div>
                <h3 className={`text-xs font-bold uppercase tracking-wider mb-2 ${isDark ? 'text-slate-500' : 'text-slate-500'}`}>
                  Status
                </h3>
                <p className={isDark ? 'text-white' : 'text-slate-900'}>
                  {prompt.status === 'active' ? 'Active - Used in production' : 'Planned - Not yet implemented'}
                </p>
              </div>
              <div className="sm:col-span-2">
                <h3 className={`text-xs font-bold uppercase tracking-wider mb-2 ${isDark ? 'text-slate-500' : 'text-slate-500'}`}>
                  Source File
                </h3>
                <code className={`text-sm ${isDark ? 'text-emerald-400' : 'text-emerald-600'}`}>
                  {prompt.source_file}
                </code>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
