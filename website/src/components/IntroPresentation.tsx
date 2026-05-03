/**
 * IntroPresentation — Auto-advancing first-visit intro.
 *
 * Six slides (~38s total) that explain what Good Measure Giving is and why it matters,
 * rendered as screenshot-style mocks of the actual product. Skip button at the bottom.
 * Shown once per browser; uses localStorage `gmg_intro_seen_v1`.
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AnimatePresence, m } from 'motion/react';
import {
  Scale, Search, Shield, Heart, ArrowRight, X,
  CheckCircle2, Star, Sparkles, ChevronRight,
} from 'lucide-react';

const STORAGE_KEY = 'gmg_intro_seen_v1';

type Slide = {
  duration: number; // ms
  render: () => React.ReactNode;
};

// ─────────────────────────────────────────────────────────────────────────────
// Slide content — each is a screenshot-like vignette
// ─────────────────────────────────────────────────────────────────────────────

const SlideHook: React.FC = () => (
  <div className="relative w-full h-full flex items-center justify-center overflow-hidden">
    {/* radial gradient bg */}
    <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,rgba(16,185,129,0.18),transparent_60%)]" />
    <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_70%_20%,rgba(56,189,248,0.10),transparent_50%)]" />

    <m.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.7 }}
      className="relative z-10 text-center px-8 max-w-3xl"
    >
      <m.div
        initial={{ opacity: 0, scale: 0.8 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.6, delay: 0.2 }}
        className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-white/5 border border-white/10 text-emerald-300 text-xs font-medium tracking-wider uppercase mb-8"
      >
        <Scale className="w-3.5 h-3.5" />
        Good Measure Giving
      </m.div>
      <h1 className="text-4xl sm:text-5xl md:text-6xl font-bold font-merriweather text-white tracking-tight leading-[1.05] [text-wrap:balance]">
        Where does your{' '}
        <span className="bg-gradient-to-r from-emerald-300 to-teal-200 bg-clip-text text-transparent">
          charity dollar
        </span>{' '}
        actually go?
      </h1>
      <m.p
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.6, delay: 0.9 }}
        className="mt-6 text-lg text-slate-300/80 max-w-xl mx-auto"
      >
        Most donors give blind. We did the research so you don't have to.
      </m.p>
    </m.div>
  </div>
);

const SlideProblem: React.FC = () => {
  const stats = [
    { num: '$500B+', label: 'given to charity each year', delay: 0.2 },
    { num: '<5%', label: 'of donors check where it goes', delay: 0.7 },
    { num: '170+', label: 'charities we evaluated for you', delay: 1.2 },
  ];
  return (
    <div className="relative w-full h-full flex items-center justify-center overflow-hidden">
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_30%_60%,rgba(244,114,182,0.10),transparent_55%)]" />
      <div className="relative z-10 px-8 max-w-4xl w-full">
        <m.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="text-center mb-10"
        >
          <h2 className="text-3xl sm:text-4xl font-bold font-merriweather text-white tracking-tight">
            The giving gap
          </h2>
          <p className="mt-2 text-slate-400 text-base">
            Generosity is high. Visibility is low.
          </p>
        </m.div>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {stats.map((s) => (
            <m.div
              key={s.label}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: s.delay }}
              className="rounded-2xl bg-white/5 backdrop-blur-sm border border-white/10 p-6 text-center"
            >
              <div className="text-3xl sm:text-4xl font-bold font-merriweather bg-gradient-to-b from-white to-slate-300 bg-clip-text text-transparent">
                {s.num}
              </div>
              <div className="mt-2 text-sm text-slate-400 leading-snug">
                {s.label}
              </div>
            </m.div>
          ))}
        </div>
      </div>
    </div>
  );
};

