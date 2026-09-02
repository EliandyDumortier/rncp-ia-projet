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
// section (history/personalized and explore/mood-keywords).
const MAX_RESULTS_PER_SECTION = 4;
// Fetch a much larger buffer so that "not interested" exclusions don't leave
// you with too few results. We fetch 10x the display size so even if many are
// marked disliked, we still have enough to show.
const POOL_BUFFER_SIZE = MAX_RESULTS_PER_SECTION * 10;

const HISTORY_RECOMMENDATION_MESSAGE =
  'Recommended from your preferences and watch history.';
const SELECTION_RECOMMENDATION_MESSAGE =
  'Matches your current mood and keyword selection.';

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
  // Dramas marked "not interested" during this session: hidden immediately
  // client-side (backfilled from the pool below), in addition to being
  // excluded server-side on future requests.
  const [hiddenIds, setHiddenIds] = useState<Set<number>>(new Set());

  const personalizedVisible = personalized
    .filter((d) => !hiddenIds.has(d.id))
    .slice(0, MAX_RESULTS_PER_SECTION);
  const moodVisible = moodResults
    .filter((d) => !hiddenIds.has(d.id))
    .slice(0, MAX_RESULTS_PER_SECTION);

  const handleInterestChange = (dramaId: number, interesse: boolean) => {
    if (interesse) return;
    setHiddenIds((prev) => new Set(prev).add(dramaId));
  };

  // If hiding a drama exhausts the local pool's buffer, top up from the
  // server in the background (rare — only after several dislikes in a row).
  useEffect(() => {
    if (personalizedFetched && !personalizedLoading && personalizedVisible.length < MAX_RESULTS_PER_SECTION) {
      fetchPersonalized();
    }
    if (moodFetched && !moodLoading && moodVisible.length < MAX_RESULTS_PER_SECTION) {
      handleGetMoodRecommendations();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hiddenIds]);

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
        top_k: POOL_BUFFER_SIZE,
      });
      setPersonalized((result.recommendations || []).slice(0, POOL_BUFFER_SIZE));
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

  // Explore recommendations: mood + keywords.
  // Both are optional; you can use mood alone, keywords alone, or combine them.
  const handleGetMoodRecommendations = async () => {
    if (!user) {
      flash('Please sign in to get recommendations.', 'info');
      nav('login');
      return;
    }

    if (!description.trim() && selectedMoods.length === 0) {
      setMoodError('Select a mood or enter keywords (island, doctors, friendship, etc.).');
      return;
    }

    setMoodError(null);
    setMoodLoading(true);
    setMoodFetched(true);
    try {
      const moodText = selectedMoods.join(', ') || undefined;
      const result = await apiClient.getRecommendations({
        top_k: POOL_BUFFER_SIZE,
        mood: moodText,
        text: description.trim() || undefined,
      });
      setMoodResults((result.recommendations || []).slice(0, POOL_BUFFER_SIZE));
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
          Recommendations based on your preferences, favorites, and watch history.
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
        ) : personalizedVisible.length > 0 ? (
          <div role="list" className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            {personalizedVisible.map((d, i) => (
              <DramaCard
                key={d.id}
                drama={d}
                isFav={isFavorite(d.id)}
                onToggleFav={toggleFav}
                onViewDetails={setSelectedDrama}
                rank={i + 1}
                isWatched={isWatched(d.id)}
                explanation={HISTORY_RECOMMENDATION_MESSAGE}
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
      {/* Section B — Explore by mood & keywords                             */}
      {/* ------------------------------------------------------------------ */}
      <section aria-labelledby="mood-title">
        <div className="flex items-center gap-2 mb-1">
          <Sparkles className="w-5 h-5 text-violet-400" aria-hidden="true" />
          <h2 id="mood-title" className="font-display text-xl font-bold text-slate-800">
            Explore by Mood &amp; Keywords
          </h2>
        </div>
        <p className="text-sm text-gray-400 mb-5">
          Based on what you asked for — mood, keywords, or both.
        </p>

        <div className="mb-8 bg-white rounded-3xl border border-slate-100 shadow-soft p-6 sm:p-8">
          <div className="mb-8">
            <p className="text-sm text-gray-600 mb-3 font-medium">1. Select a mood (optional)</p>
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

          <div className="mb-6">
            <label htmlFor="description" className="text-sm text-gray-600 mb-3 font-medium block">
              2. Or enter keywords (optional)
            </label>
            <div className="relative">
              <textarea
                id="description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="island, doctors, friendship, slow-burn romance..."
                className="w-full px-4 py-3 border-2 border-slate-200 rounded-2xl focus:border-rose-400 outline-none text-sm resize-none"
                rows={2}
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
        ) : moodVisible.length > 0 ? (
          <div role="list" className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            {moodVisible.map((d, i) => (
              <DramaCard
                key={d.id}
                drama={d}
                isFav={isFavorite(d.id)}
                onToggleFav={toggleFav}
                onViewDetails={setSelectedDrama}
                rank={i + 1}
                isWatched={isWatched(d.id)}
                explanation={SELECTION_RECOMMENDATION_MESSAGE}
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
        onInterestChange={handleInterestChange}
      />
    </div>
  );
}
