import React from 'react';
import { Link } from 'react-router-dom';
import { useCharities } from '../hooks/useCharities';
import {
  selectSimilarCharities,
  classifyZakatStatus,
  type SimilarCharityCandidate,
  type ZakatStatus,
} from '../../scripts/lib/charity-seo';

interface SimilarCharitiesProps {
  currentEin: string;
  category: string;
  zakatStatus: ZakatStatus;
  limit?: number;
}

export const SimilarCharities: React.FC<SimilarCharitiesProps> = ({
  currentEin,
  category,
  zakatStatus,
  limit = 4,
}) => {
  const { summaries, loading } = useCharities();

  if (loading || !summaries || summaries.length === 0) return null;

  const pool: SimilarCharityCandidate[] = summaries.map((c) => ({
    ein: c.ein,
    name: c.name,
    category: c.primaryCategory ?? c.category ?? '',
    amalScore: c.amalScore ?? null,
    zakatStatus: classifyZakatStatus({
      walletTag: c.walletTag ?? null,
      zakatClassification: c.zakatClassification ?? null,
    }),
  }));

  const similar = selectSimilarCharities({
    currentEin,
    category,
    zakatStatus,
    pool,
    limit,
  });

  if (similar.length === 0) return null;

  const statusLabel = (s: ZakatStatus): string => {
    if (s === 'ZAKAT_ELIGIBLE') return 'Zakat Eligible';
    if (s === 'SADAQAH_ONLY') return 'Sadaqah-Eligible';
    if (s === 'NEW_ORG') return 'Early-Stage';
    return 'Under Review';
  };

  return (
    <section aria-labelledby="similar-charities-heading" className="mt-12">
      <h2
        id="similar-charities-heading"
        className="text-2xl font-semibold mb-4 text-slate-900 dark:text-slate-100"
      >
        Similar Charities
      </h2>
      <ul className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {similar.map((c) => (
          <li key={c.ein}>
            <Link
              to={`/charity/${c.ein}`}
              className="block p-4 rounded-lg border border-slate-200 dark:border-slate-700 hover:border-slate-400 dark:hover:border-slate-500 transition-colors"
            >
              <div className="font-medium text-slate-900 dark:text-slate-100">{c.name}</div>
              {c.amalScore != null && (
                <div className="text-sm text-slate-600 dark:text-slate-400 mt-1">
                  {c.amalScore}/100 · {statusLabel(c.zakatStatus)}
                </div>
              )}
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
};