const SlideBrowse: React.FC = () => {
  const charities = [
    { name: 'Helping Hand for Relief', cause: 'Emergency Relief', score: 92, badge: 'Accepts Zakat', accent: 'emerald' as const },
    { name: 'Islamic Relief USA', cause: 'Global Development', score: 88, badge: 'Accepts Zakat', accent: 'emerald' as const },
    { name: 'Penny Appeal USA', cause: 'Orphan Sponsorship', score: 84, badge: 'Sadaqah Route', accent: 'sky' as const },
  ];
  return (
    <div className="relative w-full h-full flex items-center justify-center overflow-hidden">
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_50%_50%,rgba(16,185,129,0.10),transparent_60%)]" />
      <div className="relative z-10 px-6 max-w-5xl w-full">
        <m.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="text-center mb-6"
        >
          <h2 className="text-2xl sm:text-3xl font-bold font-merriweather text-white tracking-tight">
            Independent research on 170+ charities
          </h2>
          <p className="mt-1.5 text-sm text-slate-400">
            Financials, impact evidence, governance — all in one place.
          </p>
        </m.div>

        {/* Mock browser frame */}
        <m.div
          initial={{ opacity: 0, scale: 0.97, y: 12 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          transition={{ duration: 0.55, delay: 0.25 }}
          className="rounded-2xl bg-slate-900/80 backdrop-blur-md border border-white/10 shadow-2xl overflow-hidden"
        >
          {/* Browser chrome */}
          <div className="flex items-center gap-2 px-4 py-3 border-b border-white/5 bg-slate-950/50">
            <div className="flex gap-1.5">
              <div className="w-2.5 h-2.5 rounded-full bg-rose-400/60" />
              <div className="w-2.5 h-2.5 rounded-full bg-amber-400/60" />
              <div className="w-2.5 h-2.5 rounded-full bg-emerald-400/60" />
            </div>
            <div className="ml-3 flex-1 flex items-center gap-2 px-3 py-1 rounded-md bg-white/5 text-[11px] text-slate-400">
              <Search className="w-3 h-3" />
              goodmeasuregiving.com/browse
            </div>
          </div>
          {/* Cards grid */}
          <div className="p-5 grid grid-cols-1 md:grid-cols-3 gap-3">
            {charities.map((c, i) => (
              <m.div
                key={c.name}
                initial={{ opacity: 0, y: 14 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5, delay: 0.5 + i * 0.18 }}
                className="rounded-xl bg-slate-800/60 border border-white/5 p-4"
              >
                <div className="flex items-start justify-between gap-2 mb-3">
                  <div className="text-[13px] font-semibold text-white leading-snug line-clamp-2">
                    {c.name}
                  </div>
                  <div className="flex items-center justify-center w-10 h-10 rounded-full bg-emerald-500/15 border border-emerald-400/30 text-emerald-300 text-sm font-bold flex-shrink-0">
                    {c.score}
                  </div>
                </div>
                <div className="text-[11px] text-slate-400 mb-3">{c.cause}</div>
                <div className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium ${
                  c.accent === 'emerald'
                    ? 'bg-emerald-500/10 text-emerald-300 border border-emerald-400/20'
                    : 'bg-sky-500/10 text-sky-300 border border-sky-400/20'
                }`}>
                  <CheckCircle2 className="w-2.5 h-2.5" />
                  {c.badge}
                </div>
              </m.div>
            ))}
          </div>
        </m.div>
      </div>
    </div>
  );
};

const SlideScore: React.FC = () => {
  const dimensions = [
    { label: 'Financial Health', score: 9.2, color: 'emerald' },
    { label: 'Impact Evidence', score: 8.5, color: 'emerald' },
    { label: 'Transparency', score: 9.0, color: 'emerald' },
    { label: 'Governance', score: 7.8, color: 'amber' },
  ];
  return (
    <div className="relative w-full h-full flex items-center justify-center overflow-hidden">
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_50%_50%,rgba(56,189,248,0.10),transparent_60%)]" />
      <div className="relative z-10 px-6 max-w-4xl w-full">
        <m.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="text-center mb-6"
        >
          <h2 className="text-2xl sm:text-3xl font-bold font-merriweather text-white tracking-tight">
            Every score, fully broken down
          </h2>
          <p className="mt-1.5 text-sm text-slate-400">
            See exactly why a charity scored what it did. No black box.
          </p>
        </m.div>

        <m.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.55, delay: 0.2 }}
          className="rounded-2xl bg-slate-900/80 backdrop-blur-md border border-white/10 shadow-2xl overflow-hidden"
        >
          <div className="px-6 py-5 border-b border-white/5 flex items-center justify-between">
            <div>
              <div className="text-[11px] text-slate-500 tracking-wider uppercase">Overall Score</div>
              <div className="text-xl font-bold text-white mt-0.5">Helping Hand for Relief</div>
            </div>
            <m.div
              initial={{ scale: 0.6, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ duration: 0.5, delay: 0.5, type: 'spring' }}
              className="flex items-center gap-2 px-4 py-2 rounded-full bg-emerald-500/15 border border-emerald-400/30"
            >
              <Star className="w-4 h-4 text-emerald-300 fill-emerald-300" />
              <span className="text-2xl font-bold text-emerald-300">9.2</span>
              <span className="text-xs text-emerald-300/60">/ 10</span>
            </m.div>
          </div>
          <div className="p-6 space-y-3.5">
            {dimensions.map((d, i) => (
              <m.div
                key={d.label}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.4, delay: 0.7 + i * 0.15 }}
              >
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-sm text-slate-300">{d.label}</span>
                  <span className="text-sm font-semibold text-white tabular-nums">{d.score}</span>
                </div>
                <div className="h-1.5 rounded-full bg-white/5 overflow-hidden">
                  <m.div
                    initial={{ width: 0 }}
                    animate={{ width: `${d.score * 10}%` }}
                    transition={{ duration: 0.9, delay: 0.85 + i * 0.15, ease: 'easeOut' }}
                    className={`h-full rounded-full ${
                      d.color === 'emerald'
                        ? 'bg-gradient-to-r from-emerald-500 to-emerald-300'
                        : 'bg-gradient-to-r from-amber-500 to-amber-300'
                    }`}
                  />
                </div>
              </m.div>
            ))}
          </div>
        </m.div>
      </div>
    </div>
  );
};

const SlideZakat: React.FC = () => (
  <div className="relative w-full h-full flex items-center justify-center overflow-hidden">
    <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_30%_40%,rgba(16,185,129,0.12),transparent_55%)]" />
    <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_75%_70%,rgba(168,85,247,0.08),transparent_55%)]" />
    <div className="relative z-10 px-6 max-w-3xl w-full">
      <m.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="text-center mb-8"
      >
        <h2 className="text-2xl sm:text-3xl font-bold font-merriweather text-white tracking-tight">
          Zakat-aware, by design
        </h2>
        <p className="mt-1.5 text-sm text-slate-400">
          Filter by zakat eligibility, fiqh preference, and program type.
        </p>
      </m.div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <m.div
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.55, delay: 0.3 }}
          className="rounded-2xl bg-emerald-500/10 border border-emerald-400/30 p-5 backdrop-blur-md"
        >
          <div className="flex items-center gap-2 mb-2">
            <CheckCircle2 className="w-5 h-5 text-emerald-300" />
            <span className="text-sm font-semibold text-emerald-200 tracking-wide">Accepts Zakat</span>
          </div>
          <div className="text-[13px] text-slate-300 leading-relaxed">
            Programs that channel funds to the eight Quranic categories of recipients.
          </div>
        </m.div>
        <m.div
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.55, delay: 0.5 }}
          className="rounded-2xl bg-sky-500/10 border border-sky-400/30 p-5 backdrop-blur-md"
        >
          <div className="flex items-center gap-2 mb-2">
            <Sparkles className="w-5 h-5 text-sky-300" />
            <span className="text-sm font-semibold text-sky-200 tracking-wide">Sadaqah Route</span>
          </div>
          <div className="text-[13px] text-slate-300 leading-relaxed">
            High-impact giving for general charity, beyond the eight zakat categories.
          </div>
        </m.div>
      </div>

      <m.div
        initial={{ opacity: 0, y: 14 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.85 }}
        className="mt-5 rounded-2xl bg-white/5 border border-white/10 p-5 backdrop-blur-md flex items-start gap-3"
      >
        <Shield className="w-5 h-5 text-slate-300 flex-shrink-0 mt-0.5" />
        <div className="text-[13px] text-slate-300 leading-relaxed">
          Built with Islamic jurisprudence in mind — every wallet decision is documented, sourced, and reviewable.
        </div>
      </m.div>
    </div>
  </div>
);

const SlideCTA: React.FC<{ onStart: () => void }> = ({ onStart }) => (
  <div className="relative w-full h-full flex items-center justify-center overflow-hidden">
    <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,rgba(16,185,129,0.18),transparent_60%)]" />
    <m.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6 }}
      className="relative z-10 text-center px-8 max-w-2xl"
    >
      <m.div
        initial={{ scale: 0.7, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ duration: 0.6, delay: 0.15, type: 'spring' }}
        className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-emerald-500/15 border border-emerald-400/30 mb-6"
      >
        <Heart className="w-7 h-7 text-emerald-300" />
      </m.div>
      <h2 className="text-3xl sm:text-5xl font-bold font-merriweather text-white tracking-tight leading-[1.1] [text-wrap:balance]">
        Give with{' '}
        <span className="bg-gradient-to-r from-emerald-300 to-teal-200 bg-clip-text text-transparent">
          confidence.
        </span>
      </h2>
      <p className="mt-5 text-base sm:text-lg text-slate-300/80 max-w-md mx-auto">
        Real research. Honest scores. Better outcomes for the people you're trying to help.
      </p>
      <m.button
        onClick={onStart}
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.6 }}
        whileHover={{ scale: 1.03 }}
        whileTap={{ scale: 0.98 }}
        className="mt-8 inline-flex items-center gap-2 px-7 py-3.5 rounded-full bg-gradient-to-r from-emerald-500 to-emerald-400 text-slate-950 font-bold text-base shadow-2xl shadow-emerald-500/20"
      >
        <Search className="w-5 h-5" />
        Browse Charities
        <ArrowRight className="w-4 h-4" />
      </m.button>
    </m.div>
  </div>
);

// ─────────────────────────────────────────────────────────────────────────────
// Component
// ─────────────────────────────────────────────────────────────────────────────

const SLIDES: Slide[] = [
  { duration: 5500, render: () => <SlideHook /> },
  { duration: 7000, render: () => <SlideProblem /> },
  { duration: 7500, render: () => <SlideBrowse /> },
  { duration: 8000, render: () => <SlideScore /> },
  { duration: 7000, render: () => <SlideZakat /> },
  // CTA holds until user acts; not auto-advanced
];

export const IntroPresentation: React.FC = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [index, setIndex] = useState(0);
  const [paused, setPaused] = useState(false);
  const navigate = useNavigate();
  const startTimeRef = useRef<number>(0);
  const elapsedRef = useRef<number>(0);

  // First-visit detection
  useEffect(() => {
    let shouldShow = false;
    try {
      shouldShow = !localStorage.getItem(STORAGE_KEY);
    } catch {
      shouldShow = false; // fail closed if storage is blocked
    }
    if (!shouldShow) return;
    // small delay so the landing page paints first
    const t = window.setTimeout(() => setIsOpen(true), 350);
    return () => window.clearTimeout(t);
  }, []);

  const dismiss = useCallback(() => {
    setIsOpen(false);
    try {
      localStorage.setItem(STORAGE_KEY, '1');
    } catch {
      // ignore
    }
  }, []);

  const goNext = useCallback(() => {
    setIndex((i) => Math.min(i + 1, SLIDES.length));
  }, []);

  const startBrowsing = useCallback(() => {
    dismiss();
    navigate('/browse');
  }, [dismiss, navigate]);

  // Reset elapsed time when the active slide changes — must run before the
  // auto-advance effect below so the new slide gets its full duration.
  useEffect(() => {
    elapsedRef.current = 0;
  }, [index]);

  // Auto-advance timer (preserves elapsed across pause/resume on the same slide)
  useEffect(() => {
    if (!isOpen) return;
    if (index >= SLIDES.length) return; // CTA slide: no auto-advance
    if (paused) return;

    const duration = SLIDES[index].duration;
    const remaining = Math.max(0, duration - elapsedRef.current);
    startTimeRef.current = performance.now() - elapsedRef.current;
    const t = window.setTimeout(() => {
      goNext();
    }, remaining);
    return () => {
      window.clearTimeout(t);
      elapsedRef.current = performance.now() - startTimeRef.current;
    };
  }, [isOpen, index, paused, goNext]);

  // Keyboard
  useEffect(() => {
    if (!isOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        dismiss();
      } else if (e.key === 'ArrowRight' || e.key === ' ') {
        e.preventDefault();
        if (index >= SLIDES.length) {
          startBrowsing();
        } else {
          elapsedRef.current = 0;
          goNext();
        }
      } else if (e.key === 'ArrowLeft') {
        e.preventDefault();
        setIndex((i) => Math.max(0, i - 1));
        elapsedRef.current = 0;
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [isOpen, index, dismiss, goNext, startBrowsing]);

  // Lock body scroll while open
  useEffect(() => {
    if (!isOpen) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => { document.body.style.overflow = prev; };
  }, [isOpen]);

  if (!isOpen) return null;

  const isCTA = index >= SLIDES.length;
  const totalSlides = SLIDES.length + 1; // +1 for CTA
  const currentSlide = isCTA ? null : SLIDES[index];

  return (
    <div
      className="fixed inset-0 z-[100] bg-slate-950 text-white"
      role="dialog"
      aria-modal="true"
      aria-label="Introduction to Good Measure Giving"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
    >
      {/* Subtle ambient noise / grain via SVG */}
      <div className="pointer-events-none absolute inset-0 opacity-[0.04] mix-blend-overlay"
        style={{
          backgroundImage:
            'url("data:image/svg+xml;utf8,<svg xmlns=\'http://www.w3.org/2000/svg\' width=\'120\' height=\'120\'><filter id=\'n\'><feTurbulence baseFrequency=\'0.9\' numOctaves=\'2\' stitchTiles=\'stitch\'/></filter><rect width=\'100%25\' height=\'100%25\' filter=\'url(%23n)\'/></svg>")',
        }}
      />

      {/* Top bar: progress segments + close */}
      <div className="absolute top-0 inset-x-0 z-20 px-4 sm:px-6 pt-4 flex items-center gap-3">
        <div className="flex-1 flex gap-1.5">
          {Array.from({ length: totalSlides }).map((_, i) => {
            const active = i === index;
            const completed = i < index;
            return (
              <div key={i} className="flex-1 h-1 rounded-full bg-white/10 overflow-hidden">
                {completed && <div className="h-full bg-white/60 w-full" />}
                {active && !isCTA && (
                  <m.div
                    key={`p-${i}-${index}`}
                    className="h-full bg-white/80"
                    initial={{ width: '0%' }}
                    animate={{ width: paused ? undefined : '100%' }}
                    transition={{ duration: (currentSlide?.duration ?? 0) / 1000, ease: 'linear' }}
                  />
                )}
                {active && isCTA && <div className="h-full bg-white/80 w-full" />}
              </div>
            );
          })}
        </div>
        <button
          onClick={dismiss}
          aria-label="Close intro"
          className="p-1.5 rounded-full text-slate-400 hover:text-white hover:bg-white/10 transition-colors"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Slide stage */}
      <div className="absolute inset-0 flex items-center justify-center">
        <AnimatePresence mode="wait">
          <m.div
            key={index}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.4 }}
            className="absolute inset-0"
          >
            {isCTA ? <SlideCTA onStart={startBrowsing} /> : currentSlide?.render()}
          </m.div>
        </AnimatePresence>
      </div>

      {/* Click-to-advance regions (don't catch the bottom buttons) */}
      <button
        type="button"
        aria-label="Previous slide"
        onClick={() => { setIndex((i) => Math.max(0, i - 1)); elapsedRef.current = 0; }}
        className="absolute left-0 top-16 bottom-24 w-1/3 z-10 cursor-default focus:outline-none"
      />
      <button
        type="button"
        aria-label="Next slide"
        onClick={() => {
          if (isCTA) startBrowsing();
          else { elapsedRef.current = 0; goNext(); }
        }}
        className="absolute right-0 top-16 bottom-24 w-1/3 z-10 cursor-default focus:outline-none"
      />

      {/* Bottom bar: skip intro */}
      <div className="absolute bottom-0 inset-x-0 z-20 pb-6 sm:pb-8 px-4 flex flex-col items-center gap-3">
        {!isCTA && (
          <div className="text-[11px] text-slate-500 tracking-wider uppercase hidden sm:block">
            {index + 1} of {totalSlides}
          </div>
        )}
        <button
          onClick={dismiss}
          className="group inline-flex items-center gap-1.5 px-4 py-2 rounded-full text-sm text-slate-400 hover:text-white border border-white/10 hover:border-white/30 hover:bg-white/5 transition-all"
        >
          Skip intro
          <ChevronRight className="w-3.5 h-3.5 transition-transform group-hover:translate-x-0.5" />
        </button>
      </div>
    </div>
  );
};
