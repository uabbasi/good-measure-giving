import { useState, useMemo } from 'react';
import { AnimatePresence, m } from 'motion/react';
import { Calculator, X } from 'lucide-react';
import { useLandingTheme } from '../../../contexts/LandingThemeContext';
import { calculateZakat, NISAB_USD } from '../../utils/zakatCalculator';
import type { ZakatAssets, ZakatLiabilities } from '../../../types';

interface ZakatEstimatorProps {
  isOpen: boolean;
  onClose: () => void;
  onUseAmount: (amount: number) => void;
  lastYearZakat?: number;
}

function parseAmount(value: string): number {
  return parseInt(value.replace(/\D/g, ''), 10) || 0;
}

function formatUsd(n: number): string {
  return n.toLocaleString('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 });
}

export function ZakatEstimator({ isOpen, onClose, onUseAmount, lastYearZakat }: ZakatEstimatorProps) {
  const { isDark } = useLandingTheme();

  // Asset fields
  const [cash, setCash] = useState('');
  const [stocks, setStocks] = useState('');
  const [gold, setGold] = useState('');
  const [other, setOther] = useState('');

  // Liability fields
  const [debts, setDebts] = useState('');

  const assets: ZakatAssets = useMemo(() => ({
    cash: parseAmount(cash),
    stocks: parseAmount(stocks),
    gold: parseAmount(gold),
    other: parseAmount(other),
  }), [cash, stocks, gold, other]);

  const liabilities: ZakatLiabilities = useMemo(() => ({
    debts: parseAmount(debts),
  }), [debts]);

  const estimate = useMemo(() => calculateZakat(assets, liabilities), [assets, liabilities]);
  const hasInput = estimate.totalAssets > 0 || estimate.totalLiabilities > 0;

  function handleUse(amount: number) {
    onUseAmount(amount);
    onClose();
    resetForm();
  }

  function resetForm() {
    setCash('');
    setStocks('');
    setGold('');
    setOther('');
    setDebts('');
  }

  function handleClose() {
    onClose();
    resetForm();
  }

  const inputClass = `w-full px-3 py-2 rounded-lg border text-base ${
    isDark
      ? 'bg-slate-800 border-slate-600 text-white placeholder-slate-500 focus:border-emerald-500'
      : 'bg-white border-slate-300 text-slate-900 placeholder-slate-400 focus:border-emerald-500'
  } focus:outline-none focus:ring-1 focus:ring-emerald-500`;

  const labelClass = `block text-sm font-medium mb-1 ${isDark ? 'text-slate-300' : 'text-slate-700'}`;

  return (
    <AnimatePresence>
      {isOpen && (
        <m.div
          className="fixed inset-0 z-50 flex items-center justify-center p-4"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2 }}
        >
          {/* Backdrop */}
          <m.div
            className={`absolute inset-0 ${isDark ? 'bg-black/70' : 'bg-black/50'}`}
            onClick={handleClose}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          />
          {/* Panel */}
          <m.div
            className={`relative w-full max-w-md max-h-[90vh] overflow-y-auto rounded-xl border shadow-xl ${
              isDark ? 'bg-slate-900 border-slate-700' : 'bg-white border-slate-200'
            }`}
            initial={{ opacity: 0, scale: 0.95, y: 10 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 10 }}
            transition={{ duration: 0.2 }}
          >
            {/* Header */}
            <div className={`sticky top-0 px-6 py-4 border-b ${isDark ? 'bg-slate-900 border-slate-700' : 'bg-white border-slate-200'}`}>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Calculator className={`w-5 h-5 ${isDark ? 'text-emerald-400' : 'text-emerald-600'}`} />
                  <h2 className={`text-lg font-semibold ${isDark ? 'text-white' : 'text-slate-900'}`}>Zakat Estimator</h2>
                </div>
                <button
                  onClick={handleClose}
                  className={`p-1 rounded-lg ${isDark ? 'hover:bg-slate-800 text-slate-400' : 'hover:bg-slate-100 text-slate-500'}`}
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
            </div>

            {/* Body */}
            <div className="px-6 py-4 space-y-4">
              {/* Disclaimer */}
              <div className={`p-3 rounded-lg text-xs ${isDark ? 'bg-amber-900/30 text-amber-300' : 'bg-amber-50 text-amber-700'}`}>
                Quick estimate only — consult a scholar for complex cases.
              </div>

              {/* Assets */}
              <div>
                <p className={`text-xs font-semibold uppercase tracking-wide mb-3 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                  Assets
                </p>
                <div className="space-y-3">
                  <div>
                    <label className={labelClass}>Cash & savings *</label>
                    <input
                      type="text"
                      inputMode="numeric"
                      value={cash}
                      onChange={e => setCash(e.target.value.replace(/\D/g, ''))}
                      placeholder="0"
                      className={inputClass}
                      autoFocus
                    />
                  </div>
                  <div>
                    <label className={labelClass}>Investments & stocks</label>
                    <input
                      type="text"
                      inputMode="numeric"
                      value={stocks}
                      onChange={e => setStocks(e.target.value.replace(/\D/g, ''))}
                      placeholder="0"
                      className={inputClass}
                    />
                  </div>
                  <div>
                    <label className={labelClass}>Gold & silver (market value)</label>
                    <input
                      type="text"
                      inputMode="numeric"
                      value={gold}
                      onChange={e => setGold(e.target.value.replace(/\D/g, ''))}
                      placeholder="0"
                      className={inputClass}
                    />
                  </div>
                  <div>
                    <label className={labelClass}>Other zakatable assets</label>
                    <input
                      type="text"
                      inputMode="numeric"
                      value={other}
                      onChange={e => setOther(e.target.value.replace(/\D/g, ''))}
                      placeholder="0"
                      className={inputClass}
                    />
                  </div>
                </div>
              </div>

              {/* Liabilities */}
              <div>
                <p className={`text-xs font-semibold uppercase tracking-wide mb-3 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                  Deductions
                </p>
                <div>
                  <label className={labelClass}>Short-term debts</label>
                  <input
                    type="text"
                    inputMode="numeric"
                    value={debts}
                    onChange={e => setDebts(e.target.value.replace(/\D/g, ''))}
                    placeholder="0"
                    className={inputClass}
                  />
                </div>
              </div>

              {/* Result */}
              {hasInput && (
                <m.div
                  initial={{ opacity: 0, y: 4 }}
                  animate={{ opacity: 1, y: 0 }}
                  className={`p-4 rounded-lg border ${
                    estimate.isAboveNisab
                      ? isDark ? 'bg-emerald-900/20 border-emerald-800' : 'bg-emerald-50 border-emerald-200'
                      : isDark ? 'bg-slate-800 border-slate-700' : 'bg-slate-50 border-slate-200'
                  }`}
                >
                  <div className="space-y-2">
                    <div className={`flex justify-between text-sm ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                      <span>Total assets</span>
                      <span className="tabular-nums">{formatUsd(estimate.totalAssets)}</span>
                    </div>
                    {estimate.totalLiabilities > 0 && (
                      <div className={`flex justify-between text-sm ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                        <span>Less debts</span>
                        <span className="tabular-nums">−{formatUsd(estimate.totalLiabilities)}</span>
                      </div>
                    )}
                    <div className={`flex justify-between text-sm pt-1 border-t ${isDark ? 'text-slate-300 border-slate-700' : 'text-slate-600 border-slate-200'}`}>
                      <span>Net zakatable</span>
                      <span className="tabular-nums">{formatUsd(estimate.netZakatable)}</span>
                    </div>

                    {estimate.isAboveNisab ? (
                      <div className={`flex justify-between items-baseline pt-2 border-t ${isDark ? 'border-slate-700' : 'border-slate-200'}`}>
                        <span className={`text-sm font-medium ${isDark ? 'text-emerald-400' : 'text-emerald-700'}`}>Zakat due (2.5%)</span>
                        <span className={`text-xl font-bold tabular-nums ${isDark ? 'text-emerald-400' : 'text-emerald-700'}`}>
                          {formatUsd(estimate.zakatAmount)}
                        </span>
                      </div>
                    ) : (
                      <p className={`text-sm pt-2 border-t ${isDark ? 'text-slate-500 border-slate-700' : 'text-slate-400 border-slate-200'}`}>
                        Below nisab threshold ({formatUsd(NISAB_USD)}). No zakat due.
                      </p>
                    )}
                  </div>
                </m.div>
              )}
            </div>

            {/* Footer */}
            <div className={`sticky bottom-0 px-6 py-4 border-t space-y-2 ${isDark ? 'bg-slate-900 border-slate-700' : 'bg-white border-slate-200'}`}>
              {estimate.isAboveNisab && (
                <button
                  onClick={() => handleUse(estimate.zakatAmount)}
                  className="w-full px-4 py-2.5 rounded-lg font-medium bg-emerald-600 text-white hover:bg-emerald-700 transition-colors"
                >
                  Use this amount ({formatUsd(estimate.zakatAmount)})
                </button>
              )}
              {lastYearZakat != null && lastYearZakat > 0 && (
                <button
                  onClick={() => handleUse(lastYearZakat)}
                  className={`w-full px-4 py-2.5 rounded-lg font-medium transition-colors ${
                    isDark
                      ? 'bg-slate-800 text-slate-300 hover:bg-slate-700'
                      : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                  }`}
                >
                  Use last year's amount ({formatUsd(lastYearZakat)})
                </button>
              )}
              <button
                onClick={handleClose}
                className={`w-full px-4 py-2 text-sm transition-colors ${isDark ? 'text-slate-500 hover:text-slate-400' : 'text-slate-400 hover:text-slate-500'}`}
              >
                Enter my own amount
              </button>
            </div>
          </m.div>
        </m.div>
      )}
    </AnimatePresence>
  );
}
