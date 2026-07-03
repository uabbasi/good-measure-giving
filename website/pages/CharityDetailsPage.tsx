import React, { useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { useCharity } from '../src/hooks/useCharities';
import { GmgCharityDetail } from '../src/components/gmg/GmgCharityDetail';
import { useAuth } from '../src/auth';
import { useRichAccess } from '../src/hooks/useRichAccess';
import { incrementSignedInViews } from '../src/hooks/useActivationNudge';
import { useLandingTheme } from '../contexts/LandingThemeContext';

export const CharityDetailsPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const { charity, loading, error } = useCharity(id || '');
  const { isDark } = useLandingTheme();
  const { isSignedIn } = useAuth();
  const { recordView } = useRichAccess(id);

  // Set page title with charity name
  useEffect(() => {
    if (charity) {
      document.title = `${charity.name} | Good Measure Giving`;
    }
    return () => { document.title = 'Good Measure Giving | Muslim Charity Evaluator'; };
  }, [charity]);

  // Record view for anonymous users (progressive reveal).
  // GmgCharityDetail does NOT record views, so this must stay here.
  useEffect(() => {
    if (id && !isSignedIn) {
      recordView(id);
    }
    if (id && isSignedIn) {
      incrementSignedInViews();
    }
  }, [id, isSignedIn, recordView]);

  if (loading) {
    return (
      <div className={`min-h-screen flex items-center justify-center px-4 ${isDark ? 'bg-slate-950' : 'bg-slate-50'}`}>
        <div className={`rounded-2xl shadow-sm p-10 text-center max-w-md ${isDark ? 'bg-slate-900 border border-slate-800' : 'bg-white border border-slate-200'}`}>
          <div className="animate-pulse">
            <div className={`h-8 w-48 rounded mx-auto mb-4 ${isDark ? 'bg-slate-700' : 'bg-slate-200'}`} />
            <div className={`h-4 w-32 rounded mx-auto ${isDark ? 'bg-slate-700' : 'bg-slate-200'}`} />
          </div>
        </div>
      </div>
    );
  }

  if (!charity || error) {
    return (
      <div className={`min-h-screen flex items-center justify-center px-4 ${isDark ? 'bg-slate-950' : 'bg-slate-50'}`}>
        <div className={`rounded-2xl shadow-sm p-10 text-center max-w-md ${isDark ? 'bg-slate-900 border border-slate-800' : 'bg-white border border-slate-200'}`}>
          <h1 className={`text-2xl font-bold font-merriweather mb-3 ${isDark ? 'text-white' : 'text-slate-900'}`}>Charity not found</h1>
          <p className={`mb-6 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>The charity you're looking for isn't in our directory.</p>
          <Link to="/browse/" className={`inline-flex items-center gap-2 px-4 py-3 rounded-lg text-sm font-bold transition-colors ${isDark ? 'bg-slate-700 text-white hover:bg-slate-600' : 'bg-slate-900 text-white hover:bg-slate-800'}`}>
            <ArrowLeft className="w-4 h-4" aria-hidden="true" />
            Back to Directory
          </Link>
        </div>
      </div>
    );
  }

  return <GmgCharityDetail charity={charity} isDark={isDark} />;
};
