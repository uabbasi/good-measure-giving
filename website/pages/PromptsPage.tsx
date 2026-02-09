import React, { useState, useEffect, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { useLandingTheme } from '../contexts/LandingThemeContext';
import {
  FileCode2,
  Search,
  ShieldCheck,
  Database,
  Sparkles,
  Layers,
  ArrowRight,
  CheckCircle2,
  Clock
} from 'lucide-react';

interface Prompt {
  id: string;
  name: string;
  category: string;
  description: string;
  status: 'active' | 'planned';
}

interface PromptCategory {
  id: string;
  name: string;
  description: string;
}

interface PromptsIndex {
  prompts: Prompt[];
  categories: PromptCategory[];
  total_count: number;
  active_count: number;
  planned_count: number;
}

const categoryIcons: Record<string, typeof ShieldCheck> = {
  quality_validation: ShieldCheck,
  data_extraction: Database,
  narrative_generation: Sparkles,
  category_calibration: Layers,
};

const categoryColors: Record<string, { bg: string; bgDark: string; text: string; textDark: string }> = {
  quality_validation: {
    bg: 'bg-blue-100',
    bgDark: 'bg-blue-900/30',
    text: 'text-blue-700',
    textDark: 'text-blue-400',
  },
  data_extraction: {
    bg: 'bg-purple-100',
    bgDark: 'bg-purple-900/30',
    text: 'text-purple-700',
    textDark: 'text-purple-400',
  },
  narrative_generation: {
    bg: 'bg-emerald-100',
    bgDark: 'bg-emerald-900/30',
    text: 'text-emerald-700',
    textDark: 'text-emerald-400',
  },
  category_calibration: {
    bg: 'bg-amber-100',
    bgDark: 'bg-amber-900/30',
    text: 'text-amber-700',
    textDark: 'text-amber-400',
  },
};

export const PromptsPage: React.FC = () => {
  const { isDark } = useLandingTheme();
  const [data, setData] = useState<PromptsIndex | null>(null);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);

  useEffect(() => {
    document.title = 'AI Transparency | Good Measure Giving';
    return () => { document.title = 'Good Measure Giving | Muslim Charity Evaluator'; };
  }, []);

  useEffect(() => {
    fetch('/data/prompts/index.json')
      .then(res => res.json())
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const filteredPrompts = useMemo(() => {
    if (!data) return [];
    return data.prompts.filter(prompt => {
      const matchesSearch = !searchTerm ||
        prompt.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        prompt.description.toLowerCase().includes(searchTerm.toLowerCase());
      const matchesCategory = !selectedCategory || prompt.category === selectedCategory;
      return matchesSearch && matchesCategory;
    });
  }, [data, searchTerm, selectedCategory]);

  const groupedPrompts = useMemo(() => {
    const groups: Record<string, Prompt[]> = {};
    for (const prompt of filteredPrompts) {
      if (!groups[prompt.category]) {
        groups[prompt.category] = [];
      }
      groups[prompt.category].push(prompt);
    }
    return groups;
  }, [filteredPrompts]);

  if (loading) {
    return (
      <div className={`min-h-screen flex items-center justify-center ${isDark ? 'bg-slate-950' : 'bg-slate-50'}`}>
        <div className={isDark ? 'text-slate-400' : 'text-slate-600'}>Loading prompts...</div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className={`min-h-screen flex items-center justify-center ${isDark ? 'bg-slate-950' : 'bg-slate-50'}`}>
        <div className={isDark ? 'text-slate-400' : 'text-slate-600'}>Failed to load prompts.</div>
      </div>
    );
  }

  return (
    <div className={`min-h-screen transition-colors duration-300 ${isDark ? 'bg-slate-950' : 'bg-slate-50'}`}>
      {/* Hero */}
      <div className={`border-b ${isDark ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200'}`}>
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
          <div className="flex items-center gap-3 mb-4">
            <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${isDark ? 'bg-emerald-900/30' : 'bg-emerald-100'}`}>
              <FileCode2 className={`w-6 h-6 ${isDark ? 'text-emerald-400' : 'text-emerald-600'}`} />
            </div>
            <div>
              <h1 className={`text-3xl font-bold font-merriweather ${isDark ? 'text-white' : 'text-slate-900'}`}>
                Our AI Prompts
              </h1>
              <p className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                Full transparency into how we use AI
              </p>
            </div>
          </div>

          <p className={`text-lg leading-relaxed mb-6 max-w-3xl ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
            We believe in radical transparency. Every prompt we use to evaluate charities is published here.
            You can see exactly what instructions we give to AI models, how we prevent hallucinations,
            and what safeguards ensure accuracy.
          </p>

          {/* Stats */}
          <div className="flex flex-wrap gap-4">
            <div className={`px-4 py-2 rounded-lg ${isDark ? 'bg-slate-800' : 'bg-slate-100'}`}>
              <span className={`font-bold ${isDark ? 'text-white' : 'text-slate-900'}`}>{data.total_count}</span>
              <span className={`ml-2 text-sm ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>Total Prompts</span>
            </div>
            <div className={`px-4 py-2 rounded-lg ${isDark ? 'bg-emerald-900/30' : 'bg-emerald-100'}`}>
              <span className={`font-bold ${isDark ? 'text-emerald-400' : 'text-emerald-700'}`}>{data.active_count}</span>
              <span className={`ml-2 text-sm ${isDark ? 'text-emerald-400/70' : 'text-emerald-600'}`}>Active</span>
            </div>
            <div className={`px-4 py-2 rounded-lg ${isDark ? 'bg-amber-900/30' : 'bg-amber-100'}`}>
              <span className={`font-bold ${isDark ? 'text-amber-400' : 'text-amber-700'}`}>{data.planned_count}</span>
              <span className={`ml-2 text-sm ${isDark ? 'text-amber-400/70' : 'text-amber-600'}`}>Planned</span>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Filters */}
        <div className="flex flex-col sm:flex-row gap-4 mb-8">
          {/* Search */}
          <div className="relative flex-grow">
            <Search className={`absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 ${isDark ? 'text-slate-500' : 'text-slate-400'}`} />
            <input
              type="text"
              placeholder="Search prompts..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className={`w-full pl-10 pr-4 py-2 rounded-lg border ${
                isDark
                  ? 'bg-slate-900 border-slate-700 text-white placeholder-slate-500 focus:border-emerald-500'
                  : 'bg-white border-slate-300 text-slate-900 placeholder-slate-400 focus:border-emerald-500'
              } focus:outline-none focus:ring-1 focus:ring-emerald-500`}
            />
          </div>

          {/* Category Filter */}
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => setSelectedCategory(null)}
              className={`px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                selectedCategory === null
                  ? isDark
                    ? 'bg-emerald-600 text-white'
                    : 'bg-emerald-600 text-white'
                  : isDark
                    ? 'bg-slate-800 text-slate-300 hover:bg-slate-700'
                    : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
              }`}
            >
              All
            </button>
            {data.categories.map(cat => (
              <button
                key={cat.id}
                onClick={() => setSelectedCategory(cat.id)}
                className={`px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                  selectedCategory === cat.id
                    ? isDark
                      ? 'bg-emerald-600 text-white'
                      : 'bg-emerald-600 text-white'
                    : isDark
                      ? 'bg-slate-800 text-slate-300 hover:bg-slate-700'
                      : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                }`}
              >
                {cat.name}
              </button>
            ))}
          </div>
        </div>

        {/* Prompt Groups */}
        {Object.entries(groupedPrompts).map(([categoryId, prompts]) => {
          const category = data.categories.find(c => c.id === categoryId);
          const IconComponent = categoryIcons[categoryId] || FileCode2;
          const colors = categoryColors[categoryId] || categoryColors.quality_validation;

          return (
            <section key={categoryId} className="mb-12">
              <div className="flex items-center gap-3 mb-4">
                <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${isDark ? colors.bgDark : colors.bg}`}>
                  <IconComponent className={`w-5 h-5 ${isDark ? colors.textDark : colors.text}`} />
                </div>
                <div>
                  <h2 className={`text-xl font-bold ${isDark ? 'text-white' : 'text-slate-900'}`}>
                    {category?.name || categoryId}
                  </h2>
                  <p className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                    {category?.description}
                  </p>
                </div>
              </div>

              <div className="grid md:grid-cols-2 gap-4">
                {prompts.map(prompt => (
                  <Link
                    key={prompt.id}
                    to={`/prompts/${prompt.id}`}
                    className={`group block rounded-xl border p-5 transition-all ${
                      isDark
                        ? 'bg-slate-900 border-slate-800 hover:border-slate-700 hover:bg-slate-800/50'
                        : 'bg-white border-slate-200 hover:border-slate-300 hover:shadow-md'
                    }`}
                  >
                    <div className="flex items-start justify-between mb-2">
                      <h3 className={`font-semibold group-hover:text-emerald-500 transition-colors ${isDark ? 'text-white' : 'text-slate-900'}`}>
                        {prompt.name}
                      </h3>
                      <div className="flex items-center gap-1">
                        {prompt.status === 'active' ? (
                          <span className={`flex items-center gap-1 text-xs px-2 py-0.5 rounded-full ${
                            isDark ? 'bg-emerald-900/30 text-emerald-400' : 'bg-emerald-100 text-emerald-700'
                          }`}>
                            <CheckCircle2 className="w-3 h-3" />
                            Active
                          </span>
                        ) : (
                          <span className={`flex items-center gap-1 text-xs px-2 py-0.5 rounded-full ${
                            isDark ? 'bg-amber-900/30 text-amber-400' : 'bg-amber-100 text-amber-700'
                          }`}>
                            <Clock className="w-3 h-3" />
                            Planned
                          </span>
                        )}
                      </div>
                    </div>
                    <p className={`text-sm mb-3 line-clamp-2 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                      {prompt.description}
                    </p>
                    <div className={`flex items-center text-sm font-medium ${isDark ? 'text-emerald-400' : 'text-emerald-600'}`}>
                      View prompt
                      <ArrowRight className="w-4 h-4 ml-1 group-hover:translate-x-1 transition-transform" />
                    </div>
                  </Link>
                ))}
              </div>
            </section>
          );
        })}

        {filteredPrompts.length === 0 && (
          <div className={`text-center py-12 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
            No prompts match your search.
          </div>
        )}

        {/* Back to Methodology CTA */}
        <div className={`mt-12 pt-8 border-t ${isDark ? 'border-slate-800' : 'border-slate-200'}`}>
          <div className={`rounded-xl p-6 ${isDark ? 'bg-slate-900' : 'bg-white border border-slate-200'}`}>
            <h3 className={`text-lg font-bold mb-2 ${isDark ? 'text-white' : 'text-slate-900'}`}>
              Want to understand the full picture?
            </h3>
            <p className={`mb-4 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
              Our prompts are just one part of a comprehensive evaluation system.
              Learn how we score charities across Impact and Alignment.
            </p>
            <Link
              to="/methodology"
              className={`inline-flex items-center px-4 py-2 rounded-lg font-medium transition-colors ${
                isDark
                  ? 'bg-emerald-600 text-white hover:bg-emerald-700'
                  : 'bg-emerald-600 text-white hover:bg-emerald-700'
              }`}
            >
              View Our Methodology
              <ArrowRight className="w-4 h-4 ml-2" />
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
};
