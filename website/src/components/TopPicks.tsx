import { useMemo } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';
import { m } from 'motion/react';
import { useLandingTheme } from '../../contexts/LandingThemeContext';
import { getTopPicks, type TopPickGroup } from '../utils/topPicks';
import { BookmarkButton } from './BookmarkButton';
import type { CharitySummary } from '../hooks/useCharities';

interface TopPicksProps {
  charities: CharitySummary[];
  bookmarkedEins?: Set<string>;
}

function formatScore(score: number | null): string {
  return score != null ? String(Math.round(score)) : '—';
}

function walletLabel(tag: string): string {
  if (tag === 'ZAKAT-ELIGIBLE') return 'Zakat';
  if (tag === 'SADAQAH-STRATEGIC') return 'Sadaqah';
  return 'Sadaqah';
}

function walletColor(tag: string, isDark: boolean): string {
  if (tag === 'ZAKAT-ELIGIBLE') return isDark ? 'bg-emerald-900/40 text-emerald-400' : 'bg-emerald-50 text-emerald-700';
  return isDark ? 'bg-slate-700 text-slate-400' : 'bg-slate-100 text-slate-600';
}

export function TopPicks({ charities, bookmarkedEins }: TopPicksProps) {
  const { isDark } = useLandingTheme();

  const groups = useMemo(() =>
    getTopPicks(charities, { perCategory: 2, maxCategories: 4, excludeEins: bookmarkedEins }),
    [charities, bookmarkedEins]
  );

  if (groups.length === 0) return null;

  return (
    <section className="mb-6">
      <div className="mb-4">
        <h2 className={`text-lg font-semibold ${isDark ? 'text-white' : 'text-slate-900'}`}>
          Top Picks by Cause
        </h2>
        <p className={`text-sm mt-0.5 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
          Highest-scoring charities across cause areas
        </p>
      </div>

      <div className="space-y-4">
        {groups.map((group, gi) => (
          <GroupSection key={group.category} group={group} isDark={isDark} delay={gi * 0.08} />
        ))}
      </div>
    </section>
  );
}

function GroupSection({ group, isDark, delay }: { group: TopPickGroup; isDark: boolean; delay: number }) {
  return (
    <m.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25, delay }}
    >
      <p className={`text-xs font-semibold uppercase tracking-wide mb-2 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
        {group.label}
      </p>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        {group.picks.map(c => (
          <PickCard key={c.ein} charity={c} isDark={isDark} />
        ))}
      </div>
    </m.div>
  );
}

function PickCard({ charity, isDark }: { charity: CharitySummary; isDark: boolean }) {
  const href = `/charity/${charity.ein.replace(/^(\d{2})(\d+)$/, '$1-$2')}`;

  return (
    <div className={`flex items-center gap-3 px-3 py-2.5 rounded-lg border transition-colors ${
      isDark
        ? 'bg-slate-800/50 border-slate-700 hover:bg-slate-800'
        : 'bg-white border-slate-200 hover:bg-slate-50'
    }`}>
      {/* Score pill */}
      <div className={`flex-shrink-0 w-9 h-9 rounded-lg flex items-center justify-center text-sm font-bold ${
        isDark ? 'bg-emerald-900/40 text-emerald-400' : 'bg-emerald-50 text-emerald-700'
      }`}>
        {formatScore(charity.amalScore)}
      </div>

      {/* Name + badges */}
      <div className="flex-1 min-w-0">
        <Link to={href} className={`text-sm font-medium hover:underline block truncate ${isDark ? 'text-slate-200' : 'text-slate-800'}`}>
          {charity.name}
        </Link>
        <div className="flex items-center gap-1.5 mt-0.5">
          <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded ${walletColor(charity.walletTag, isDark)}`}>
            {walletLabel(charity.walletTag)}
          </span>
          {charity.slug && (
            <span className={`text-[11px] truncate ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
              {charity.slug}
            </span>
          )}
        </div>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-1 flex-shrink-0">
        <BookmarkButton charityEin={charity.ein} size="sm" />
        <Link
          to={href}
          className={`p-1.5 rounded-lg transition-colors ${isDark ? 'text-slate-500 hover:text-emerald-400' : 'text-slate-400 hover:text-emerald-600'}`}
        >
          <ArrowRight className="w-4 h-4" />
        </Link>
      </div>
    </div>
  );
}
