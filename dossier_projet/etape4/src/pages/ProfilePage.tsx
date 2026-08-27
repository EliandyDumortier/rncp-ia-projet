import { LogOut, Heart, Sparkles, Star } from 'lucide-react';
import type { Page } from '../types';
import { useAuth } from '../auth';
import { useFavorites } from '../useFavorites';

interface ProfilePageProps {
  nav: (p: Page) => void;
}

export function ProfilePage({ nav }: ProfilePageProps) {
  const { user, logout, flash } = useAuth();
  const { favoriteCount } = useFavorites(user?.user_id ?? null);

  if (!user) {
    return (
      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-16 text-center">
        <p className="text-gray-500 mb-4">Please sign in to view your profile.</p>
        <button onClick={() => nav('login')} className="text-rose-500 font-medium hover:text-rose-600">
          Sign in
        </button>
      </div>
    );
  }

  const stats = [
    { label: 'Username', value: user.username, icon: <Star className="w-5 h-5 text-rose-400" /> },
    { label: 'Favorites', value: String(favoriteCount), icon: <Heart className="w-5 h-5 text-pink-400" /> },
    { label: 'Recommendations viewed', value: '—', icon: <Sparkles className="w-5 h-5 text-orange-400" /> },
  ];

  return (
    <div className="max-w-2xl mx-auto px-4 sm:px-6 py-8">
      <h1 className="font-display text-2xl font-bold text-slate-800 mb-8 text-center">My Profile</h1>

      <div className="bg-white rounded-3xl shadow-soft border border-slate-100 p-6 mb-6">
        <dl className="space-y-4">
          {stats.map((s) => (
            <div key={s.label} className="flex items-center gap-3 pb-4 border-b border-slate-100 last:border-0 last:pb-0">
              <div className="w-10 h-10 rounded-2xl bg-rose-50 flex items-center justify-center">
                {s.icon}
              </div>
              <dt className="text-sm text-gray-500 flex-1">{s.label}</dt>
              <dd className="text-sm font-semibold text-slate-800">{s.value}</dd>
            </div>
          ))}
        </dl>
      </div>

      <button
        onClick={() => {
          logout();
          flash('You have been signed out successfully.', 'info');
          nav('home');
        }}
        className="w-full flex items-center justify-center gap-2 bg-rose-50 text-rose-600 font-semibold py-3 rounded-2xl hover:bg-rose-100 transition-all"
      >
        <LogOut className="w-5 h-5" aria-hidden="true" /> Sign out
      </button>
    </div>
  );
}
