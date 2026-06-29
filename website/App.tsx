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
const LandingPage = lazy(() => import('./pages/LandingPage').then(m => ({ default: m.LandingPage })));
const BrowsePage = lazy(() => import('./pages/BrowsePage').then(m => ({ default: m.BrowsePage })));
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
const ComparePage = lazy(() => import('./pages/ComparePage').then(m => ({ default: m.ComparePage })));
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
import { isMotifDesign } from './src/utils/designMode';


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
  '/about',
  '/privacy',
  '/faq',
  '/causes',
  '/guides',
  '/zakat-calculator',
]);

export const AppContent: React.FC = () => {
  const location = useLocation();
  const { isDark } = useLandingTheme();
  const isLandingPage = location.pathname === '/';
  // GMG "Modern" motif is the default design for everyone. `?design=legacy` is an
  // escape hatch to the old design. Two motif flavors, both suppress the app
  // Navbar/Footer/overlays:
  //  - full-bleed: motif pages that render their own GmgNav (landing, browse, …)
  //  - auth-chrome: legacy signed-in pages wrapped in motif chrome (profile, invites)
  const isMotif = isMotifDesign(location.search);
  const isGmgFullBleed =
    isMotif &&
    (location.pathname.startsWith('/charity/') ||
      location.pathname === '/browse' ||
      location.pathname === '/compare' ||
      location.pathname === '/');
  const isGmgAuthChrome =
    isMotif &&
    (location.pathname === '/profile' || location.pathname.startsWith('/plan/join'));
  const isGmgMotifOnly = MOTIF_CONTENT_ROUTES.has(location.pathname);
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
            <Route path="/" element={isGmgFullBleed ? <GmgLanding isDark={isDark} /> : <LandingPage />} />
            <Route path="/browse" element={isGmgFullBleed ? <GmgBrowse isDark={isDark} /> : <BrowsePage />} />
            <Route path="/charity/:id" element={<CharityDetailsPage />} />
            <Route path="/methodology" element={<MethodologyPage />} />
            <Route path="/link-to-us" element={<LinkToUsPage />} />
            <Route path="/changelog" element={<ChangelogPage isDark={isDark} />} />
            <Route path="/faq" element={<FAQPage isDark={isDark} />} />
            <Route path="/about" element={<AboutPage isDark={isDark} />} />
            <Route path="/privacy" element={<PrivacyPage isDark={isDark} />} />
            <Route path="/bookmarks" element={<Navigate to="/profile" replace />} />
            <Route path="/compare" element={isGmgFullBleed ? <GmgCompare isDark={isDark} /> : <ComparePage />} />
            <Route path="/profile" element={isGmgAuthChrome ? <GmgChromeFrame isDark={isDark} requireAuth><ProfilePage /></GmgChromeFrame> : <ProfilePage />} />
            <Route path="/prompts" element={<PromptsPage />} />
            <Route path="/prompts/:promptId" element={<PromptDetailPage />} />
            <Route path="/causes" element={<CausesIndexPage isDark={isDark} />} />
            <Route path="/causes/:slug" element={<CausePage />} />
            <Route path="/best-muslim-charities-in-usa" element={<BestMuslimCharitiesPage />} />
            <Route path="/guides" element={<GuidesIndexPage isDark={isDark} />} />
            <Route path="/guides/:slug" element={<GuidePage />} />
            <Route path="/zakat-calculator" element={<ZakatCalculatorHubPage isDark={isDark} />} />
            <Route path="/zakat-calculator/:asset" element={<ZakatCalculatorAssetPage />} />
            <Route path="/plan/join/:planId/:token" element={isGmgAuthChrome ? <GmgChromeFrame isDark={isDark}><JoinPlanPage /></GmgChromeFrame> : <JoinPlanPage />} />

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
