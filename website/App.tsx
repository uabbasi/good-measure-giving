import React, { lazy, Suspense, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, useLocation, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import { LazyMotion, domAnimation } from 'motion/react';
import { ThemeProvider } from './contexts/ThemeContext';
import { LandingThemeProvider, useLandingTheme } from './contexts/LandingThemeContext';
import { UserFeaturesProvider } from './src/contexts/UserFeaturesContext';
import { Navbar } from './components/Navbar';
// BetaBanner moved inline to Navbar as a subtle pill
import { Footer } from './components/Footer';
const CharityDetailsPage = lazy(() => import('./pages/CharityDetailsPage').then(m => ({ default: m.CharityDetailsPage })));
const MethodologyPage = lazy(() => import('./pages/MethodologyPage').then(m => ({ default: m.MethodologyPage })));
const LinkToUsPage = lazy(() => import('./pages/LinkToUsPage').then(m => ({ default: m.LinkToUsPage })));
const ChangelogPage = lazy(() => import('./pages/ChangelogPage').then(m => ({ default: m.ChangelogPage })));
const FAQPage = lazy(() => import('./pages/FAQPage').then(m => ({ default: m.FAQPage })));
const AboutPage = lazy(() => import('./pages/AboutPage').then(m => ({ default: m.AboutPage })));
const PrivacyPage = lazy(() => import('./pages/PrivacyPage').then(m => ({ default: m.PrivacyPage })));
const NotFoundPage = lazy(() => import('./pages/NotFoundPage').then(m => ({ default: m.NotFoundPage })));
const PromptsPage = lazy(() => import('./pages/PromptsPage').then(m => ({ default: m.PromptsPage })));
const PromptDetailPage = lazy(() => import('./pages/PromptDetailPage').then(m => ({ default: m.PromptDetailPage })));
const ProfilePage = lazy(() => import('./pages/ProfilePage').then(m => ({ default: m.ProfilePage })));
const CausesIndexPage = lazy(() => import('./pages/CausesIndexPage').then(m => ({ default: m.CausesIndexPage })));
const CausePage = lazy(() => import('./pages/CausePage').then(m => ({ default: m.CausePage })));
const BestMuslimCharitiesPage = lazy(() => import('./pages/BestMuslimCharitiesPage').then(m => ({ default: m.BestMuslimCharitiesPage })));
const GuidesIndexPage = lazy(() => import('./pages/GuidesIndexPage').then(m => ({ default: m.GuidesIndexPage })));
const GuidePage = lazy(() => import('./pages/GuidePage').then(m => ({ default: m.GuidePage })));
const ZakatCalculatorHubPage = lazy(() => import('./pages/ZakatCalculatorHubPage').then(m => ({ default: m.ZakatCalculatorHubPage })));
const ZakatCalculatorAssetPage = lazy(() => import('./pages/ZakatCalculatorAssetPage').then(m => ({ default: m.ZakatCalculatorAssetPage })));
const JoinPlanPage = lazy(() => import('./pages/JoinPlanPage').then(m => ({ default: m.JoinPlanPage })));
const GmgBrowse = lazy(() => import('./src/components/gmg/GmgBrowse').then(m => ({ default: m.GmgBrowse })));
const GmgLanding = lazy(() => import('./src/components/gmg/GmgLanding').then(m => ({ default: m.GmgLanding })));
const GmgCompare = lazy(() => import('./src/components/gmg/GmgCompare').then(m => ({ default: m.GmgCompare })));
import { CompareBar } from './src/components/CompareBar';
import { MobileBottomNav } from './src/components/MobileBottomNav';
import { WelcomeTour } from './src/components/WelcomeTour';
import { IntroPresentation } from './src/components/IntroPresentation';
import { BookmarkToast } from './src/components/BookmarkToast';
import { BookmarkAutoCategorize } from './src/components/BookmarkAutoCategorize';
import { NamePromptModal } from './src/auth';
import { ClientOnly } from './src/components/ClientOnly';
import { GmgChromeFrame } from './src/components/gmg/chrome';
import { DevQuickLogin } from './src/auth/DevQuickLogin';
import { ScrollToTop } from './components/ScrollToTop';
import { trackPageView } from './src/utils/analytics';


// TanStack Query client — staleTime: Infinity because charity data is static JSON
export function createAppQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: Infinity,
        refetchOnWindowFocus: false,
      },
    },
  });
}

export const AppProviders: React.FC<{ queryClient: QueryClient; children: React.ReactNode }> = ({
  queryClient,
  children,
}) => (
  <QueryClientProvider client={queryClient}>
    <LazyMotion features={domAnimation} strict>
      <ThemeProvider>
        <LandingThemeProvider>
          <UserFeaturesProvider>{children}</UserFeaturesProvider>
        </LandingThemeProvider>
      </ThemeProvider>
    </LazyMotion>
  </QueryClientProvider>
);

// T009-T011: Removed ThirdBucket theme switching - single Amal theme only

// Content/SEO pages converted to the Modern motif (motif-only, no legacy variant).
// Each renders its own GmgNav + footer via the content kit; add a route here as it
// is converted so the app's legacy Navbar/Footer is suppressed for it.
const MOTIF_CONTENT_ROUTES = new Set<string>([
  '/changelog',
  '/methodology',
  '/about',
  '/privacy',
  '/faq',
  '/causes',
  '/guides',
  '/prompts',
  '/link-to-us',
  '/best-muslim-charities-in-usa',
  '/zakat-calculator',
]);

// Dynamic detail routes converted to the motif. MOTIF_CONTENT_ROUTES is matched by
// exact pathname, so these prefixes catch /causes/:slug, /guides/:slug, /prompts/:id.
const MOTIF_CONTENT_PREFIXES = ['/causes/', '/guides/', '/prompts/', '/zakat-calculator/'];

