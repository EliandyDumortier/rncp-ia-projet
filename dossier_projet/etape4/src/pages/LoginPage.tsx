import { useEffect, useState } from 'react';
import { LogIn, AlertCircle, UserPlus } from 'lucide-react';
import type { Page } from '../types';
import { useAuth } from '../auth';
import { RecommendationAPIError, DataAPIError, dataApi } from '../api';
import { GenreChipPicker } from '../components/GenreChipPicker';
import { ActorAutocomplete } from '../components/ActorAutocomplete';

interface LoginPageProps {
  nav: (p: Page) => void;
}

const MAX_GENRES = 3;
const MAX_ACTORS = 5;

export function LoginPage({ nav }: LoginPageProps) {
  const { login, register, flash, user } = useAuth();
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [email, setEmail] = useState('');
  const [consent, setConsent] = useState(false);
  const [marketingConsent, setMarketingConsent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // Optional onboarding preferences (favorite genres/actors). Entirely
  // skippable — a user can register without selecting anything here.
  const [allGenres, setAllGenres] = useState<string[]>([]);
  const [onboardGenres, setOnboardGenres] = useState<string[]>([]);
  const [onboardActors, setOnboardActors] = useState<string[]>([]);

  useEffect(() => {
    if (mode !== 'register' || allGenres.length > 0) return;
    dataApi.listGenres().then(setAllGenres).catch(() => setAllGenres([]));
  }, [mode, allGenres.length]);

  if (user) {
    nav('home');
    return null;
  }

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username || !password) {
      setError('Please enter your username and password.');
      return;
    }
    setError(null);
    setLoading(true);
    try {
      await login(username, password);
      flash(`Welcome, ${username}!`, 'success');
      nav('home');
    } catch (err) {
      if (err instanceof RecommendationAPIError) {
        setError('Invalid credentials. Please try again.');
      } else {
        setError('An unexpected error occurred.');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username || !email || !password) {
      setError('Please fill in all fields.');
      return;
    }
    if (!consent) {
      setError('You must accept data collection (GDPR).');
      return;
    }
    if (password.length < 8) {
      setError('Password must be at least 8 characters long.');
      return;
    }
    setError(null);
    setLoading(true);
    try {
      await register({
        pseudonyme: username,
        email,
        mot_de_passe: password,
        consentement_collecte: consent,
        consentement_marketing: marketingConsent,
      });
      // Optional onboarding preferences: only saved if the user picked
      // something. Registration itself never requires this.
      if (onboardGenres.length > 0 || onboardActors.length > 0) {
        try {
          await dataApi.updatePreferences({
            genres: onboardGenres,
            acteurs: onboardActors,
          });
        } catch {
          // Non-blocking: the account is still created successfully even if
          // saving initial preferences fails; the user can retry from their profile.
          flash('Account created, but your initial preferences could not be saved. You can set them from your profile.', 'info');
        }
      }
      flash(`Account created. Welcome, ${username}!`, 'success');
      nav('home');
    } catch (err) {
      if (err instanceof DataAPIError) {
        setError(err.message);
      } else if (err instanceof RecommendationAPIError) {
        setError('Account created, but automatic sign-in failed. Please sign in with your new account.');
      } else {
        setError('An unexpected error occurred.');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-md mx-auto px-4 sm:px-6 py-12">
      <div className="bg-white rounded-3xl shadow-card border border-slate-100 p-8">
        <div className="text-center mb-6">
          <div className="w-14 h-14 rounded-2xl bg-rose-50 flex items-center justify-center mx-auto mb-4">
            {mode === 'login' ? (
              <LogIn className="w-7 h-7 text-rose-500" aria-hidden="true" />
            ) : (
              <UserPlus className="w-7 h-7 text-rose-500" aria-hidden="true" />
            )}
          </div>
          <h1 className="font-display text-2xl font-bold text-slate-800">
            {mode === 'login' ? 'Sign In' : 'Create Account'}
          </h1>
          <p className="text-sm text-gray-400 mt-1">
            {mode === 'login'
              ? 'Sign in to access AI recommendations'
              : 'Sign up to access AI recommendations'}
          </p>
        </div>

        {error && (
          <div
            role="alert"
            aria-live="assertive"
            className="mb-4 bg-red-50 border border-red-200 rounded-2xl p-3 flex items-center gap-2"
          >
            <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0" aria-hidden="true" />
            <p className="text-sm text-red-700">{error}</p>
          </div>
        )}

        {mode === 'login' ? (
          <form onSubmit={handleLogin} noValidate className="space-y-4">
            <div>
              <label htmlFor="username" className="block text-sm font-medium text-slate-700 mb-1">
                Username
              </label>
              <input
                id="username"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoComplete="username"
                className="w-full px-4 py-3 border-2 border-slate-200 rounded-2xl focus:border-rose-400 outline-none text-sm"
                required
              />
            </div>
            <div>
              <label htmlFor="password" className="block text-sm font-medium text-slate-700 mb-1">
                Password
              </label>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
                className="w-full px-4 py-3 border-2 border-slate-200 rounded-2xl focus:border-rose-400 outline-none text-sm"
                required
              />
            </div>
            <button
              type="submit"
              disabled={loading}
              className="w-full bg-rose-500 text-white font-semibold py-3 rounded-2xl hover:bg-rose-600 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? 'Signing in...' : 'Sign in'}
            </button>
          </form>
        ) : (
          <form onSubmit={handleRegister} noValidate className="space-y-4">
            <div>
              <label htmlFor="reg-username" className="block text-sm font-medium text-slate-700 mb-1">
                Username
              </label>
              <input
                id="reg-username"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoComplete="username"
                className="w-full px-4 py-3 border-2 border-slate-200 rounded-2xl focus:border-rose-400 outline-none text-sm"
                required
              />
            </div>
            <div>
              <label htmlFor="reg-email" className="block text-sm font-medium text-slate-700 mb-1">
                Email
              </label>
              <input
                id="reg-email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoComplete="email"
                className="w-full px-4 py-3 border-2 border-slate-200 rounded-2xl focus:border-rose-400 outline-none text-sm"
                required
              />
            </div>
            <div>
              <label htmlFor="reg-password" className="block text-sm font-medium text-slate-700 mb-1">
                Password (8 characters minimum)
              </label>
              <input
                id="reg-password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="new-password"
                className="w-full px-4 py-3 border-2 border-slate-200 rounded-2xl focus:border-rose-400 outline-none text-sm"
                required
              />
            </div>

            <div className="pt-2 border-t border-slate-100">
              <p className="text-sm font-medium text-slate-700 mb-1">
                Personalize your recommendations <span className="font-normal text-gray-400">(optional)</span>
              </p>
              <p className="text-xs text-gray-400 mb-3">
                You can skip this and set it later from your profile.
              </p>
              <div className="space-y-3">
                <div>
                  <label className="block text-xs font-medium text-slate-500 mb-1">
                    Favorite genres (up to {MAX_GENRES})
                  </label>
                  <GenreChipPicker
                    id="onboard-genres"
                    allGenres={allGenres}
                    selected={onboardGenres}
                    onChange={setOnboardGenres}
                    maxSelections={MAX_GENRES}
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-500 mb-1">
                    Favorite actors/actresses (up to {MAX_ACTORS})
                  </label>
                  <ActorAutocomplete
                    id="onboard-actors"
                    selected={onboardActors}
                    onChange={setOnboardActors}
                    maxSelections={MAX_ACTORS}
                  />
                </div>
              </div>
            </div>

            <div className="space-y-2">
              <label className="flex items-start gap-2 text-sm text-slate-600">
                <input
                  type="checkbox"
                  checked={consent}
                  onChange={(e) => setConsent(e.target.checked)}
                  className="mt-0.5"
                  required
                />
                <span>I accept the collection of my data (GDPR art. 6.1.a)</span>
              </label>
              <label className="flex items-start gap-2 text-sm text-slate-600">
                <input
                  type="checkbox"
                  checked={marketingConsent}
                  onChange={(e) => setMarketingConsent(e.target.checked)}
                  className="mt-0.5"
                />
                <span>I accept to receive marketing communications (GDPR art. 7)</span>
              </label>
            </div>
            <button
              type="submit"
              disabled={loading}
              className="w-full bg-rose-500 text-white font-semibold py-3 rounded-2xl hover:bg-rose-600 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? 'Creating...' : 'Create my account'}
            </button>
          </form>
        )}

        <div className="text-center mt-4">
          {mode === 'login' ? (
            <p className="text-sm text-gray-400">
              Don't have an account yet?{' '}
              <button
                onClick={() => { setMode('register'); setError(null); }}
                className="text-rose-500 font-medium hover:text-rose-600"
              >
                Sign up
              </button>
            </p>
          ) : (
            <p className="text-sm text-gray-400">
              Already registered?{' '}
              <button
                onClick={() => { setMode('login'); setError(null); }}
                className="text-rose-500 font-medium hover:text-rose-600"
              >
                Sign in
              </button>
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
