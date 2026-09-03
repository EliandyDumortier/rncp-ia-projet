import { LogOut, Heart, Eye, Sparkles, Star, Save } from 'lucide-react';
import { useEffect, useState } from 'react';
import type { Page, UserProfile } from '../types';
import { useAuth } from '../auth';
import { dataApi, DataAPIError } from '../api';
import { GenreChipPicker } from '../components/GenreChipPicker';
import { ActorAutocomplete } from '../components/ActorAutocomplete';

interface ProfilePageProps {
  nav: (p: Page) => void;
}

const MAX_GENRES = 3;
const MAX_ACTORS = 5;

export function ProfilePage({ nav }: ProfilePageProps) {
  const { user, logout, flash } = useAuth();

  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const [allGenres, setAllGenres] = useState<string[]>([]);
  const [selectedGenres, setSelectedGenres] = useState<string[]>([]);
  const [selectedActors, setSelectedActors] = useState<string[]>([]);
  const [happyEndingOnly, setHappyEndingOnly] = useState(false);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const [me, genres] = await Promise.all([dataApi.getMe(), dataApi.listGenres()]);
        if (cancelled) return;
        setProfile(me);
        setSelectedGenres(me.genres_preferes);
        setSelectedActors(me.acteurs_preferes);
        setHappyEndingOnly(me.fin_heureuse_uniquement);
        setAllGenres(genres);
      } catch {
        if (!cancelled) flash('Could not load your profile. Please try again later.', 'error');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user]);

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

  const handleSavePreferences = async () => {
    setSaving(true);
    try {
      const updated = await dataApi.updatePreferences({
        genres: selectedGenres,
        acteurs: selectedActors,
        fin_heureuse_uniquement: happyEndingOnly,
      });
      setProfile(updated);
      flash('Your recommendation preferences have been saved.', 'success');
    } catch (err) {
      if (err instanceof DataAPIError) {
        flash(err.message, 'error');
      } else {
        flash('Could not save your preferences. Please try again.', 'error');
      }
    } finally {
      setSaving(false);
    }
  };

  const stats = [
    { label: 'Username', value: user.username, icon: <Star className="w-5 h-5 text-rose-400" /> },
    { label: 'Favorites', value: String(profile?.nb_favoris ?? '—'), icon: <Heart className="w-5 h-5 text-pink-400" /> },
    { label: 'Dramas watched', value: String(profile?.nb_dramas_vus ?? '—'), icon: <Eye className="w-5 h-5 text-violet-400" /> },
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

      <div className="bg-white rounded-3xl shadow-soft border border-slate-100 p-6 mb-6">
        <div className="flex items-center gap-2 mb-1">
          <Sparkles className="w-5 h-5 text-rose-400" aria-hidden="true" />
          <h2 className="font-display text-lg font-bold text-slate-800">Recommendation preferences</h2>
        </div>
        <p className="text-sm text-gray-400 mb-6">
          Optional — helps us personalize your recommendations. You can leave any of this blank.
        </p>

        {loading ? (
          <p className="text-sm text-gray-400">Loading your preferences…</p>
        ) : (
          <div className="space-y-6">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">
                Favorite genres (up to {MAX_GENRES})
              </label>
              <GenreChipPicker
                allGenres={allGenres}
                selected={selectedGenres}
                onChange={setSelectedGenres}
                maxSelections={MAX_GENRES}
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">
                Favorite actors/actresses (up to {MAX_ACTORS})
              </label>
              <ActorAutocomplete
                selected={selectedActors}
                onChange={setSelectedActors}
                maxSelections={MAX_ACTORS}
              />
            </div>

            <label className="flex items-start gap-2 text-sm text-slate-600">
              <input
                type="checkbox"
                checked={happyEndingOnly}
                onChange={(e) => setHappyEndingOnly(e.target.checked)}
                className="mt-0.5"
              />
              <span>Only recommend dramas with a happy ending</span>
            </label>

            <button
              onClick={handleSavePreferences}
              disabled={saving}
              className="w-full flex items-center justify-center gap-2 bg-rose-500 text-white font-semibold py-3 rounded-2xl hover:bg-rose-600 disabled:opacity-50 transition-all"
            >
              <Save className="w-4 h-4" aria-hidden="true" />
              {saving ? 'Saving…' : 'Save preferences'}
            </button>
          </div>
        )}
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