export const AppContent: React.FC = () => {
  const location = useLocation();
  const { isDark } = useLandingTheme();
  // Canonical URLs carry a trailing slash (e.g. /browse/, /about/). The design-mode
  // checks below match exact paths, so normalize the trailing slash first —
  // otherwise a RELOADED canonical URL fails the exact match and falls through to
  // the legacy design, even though SSR and in-app navigation resolved the motif.
  const path = location.pathname.length > 1 ? location.pathname.replace(/\/+$/, '') : location.pathname;
  const isLandingPage = path === '/';
  // GMG "Modern" motif is the only design. Two motif flavors, both suppress the app
  // Navbar/Footer/overlays:
  //  - full-bleed: motif pages that render their own GmgNav (landing, browse, …)
  //  - auth-chrome: signed-in pages wrapped in motif chrome (profile, invites)
  // The legacy design escape hatch has been retired; rollback lives in git history.
  const isGmgFullBleed =
    path.startsWith('/charity/') ||
    path === '/browse' ||
    path === '/compare' ||
    path === '/';
  const isGmgAuthChrome =
    path === '/profile' || path.startsWith('/plan/join');
  const isGmgMotifOnly =
    MOTIF_CONTENT_ROUTES.has(path) ||
    MOTIF_CONTENT_PREFIXES.some((pre) => path.startsWith(pre));
  const isGmgPreview = isGmgFullBleed || isGmgAuthChrome || isGmgMotifOnly;

  // T049: Track page views on route changes
  useEffect(() => {
    trackPageView(location.pathname);
  }, [location.pathname]);

  return (
    <div className={isGmgPreview ? 'min-h-screen flex flex-col' : `${isLandingPage ? 'h-[100dvh] lg:h-auto lg:min-h-screen overflow-hidden lg:overflow-visible' : 'min-h-screen'} flex flex-col font-sans transition-colors duration-300 ${isDark ? 'bg-slate-950 text-white' : 'bg-slate-50 text-slate-900'}`}>
      {/* Skip to main content link for keyboard users */}
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:top-4 focus:left-4 focus:z-50 focus:px-4 focus:py-2 focus:bg-emerald-600 focus:text-white focus:rounded-lg focus:outline-none"
      >
        Skip to main content
      </a>
      {!isGmgPreview && <Navbar />}
      <main id="main" className={`flex-grow ${isLandingPage ? 'min-h-0 overflow-hidden lg:min-h-0 lg:overflow-visible' : ''}`}>
        <Suspense fallback={null}>
          <Routes>
            <Route path="/" element={<GmgLanding isDark={isDark} />} />
            <Route path="/browse" element={<GmgBrowse isDark={isDark} />} />
            <Route path="/charity/:id" element={<CharityDetailsPage />} />
            <Route path="/methodology" element={<MethodologyPage isDark={isDark} />} />
            <Route path="/link-to-us" element={<LinkToUsPage isDark={isDark} />} />
            <Route path="/changelog" element={<ChangelogPage isDark={isDark} />} />
            <Route path="/faq" element={<FAQPage isDark={isDark} />} />
            <Route path="/about" element={<AboutPage isDark={isDark} />} />
            <Route path="/privacy" element={<PrivacyPage isDark={isDark} />} />
            <Route path="/bookmarks" element={<Navigate to="/profile" replace />} />
            <Route path="/compare" element={<GmgCompare isDark={isDark} />} />
            <Route path="/profile" element={<GmgChromeFrame isDark={isDark} requireAuth><ProfilePage /></GmgChromeFrame>} />
            <Route path="/prompts" element={<PromptsPage isDark={isDark} />} />
            <Route path="/prompts/:promptId" element={<PromptDetailPage isDark={isDark} />} />
            <Route path="/causes" element={<CausesIndexPage isDark={isDark} />} />
            <Route path="/causes/:slug" element={<CausePage isDark={isDark} />} />
            <Route path="/best-muslim-charities-in-usa" element={<BestMuslimCharitiesPage isDark={isDark} />} />
            <Route path="/guides" element={<GuidesIndexPage isDark={isDark} />} />
            <Route path="/guides/:slug" element={<GuidePage isDark={isDark} />} />
            <Route path="/zakat-calculator" element={<ZakatCalculatorHubPage isDark={isDark} />} />
            <Route path="/zakat-calculator/:asset" element={<ZakatCalculatorAssetPage isDark={isDark} />} />
            <Route path="/plan/join/:planId/:token" element={<GmgChromeFrame isDark={isDark}><JoinPlanPage /></GmgChromeFrame>} />

            {/* Catch-all: 404 */}
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </Suspense>
      </main>
      {!isGmgPreview && (isLandingPage ? <div className="hidden lg:block"><Footer /></div> : <Footer />)}
      <ClientOnly>
        {!isGmgPreview && <CompareBar />}
        {!isGmgPreview && !isLandingPage && <MobileBottomNav />}
        {!isGmgPreview && <WelcomeTour />}
        {!isGmgPreview && <IntroPresentation />}
        <BookmarkToast />
        <BookmarkAutoCategorize />
        <NamePromptModal />
      </ClientOnly>
    </div>
  );
};

const App: React.FC = () => {
  const [queryClient] = React.useState(createAppQueryClient);
  return (
    <AppProviders queryClient={queryClient}>
      {import.meta.env.DEV && <DevQuickLogin />}
      <Router future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <ScrollToTop />
        <AppContent />
      </Router>
      <ReactQueryDevtools initialIsOpen={false} />
    </AppProviders>
  );
};

export default App;
