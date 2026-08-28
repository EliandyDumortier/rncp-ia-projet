import { useState } from 'react';
import { Film, Menu, X, LogOut, User as UserIcon } from 'lucide-react';
import type { Page } from '../types';
import { useAuth } from '../auth';

interface NavbarProps {
  page: Page;
  nav: (p: Page) => void;
}

const navItems: [Page, string][] = [
  ['home', 'Home'],
  ['search', 'Search'],
  ['recommendations', 'Recommendations'],
  ['favorites', 'Favorites'],
  ['history', 'My List'],
];

export function Navbar({ page, nav }: NavbarProps) {
  const { user, logout } = useAuth();

  return (
    <header role="banner" className="sticky top-0 z-50 bg-white/90 backdrop-blur-md border-b border-slate-100">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-4 flex items-center justify-between">
        <button
          onClick={() => nav('home')}
          className="flex items-center gap-2 font-display font-bold text-xl text-rose-600"
          aria-label="K-Drama AI — Home"
        >
          <Film className="w-6 h-6" aria-hidden="true" />
          K-Drama AI
        </button>

        <nav aria-label="Main menu" className="hidden md:flex items-center gap-6">
          {navItems.map(([key, label]) => (
            <button
              key={key}
              onClick={() => nav(key)}
              aria-current={page === key ? 'page' : undefined}
              className={`text-sm font-medium transition-colors ${
                page === key ? 'text-rose-600' : 'text-slate-600 hover:text-rose-500'
              }`}
            >
              {label}
            </button>
          ))}
          {user ? (
            <div className="flex items-center gap-3">
              <button
                onClick={() => nav('profile')}
                className="flex items-center gap-1.5 text-sm font-medium text-slate-600 hover:text-rose-500"
              >
                <UserIcon className="w-4 h-4" aria-hidden="true" />
                {user.username}
              </button>
              <button
                onClick={logout}
                className="flex items-center gap-1 text-sm text-slate-500 hover:text-rose-500"
                aria-label="Sign out"
              >
                <LogOut className="w-4 h-4" aria-hidden="true" />
              </button>
            </div>
          ) : (
            <button
              onClick={() => nav('login')}
              className={`text-sm font-medium ${page === 'login' ? 'text-rose-600' : 'text-slate-600 hover:text-rose-500'}`}
            >
              Sign in
            </button>
          )}
        </nav>

        <MobileMenu page={page} nav={nav} />
      </div>
    </header>
  );
}

function MobileMenu({ page, nav }: NavbarProps) {
  const { user, logout } = useAuth();
  const [open, setOpen] = useState(false);

  return (
    <div className="md:hidden">
      <button
        className="p-2 text-slate-600"
        onClick={() => setOpen(!open)}
        aria-label="Menu"
        aria-expanded={open}
      >
        {open ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
      </button>
      {open && (
        <nav className="absolute top-16 right-4 bg-white rounded-2xl shadow-card border border-slate-100 p-4 flex flex-col gap-2 min-w-[180px]">
          {navItems.map(([key, label]) => (
            <button
              key={key}
              onClick={() => { nav(key); setOpen(false); }}
              className={`text-sm font-medium py-2 text-left ${page === key ? 'text-rose-600' : 'text-slate-600'}`}
            >
              {label}
            </button>
          ))}
          {user ? (
            <>
              <button onClick={() => { nav('profile'); setOpen(false); }} className="text-sm font-medium py-2 text-left text-slate-600">
                {user.username}
              </button>
              <button onClick={() => { logout(); setOpen(false); }} className="text-sm py-2 text-left text-slate-500">
                Sign out
              </button>
            </>
          ) : (
            <button onClick={() => { nav('login'); setOpen(false); }} className="text-sm font-medium py-2 text-left text-slate-600">
              Sign in
            </button>
          )}
        </nav>
      )}
    </div>
  );
}
