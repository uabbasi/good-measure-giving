import React, { lazy, Suspense, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, useLocation, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import { LazyMotion, domAnimation } from 'motion/react';
import { ThemeProvider } from './contexts/ThemeContext';
import { LandingThemeProvider, useLandingTheme } from './contexts/LandingThemeContext';
import { UserFeaturesProvider } from './src/contexts/UserFeaturesContext';
import { Navbar } from './components/Navbar';
import { Footer } from './components/Footer';
const LandingPage = lazy(() => import('./pages/LandingPage').then(m => ({ default: m.LandingPage })));
const BrowsePage = lazy(() => import('./pages/BrowsePage').then(m => ({ default: m.BrowsePage })));
const CharityDetailsPage = lazy(() => import('./pages/CharityDetailsPage').then(m => ({ default: m.CharityDetailsPage })));
const MethodologyPage = lazy(() => import('./pages/MethodologyPage').then(m => ({ default: m.MethodologyPage })));
const FAQPage = lazy(() => import('./pages/FAQPage').then(m => ({ default: m.FAQPage })));
const AboutPage = lazy(() => import('./pages/AboutPage').then(m => ({ default: m.AboutPage })));
const NotFoundPage = lazy(() => import('./pages/NotFoundPage').then(m => ({ default: m.NotFoundPage })));
const PromptsPage = lazy(() => import('./pages/PromptsPage').then(m => ({ default: m.PromptsPage })));
const PromptDetailPage = lazy(() => import('./pages/PromptDetailPage').then(m => ({ default: m.PromptDetailPage })));
const ComparePage = lazy(() => import('./pages/ComparePage').then(m => ({ default: m.ComparePage })));
const ProfilePage = lazy(() => import('./pages/ProfilePage').then(m => ({ default: m.ProfilePage })));
import { CompareBar } from './src/components/CompareBar';
import { ScrollToTop } from './components/ScrollToTop';
import { trackPageView } from './src/utils/analytics';


// TanStack Query client — staleTime: Infinity because charity data is static JSON
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: Infinity,
      refetchOnWindowFocus: false,
    },
  },
});

// T009-T011: Removed ThirdBucket theme switching - single Amal theme only

const AppContent: React.FC = () => {
  const location = useLocation();
  const { isDark } = useLandingTheme();
  const isLandingPage = location.pathname === '/';

  // T049: Track page views on route changes
  useEffect(() => {
    trackPageView(location.pathname);
  }, [location.pathname]);

  return (
    <div className={`min-h-screen flex flex-col font-sans transition-colors duration-300 ${isDark ? 'bg-slate-950 text-white' : 'bg-slate-50 text-slate-900'}`}>
      {/* Skip to main content link for keyboard users */}
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:top-4 focus:left-4 focus:z-50 focus:px-4 focus:py-2 focus:bg-emerald-600 focus:text-white focus:rounded-lg focus:outline-none"
      >
        Skip to main content
      </a>
      <Navbar />
      <main id="main" className="flex-grow">
        <Suspense fallback={null}>
          <Routes>
            <Route path="/" element={<LandingPage />} />
            <Route path="/browse" element={<BrowsePage />} />
            <Route path="/charity/:id" element={<CharityDetailsPage />} />
            <Route path="/methodology" element={<MethodologyPage />} />
            <Route path="/faq" element={<FAQPage />} />
            <Route path="/about" element={<AboutPage />} />
            <Route path="/bookmarks" element={<Navigate to="/profile" replace />} />
            <Route path="/compare" element={<ComparePage />} />
            <Route path="/profile" element={<ProfilePage />} />
            <Route path="/prompts" element={<PromptsPage />} />
            <Route path="/prompts/:promptId" element={<PromptDetailPage />} />

            {/* Catch-all: 404 */}
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </Suspense>
      </main>
      <Footer />
      <CompareBar />
    </div>
  );
};

const App: React.FC = () => {
  return (
    <QueryClientProvider client={queryClient}>
      <LazyMotion features={domAnimation} strict>
        <ThemeProvider>
          <LandingThemeProvider>
            <UserFeaturesProvider>
              <Router future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
                <ScrollToTop />
                <AppContent />
              </Router>
            </UserFeaturesProvider>
          </LandingThemeProvider>
        </ThemeProvider>
      </LazyMotion>
      <ReactQueryDevtools initialIsOpen={false} />
    </QueryClientProvider>
  );
};

export default App;