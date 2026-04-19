import { useMemo } from 'react';
import { Link } from 'react-router-dom';
import { ArrowUpRight } from 'lucide-react';
import { m } from 'motion/react';
import { useLandingTheme } from '../../contexts/LandingThemeContext';
import { getTopPicks, type TopPickGroup } from '../utils/topPicks';
import { BookmarkButton } from './BookmarkButton';
import type { CharitySummary } from '../hooks/useCharities';

interface TopPicksProps {
  charities: CharitySummary[];
  bookmarkedEins?: Set<string>;
}

function walletLabel(tag: string): string {
  if (tag === 'ZAKAT-ELIGIBLE') return 'Zakat';
  if (tag === 'SADAQAH-STRATEGIC') return 'Sadaqah';
  return 'Sadaqah';
}

function walletColor(tag: string, isDark: boolean): string {
  if (tag === 'ZAKAT-ELIGIBLE') return isDark ? 'bg-emerald-900/40 text-emerald-300' : 'bg-emerald-50 text-emerald-700';
  return isDark ? 'bg-slate-700/60 text-slate-300' : 'bg-slate-100 text-slate-600';
}

export function TopPicks({ charities, bookmarkedEins }: TopPicksProps) {
  const { isDark } = useLandingTheme();

  const groups = useMemo(() =>
    getTopPicks(charities, { perCategory: 1, maxCategories: 8, excludeEins: bookmarkedEins }),
    [charities, bookmarkedEins]
  );

  if (groups.length === 0) return null;

  return (
    <section className="mb-6">
      <div className="mb-3">
        <h2 className={`text-lg sm:text-xl font-bold font-merriweather ${isDark ? 'text-white' : 'text-slate-900'}`}>
          Top picks by cause
        </h2>
        <p className={`text-xs mt-0.5 ${isDark ? 'text-slate-500' : 'text-slate-500'}`}>
          Highest-scoring charity in each cause area
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-2 sm:gap-3">
        {groups.map((group, gi) => (
          <PickTile key={group.category} group={group} isDark={isDark} delay={gi * 0.03} />
        ))}
      </div>
    </section>
  );
}

function PickTile({ group, isDark, delay }: { group: TopPickGroup; isDark: boolean; delay: number }) {
  const charity = group.picks[0];
  if (!charity) return null;
  const href = `/charity/${charity.ein.replace(/^(\d{2})(\d+)$/, '$1-$2')}`;

  return (
    <m.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2, delay }}
      className="h-full"
    >
      <Link
        to={href}
        className={`group relative h-full flex flex-col rounded-lg border px-3 py-2.5 transition-all ${
          isDark
            ? 'bg-slate-900/60 border-slate-800 hover:border-emerald-700/50 hover:bg-slate-900'
            : 'bg-white border-slate-200 hover:border-emerald-300 hover:shadow-sm'
        }`}
      >
        {/* Header: cause label + bookmark */}
        <div className="flex items-start justify-between gap-2 mb-1">
          <span className={`text-[11px] font-medium truncate ${isDark ? 'text-emerald-400/90' : 'text-emerald-700'}`}>
            {group.label.toLowerCase()}
          </span>
          <div
            className="flex-shrink-0 -mr-1.5 -mt-0.5"
            onClick={(e) => e.stopPropagation()}
            onMouseDown={(e) => e.stopPropagation()}
          >
            <BookmarkButton charityEin={charity.ein} size="sm" />
          </div>
        </div>

        {/* Charity name — primary content */}
        <h3 className={`text-[15px] font-bold font-merriweather leading-snug line-clamp-2 ${isDark ? 'text-white' : 'text-slate-900'}`}>
          {charity.name}
        </h3>

        {/* Footer: slug + wallet tag + arrow */}
        <div className="mt-2 flex items-center justify-between gap-2">
          <div className="flex items-center gap-1.5 min-w-0">
            <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded flex-shrink-0 ${walletColor(charity.walletTag, isDark)}`}>
              {walletLabel(charity.walletTag)}
            </span>
            {charity.slug && (
              <span className={`text-[11px] truncate ${isDark ? 'text-slate-500' : 'text-slate-500'}`}>
                {charity.slug}
              </span>
            )}
          </div>
          <ArrowUpRight
            className={`w-3.5 h-3.5 flex-shrink-0 transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5 ${
              isDark ? 'text-slate-600 group-hover:text-emerald-400' : 'text-slate-400 group-hover:text-emerald-600'
            }`}
          />
        </div>
      </Link>
    </m.div>
  );
}
