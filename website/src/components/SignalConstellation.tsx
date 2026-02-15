import React from 'react';
import { AlertTriangle, Heart, Landmark, ShieldCheck } from 'lucide-react';
import type { UISignalsV1 } from '../../types';

interface SignalConstellationProps {
  signals: UISignalsV1['signal_states'];
  isDark: boolean;
  compact?: boolean;
  showLabels?: boolean;
}

const stateClasses = (state: string, isDark: boolean): string => {
  if (state === 'Strong') return isDark ? 'text-emerald-300 bg-emerald-900/30 border-emerald-800/50' : 'text-emerald-700 bg-emerald-50 border-emerald-200';
  if (state === 'Moderate') return isDark ? 'text-amber-300 bg-amber-900/30 border-amber-800/50' : 'text-amber-700 bg-amber-50 border-amber-200';
  return isDark ? 'text-slate-300 bg-slate-800 border-slate-700' : 'text-slate-600 bg-slate-100 border-slate-200';
};

const labelByKey: Record<keyof UISignalsV1['signal_states'], string> = {
  evidence: 'Evidence',
  financial_health: 'Financial',
  donor_fit: 'Donor Fit',
  risk: 'Risk',
};

const iconByKey: Record<keyof UISignalsV1['signal_states'], React.ElementType> = {
  evidence: ShieldCheck,
  financial_health: Landmark,
  donor_fit: Heart,
  risk: AlertTriangle,
};

export const SignalConstellation: React.FC<SignalConstellationProps> = ({
  signals,
  isDark,
  compact = false,
  showLabels = true,
}) => {
  return (
    <div className={`flex items-center ${compact ? 'gap-1.5' : 'gap-2'} flex-wrap`}>
      {(Object.keys(signals) as Array<keyof UISignalsV1['signal_states']>).map((key) => {
        const Icon = iconByKey[key];
        const label = labelByKey[key];
        const state = signals[key];
        return (
          <span
            key={key}
            title={`${label}: ${state}`}
            className={`inline-flex items-center border rounded ${compact ? 'px-1.5 py-1 text-[10px]' : 'px-2 py-1 text-xs'} ${stateClasses(state, isDark)}`}
          >
            <Icon className={`${compact ? 'w-3 h-3' : 'w-3.5 h-3.5'}`} aria-hidden="true" />
            {showLabels && (
              <span className={`${compact ? 'ml-1' : 'ml-1.5'} whitespace-nowrap`}>
                {compact ? label.split(' ')[0] : label}
              </span>
            )}
          </span>
        );
      })}
    </div>
  );
};

export default SignalConstellation;
