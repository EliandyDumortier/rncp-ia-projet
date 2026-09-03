import { useState, useEffect, useCallback } from 'react';
import type { Page } from './types';
import { AuthProvider } from './auth';
import { Navbar } from './components/Navbar';
import { SkipLink } from './components/SkipLink';
import { FlashMessages } from './components/FlashMessages';
import { HomePage } from './pages/HomePage';
import { SearchPage } from './pages/SearchPage';
import { RecommendationsPage } from './pages/RecommendationsPage';
import { FavoritesPage } from './pages/FavoritesPage';
import { HistoryPage } from './pages/HistoryPage';
import { ProfilePage } from './pages/ProfilePage';
import { LoginPage } from './pages/LoginPage';

function AppContent() {
  const [page, setPage] = useState<Page>('home');

  const nav = useCallback((p: Page) => {
    setPage(p);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }, []);

  useEffect(() => {
    document.title = pageTitle(page);
  }, [page]);

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">
      <SkipLink />
      <Navbar page={page} nav={nav} />
      <FlashMessages />

      <main id="main-content" role="main" className="flex-1">
        {page === 'home' && <HomePage nav={nav} />}
        {page === 'search' && <SearchPage nav={nav} />}
        {page === 'recommendations' && <RecommendationsPage nav={nav} />}
        {page === 'favorites' && <FavoritesPage nav={nav} />}
        {page === 'history' && <HistoryPage nav={nav} />}
        {page === 'profile' && <ProfilePage nav={nav} />}
        {page === 'login' && <LoginPage nav={nav} />}
      </main>

      <footer role="contentinfo" className="bg-slate-900 text-slate-300 py-8 px-4">
        <div className="max-w-6xl mx-auto text-center">
          <p className="font-display font-bold text-rose-400 mb-2">K-Drama AI</p>
          <p className="text-sm text-slate-400">
            React web app with AI recommendation service — Step 4, RNCP AI
          </p>
          <p className="text-xs text-slate-500 mt-2">
            RGAA 4.1 / WCAG 2.1 AA compliant &middot; Educational project
          </p>
        </div>
      </footer>
    </div>
  );
}

function pageTitle(page: Page): string {
  const titles: Record<Page, string> = {
    home: 'K-Drama AI — Home',
    search: 'K-Drama AI — Search',
    recommendations: 'K-Drama AI — Recommendations',
    favorites: 'K-Drama AI — My Favorites',
    history: 'K-Drama AI — My Watched Dramas',
    profile: 'K-Drama AI — My Profile',
    login: 'K-Drama AI — Sign In',
  };
  return titles[page];
}

export function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}
