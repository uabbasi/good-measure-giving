import React, { useEffect, useState } from 'react';
import { useParams, Link, Navigate } from 'react-router-dom';
import { useLandingTheme } from '../contexts/LandingThemeContext';
import type { Guide } from '../scripts/lib/guide-seo';

export const GuidePage: React.FC = () => {
  const { slug } = useParams<{ slug: string }>();
  const { isDark } = useLandingTheme();
  const [guide, setGuide] = useState<Guide | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    if (!slug) return;
    fetch(`/data/guides/${slug}.json`)
      .then((r) => {
        if (!r.ok) {
          setNotFound(true);
          return null;
        }
        return r.json();
      })
      .then((data: Guide | null) => {
        if (data) {
          setGuide(data);
          document.title = data.metaTitle;
        }
      })
      .catch(() => setNotFound(true))
      .finally(() => setLoading(false));

    return () => { document.title = 'Good Measure Giving | Muslim Charity Evaluator'; };
  }, [slug]);

  if (notFound) return <Navigate to="/guides" replace />;

  if (loading || !guide) {
    return (
      <div className={`min-h-screen flex items-center justify-center ${isDark ? 'bg-slate-950' : 'bg-slate-50'}`}>
        <div className={isDark ? 'text-slate-400' : 'text-slate-600'}>Loading guide…</div>
      </div>
    );
  }

  return (
    <article className={`min-h-screen ${isDark ? 'bg-slate-950 text-white' : 'bg-slate-50 text-slate-900'}`}>
      <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <nav aria-label="Breadcrumb" className="mb-6 text-sm text-slate-500">
          <Link to="/" className="hover:underline">Home</Link>
          <span className="mx-2">/</span>
          <Link to="/guides" className="hover:underline">Guides</Link>
          <span className="mx-2">/</span>
          <span>{guide.title}</span>
        </nav>

        <header className="mb-10">
          <h1 className="text-4xl font-semibold mb-3">{guide.title}</h1>
          <div className="text-sm text-slate-500">
            {guide.readingTimeMinutes} min read · Updated {new Date(guide.updatedOn).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })}
          </div>
        </header>

        <div className="mb-10 p-4 rounded-lg bg-slate-100 dark:bg-slate-800/50 border-l-4 border-emerald-500">
          <div className="text-xs uppercase tracking-wide font-semibold text-slate-500 dark:text-slate-400 mb-1">TL;DR</div>
          <p className="text-slate-800 dark:text-slate-200">{guide.tldr}</p>
        </div>

        {guide.sections.map((section, i) => (
          <section key={i} className="mb-10">
            <h2 className="text-2xl font-semibold mb-4">{section.heading}</h2>
            {section.paragraphs.map((p, j) => (
              <p key={j} className="mb-4 leading-relaxed text-slate-700 dark:text-slate-300">{p}</p>
            ))}
          </section>
        ))}

        {guide.callouts && guide.callouts.length > 0 && (
          <div className="mb-10">
            {guide.callouts.map((c, i) => (
              <div key={i} className="p-4 rounded-lg bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 mb-4">
                <div className="text-xs uppercase tracking-wide font-semibold text-amber-700 dark:text-amber-400 mb-1">{c.label}</div>
                <p className="text-amber-900 dark:text-amber-100">{c.text}</p>
              </div>
            ))}
          </div>
        )}

        <section className="mb-10">
          <h2 className="text-2xl font-semibold mb-4">Frequently Asked Questions</h2>
          <dl>
            {guide.faq.map((item, i) => (
              <div key={i} className="mb-6">
                <dt className="font-semibold text-slate-900 dark:text-slate-100">{item.q}</dt>
                <dd className="mt-1 text-slate-700 dark:text-slate-300">{item.a}</dd>
              </div>
            ))}
          </dl>
        </section>

        {guide.relatedCauses && guide.relatedCauses.length > 0 && (
          <section className="mb-10">
            <h2 className="text-2xl font-semibold mb-4">Related Cause Areas</h2>
            <ul className="flex flex-wrap gap-2">
              {guide.relatedCauses.map((slug) => (
                <li key={slug}>
                  <Link to={`/causes/${slug}`} className="inline-block px-3 py-1 text-sm rounded-full border border-slate-300 dark:border-slate-700 hover:border-slate-500">
                    {slug.replace(/-/g, ' ')}
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        )}
      </div>
    </article>
  );
};
