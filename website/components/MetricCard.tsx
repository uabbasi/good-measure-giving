import React from 'react';
import { DimensionEvaluation, RatingColor } from '../types';
import { CheckCircle, AlertTriangle, XCircle, HelpCircle, Minus } from 'lucide-react';

interface AssessmentCardProps {
  title: string;
  evaluation?: DimensionEvaluation;
  ratingColor?: RatingColor; // Allow direct color passing if no full evaluation object
  rawMetric?: string; // e.g., "82%" or "$1.2M"
}

export const AssessmentCard: React.FC<AssessmentCardProps> = ({ title, evaluation, ratingColor, rawMetric }) => {
  const color = evaluation?.rating || ratingColor || RatingColor.UNKNOWN;
  
  const styles = getRatingStyles(color);

  return (
    <div className="group relative flex flex-col h-full p-6 bg-white border border-slate-200 rounded-xl hover:border-slate-300 transition-all shadow-sm hover:shadow-md">
      
      <div className="flex items-start justify-between mb-4">
        <h4 className="text-xs font-bold uppercase tracking-widest text-slate-500">{title}</h4>
        <div className={`p-1 rounded-full ${styles.bgIcon}`}>
          {styles.icon}
        </div>
      </div>
      
      {rawMetric && (
        <div className={`text-3xl font-bold ${styles.text} mb-3 font-merriweather`}>
          {rawMetric}
        </div>
      )}

      {evaluation?.rationale && (
        <div className="mt-auto">
          <p className="text-sm leading-relaxed text-slate-600">
            {evaluation.rationale}
          </p>
        </div>
      )}
      
      {/* Color accent bar at bottom */}
      <div className={`absolute bottom-0 left-0 right-0 h-1 ${styles.bgBar} rounded-b-xl opacity-0 group-hover:opacity-100 transition-opacity`} />
    </div>
  );
};

// New compact component for list views
export const RatingIcon: React.FC<{ color: RatingColor | string, className?: string }> = ({ color, className = "" }) => {
  const styles = getRatingStyles(color);
  return (
    <div className={`w-8 h-8 rounded-full flex items-center justify-center ${styles.bgIcon} ${className}`}>
      {styles.icon}
    </div>
  );
};

// Helper function for styles
const getRatingStyles = (c: RatingColor | string) => {
  // Normalize to string for comparison
  const color = String(c);

  switch (color) {
    case 'GREEN':
      return {
        bgBar: 'bg-emerald-500',
        bgIcon: 'bg-emerald-50',
        text: 'text-slate-900',
        icon: <CheckCircle className="w-4 h-4 text-emerald-600" />
      };
    case 'YELLOW':
      return {
        bgBar: 'bg-amber-500',
        bgIcon: 'bg-amber-50',
        text: 'text-slate-900',
        icon: <AlertTriangle className="w-4 h-4 text-amber-600" />
      };
    case 'RED':
      return { 
        bgBar: 'bg-rose-500', 
        bgIcon: 'bg-rose-50', 
        text: 'text-slate-900', 
        icon: <XCircle className="w-4 h-4 text-rose-600" /> 
      };
    default:
      return { 
        bgBar: 'bg-slate-300', 
        bgIcon: 'bg-slate-100', 
        text: 'text-slate-400', 
        icon: <Minus className="w-4 h-4 text-slate-400" /> 
      };
  }
};