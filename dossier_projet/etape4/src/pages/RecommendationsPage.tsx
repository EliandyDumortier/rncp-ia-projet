import { Sparkles, AlertCircle, RefreshCw, Send, History as HistoryIcon } from 'lucide-react';
import { useState, useEffect, useCallback } from 'react';
import type { Drama, Recommendation, Page } from '../types';
import { fetchDramas } from '../data';
import { DramaCard } from '../components/DramaCard';
import { DramaDetailModal } from '../components/DramaDetailModal';
import { LoadingSkeleton } from '../components/LoadingSkeleton';
import { apiClient, RecommendationAPIError } from '../api';
import { useAuth } from '../auth';
import { useFavorites } from '../useFavorites';
import { useWatchedDramas } from '../useWatchedDramas';

interface RecommendationsPageProps {
  nav: (p: Page) => void;
}

// Hard cap enforced on both sections, independent of what top_k is requested
// with: the recommendation page must never show more than 4 results per
// section (history/personalized and chat/mood).
const MAX_RESULTS_PER_SECTION = 4;

const MOOD_GENRES = [
  { label: 'Comfort', emoji: '🪴' },
  { label: 'Cry', emoji: '😭' },
  { label: 'Funny', emoji: '😂' },
  { label: 'Thriller', emoji: '🎭' },
  { label: 'Cozy Weekend', emoji: '☕' },
  { label: 'Strong Female Lead', emoji: '👩' },
  { label: 'Slow Burn Romance', emoji: '🔥' },
  { label: 'Fantasy Adventure', emoji: '✨' },
];

export function RecommendationsPage({ nav }: RecommendationsPageProps) {
  const { user, flash } = useAuth();
  const { favorites, isFavorite, addFavorite, removeFavorite } = useFavorites(user?.user_id ?? null);
  const { isWatched } = useWatchedDramas(user?.user_id ?? null);

  const [description, setDescription] = useState('');
  const [selectedMoods, setSelectedMoods] = useState<string[]>([]);

  const [personalized, setPersonalized] = useState<Recommendation[]>([]);
  const [personalizedLoading, setPersonalizedLoading] = useState(false);
  const [personalizedError, setPersonalizedError] = useState<string | null>(null);
  const [personalizedFetched, setPersonalizedFetched] = useState(false);

  const [moodResults, setMoodResults] = useState<Recommendation[]>([]);
  const [moodLoading, setMoodLoading] = useState(false);
  const [moodError, setMoodError] = useState<string | null>(null);
  const [moodFetched, setMoodFetched] = useState(false);

  const [selectedDrama, setSelectedDrama] = useState<Drama | null>(null);

  // History/personalized recommendations are always available for a signed-in
  // user (based on their profile, watch history and preferences server-side),
  // so we fetch them automatically once the user is known.
  const fetchPersonalized = useCallback(async () => {
    if (!user) return;
    setPersonalizedLoading(true);
    setPersonalizedError(null);
    try {
      const result = await apiClient.getRecommendations({
        user_id: user.user_id,
        top_k: MAX_RESULTS_PER_SECTION,
      });
      setPersonalized((result.recommendations || []).slice(0, MAX_RESULTS_PER_SECTION));
    } catch (err) {
      if (err instanceof RecommendationAPIError) {
        setPersonalizedError(err.message);
        const fallback = await fetchDramas(1, MAX_RESULTS_PER_SECTION, undefined, 'note_moyenne', 'desc');
        setPersonalized(fallback.items.slice(0, MAX_RESULTS_PER_SECTION));
      } else {
        setPersonalizedError(err instanceof Error ? err.message : String(err));
      }
    } finally {
      setPersonalizedLoading(false);
      setPersonalizedFetched(true);
    }
  }, [user]);

  useEffect(() => {
    if (user) {
      fetchPersonalized();
    }
  }, [user, fetchPersonalized]);

  // Chat/mood recommendations are driven by explicit user input (free text
  // and/or mood chips) and are only fetched on demand.
  const handleGetMoodRecommendations = async () => {
    if (!user) {
      flash('Please sign in to get recommendations.', 'info');
      nav('login');
      return;
    }

    if (!description.trim() && selectedMoods.length === 0) {
      setMoodError('Please describe what you want to watch or select a mood.');
      return;
    }

    setMoodError(null);
    setMoodLoading(true);
    setMoodFetched(true);
    try {
      const moodText = selectedMoods.join(', ') || undefined;
      const result = await apiClient.getRecommendations({
        user_id: user.user_id,
        top_k: MAX_RESULTS_PER_SECTION,
        mood: moodText,
        text: description.trim() || undefined,
      });
      setMoodResults((result.recommendations || []).slice(0, MAX_RESULTS_PER_SECTION));
    } catch (err) {
      if (err instanceof RecommendationAPIError) {
        setMoodError(err.message);
        const fallback = await fetchDramas(1, MAX_RESULTS_PER_SECTION, undefined, 'note_moyenne', 'desc');
        setMoodResults(fallback.items.slice(0, MAX_RESULTS_PER_SECTION));
      } else {
        setMoodError(err instanceof Error ? err.message : String(err));
      }
    } finally {
      setMoodLoading(false);
    }
  };

  const handleMoodToggle = (mood: string) => {
    setSelectedMoods(prev =>
      prev.includes(mood) ? prev.filter(m => m !== mood) : [...prev, mood]
    );
  };

  const toggleFav = (drama: Drama) => {
    if (!user) return;
    if (isFavorite(drama.id)) {
      const fav = favorites.find((f) => f.drama_id === drama.id);
      if (fav) removeFavorite(fav.id);
      flash(`Removed "${drama.title}" from your favorites.`, 'info');
    } else {
      addFavorite(drama);
      flash(`Added "${drama.title}" to your favorites.`, 'success');
    }
  };

  const handleAddToWatched = (drama: Drama) => {
    if (!user) {
      flash('Please sign in to track watched dramas.', 'info');
      nav('login');
      return;
    }
    setSelectedDrama(null);
    nav('history');
    flash(`Go to "My List" to rate "${drama.title}"`, 'info');
  };

  if (!user) {
    return (
      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-16 text-center">
        <Sparkles className="w-12 h-12 mx-auto mb-4 text-rose-400" aria-hidden="true" />
        <p className="text-gray-500 mb-4">Please sign in to access your recommendations.</p>
        <button onClick={() => nav('login')} className="text-rose-500 font-medium hover:text-rose-600">
          Sign in
        </button>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 py-8">
      <div className="text-center mb-10">
        <Sparkles className="w-10 h-10 mx-auto mb-3 text-rose-400" aria-hidden="true" />
        <h1 className="font-display text-3xl font-bold text-slate-800 mb-2">
          Your Recommendations
        </h1>
        <p className="text-gray-500 max-w-lg mx-auto text-sm">
          A short list of your best matches, based on your profile and history, plus mood-based
          picks whenever you want something different.
        </p>
      </div>

      {/* ------------------------------------------------------------------ */}
      {/* Section A — History / personalized recommendations (max 4)         */}
      {/* ------------------------------------------------------------------ */}
      <section aria-labelledby="personalized-title" className="mb-14">
        <div className="flex items-center gap-2 mb-1">
          <HistoryIcon className="w-5 h-5 text-rose-400" aria-hidden="true" />
          <h2 id="personalized-title" className="font-display text-xl font-bold text-slate-800">
            For You
          </h2>
        </div>
        <p className="text-sm text-gray-400 mb-5">
          Based on your profile, watch history, favorites and preferences.
        </p>

        {personalizedError && (
          <div
            role="alert"
            aria-live="assertive"
            className="mb-6 bg-red-50 border border-red-200 rounded-2xl p-4 flex items-center gap-3"
          >
            <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0" aria-hidden="true" />
            <p className="text-sm text-red-700 flex-1">{personalizedError}</p>
            <button
              onClick={fetchPersonalized}
              className="flex items-center gap-1 text-sm text-red-600 font-medium hover:text-red-700"
            >
              <RefreshCw className="w-4 h-4" aria-hidden="true" /> Retry
            </button>
          </div>
        )}

        {personalizedLoading ? (
          <LoadingSkeleton count={MAX_RESULTS_PER_SECTION} />
        ) : personalized.length > 0 ? (
          <div role="list" className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            {personalized.slice(0, MAX_RESULTS_PER_SECTION).map((d, i) => (
              <DramaCard
                key={d.id}
                drama={d}
                isFav={isFavorite(d.id)}
                onToggleFav={toggleFav}
                onViewDetails={setSelectedDrama}
                rank={i + 1}
                isWatched={isWatched(d.id)}
                explanation={d.explanation}
              />
            ))}
          </div>
        ) : personalizedFetched ? (
          <div className="text-center py-10 text-gray-400">
            <Sparkles className="w-10 h-10 mx-auto mb-3 opacity-40" aria-hidden="true" />
            <p>No personalized recommendations yet. Rate or favorite a few dramas to get started.</p>
          </div>
        ) : null}
      </section>

      {/* ------------------------------------------------------------------ */}
      {/* Section B — Chat / mood-based recommendations (max 4)              */}
      {/* ------------------------------------------------------------------ */}
      <section aria-labelledby="mood-title">
        <div className="flex items-center gap-2 mb-1">
          <Sparkles className="w-5 h-5 text-violet-400" aria-hidden="true" />
          <h2 id="mood-title" className="font-display text-xl font-bold text-slate-800">
            Chat &amp; Mood
          </h2>
        </div>
        <p className="text-sm text-gray-400 mb-5">
          Tell us what you're in the mood for right now.
        </p>

        <div className="mb-8 bg-white rounded-3xl border border-slate-100 shadow-soft p-6 sm:p-8">
          <div className="mb-6">
            <label htmlFor="description" className="sr-only">Describe what you want to watch</label>
            <div className="relative">
              <textarea
                id="description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="I want a drama with a slow-burn romance, something that makes me cry but has a happy ending..."
                className="w-full px-4 py-3 border-2 border-slate-200 rounded-2xl focus:border-rose-400 outline-none text-sm resize-none"
                rows={3}
              />
              <button
                onClick={handleGetMoodRecommendations}
                disabled={moodLoading}
                className="absolute bottom-2 right-2 p-2 bg-rose-500 text-white rounded-full hover:bg-rose-600 disabled:bg-gray-400 transition-colors"
                aria-label="Send request"
              >
                <Send className="w-4 h-4" aria-hidden="true" />
              </button>
            </div>
          </div>

          <div>
            <p className="text-sm text-gray-600 mb-3">Or pick a mood</p>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
              {MOOD_GENRES.map((mood) => (
                <button
                  key={mood.label}
                  onClick={() => handleMoodToggle(mood.label)}
                  className={`py-2 px-3 rounded-full text-sm font-medium transition-all ${
                    selectedMoods.includes(mood.label)
                      ? 'bg-rose-500 text-white'
                      : 'bg-rose-50 text-rose-600 border border-rose-200 hover:border-rose-400'
                  }`}
                >
                  <span className="mr-1">{mood.emoji}</span>
                  {mood.label}
                </button>
              ))}
            </div>
          </div>

          <button
            onClick={handleGetMoodRecommendations}
            disabled={moodLoading}
            className="w-full mt-6 py-3 px-4 bg-rose-500 text-white rounded-2xl font-medium hover:bg-rose-600 disabled:bg-gray-400 transition-colors flex items-center justify-center gap-2"
          >
            <Sparkles className="w-4 h-4" aria-hidden="true" />
            Get Recommendations
          </button>
        </div>

        {moodError && (
          <div
            role="alert"
            aria-live="assertive"
            className="mb-6 bg-red-50 border border-red-200 rounded-2xl p-4 flex items-center gap-3"
          >
            <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0" aria-hidden="true" />
            <p className="text-sm text-red-700 flex-1">{moodError}</p>
            <button
              onClick={handleGetMoodRecommendations}
              className="flex items-center gap-1 text-sm text-red-600 font-medium hover:text-red-700"
            >
              <RefreshCw className="w-4 h-4" aria-hidden="true" /> Retry
            </button>
          </div>
        )}

        {moodLoading ? (
          <LoadingSkeleton count={MAX_RESULTS_PER_SECTION} />
        ) : moodResults.length > 0 ? (
          <div role="list" className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            {moodResults.slice(0, MAX_RESULTS_PER_SECTION).map((d, i) => (
              <DramaCard
                key={d.id}
                drama={d}
                isFav={isFavorite(d.id)}
                onToggleFav={toggleFav}
                onViewDetails={setSelectedDrama}
                rank={i + 1}
                isWatched={isWatched(d.id)}
                explanation={d.explanation}
              />
            ))}
          </div>
        ) : moodFetched ? (
          <div className="text-center py-10 text-gray-400">
            <Sparkles className="w-10 h-10 mx-auto mb-3 opacity-40" aria-hidden="true" />
            <p>No recommendations found. Try adjusting your mood or description.</p>
          </div>
        ) : (
          <div className="text-center py-10 text-gray-400">
            <Sparkles className="w-10 h-10 mx-auto mb-3 opacity-40" aria-hidden="true" />
            <p>Enter a mood or describe what you want to watch to get started.</p>
          </div>
        )}
      </section>

      <DramaDetailModal
        drama={selectedDrama}
        isFav={selectedDrama ? isFavorite(selectedDrama.id) : false}
        onClose={() => setSelectedDrama(null)}
        onToggleFav={toggleFav}
        isWatched={selectedDrama ? isWatched(selectedDrama.id) : false}
        onAddToWatched={handleAddToWatched}
      />
    </div>
  );
}
