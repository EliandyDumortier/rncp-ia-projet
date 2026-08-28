import { Sparkles, AlertCircle, RefreshCw, Send, ArrowLeft } from 'lucide-react';
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
  const { watchedDramas, isWatched, addWatchedDrama } = useWatchedDramas(user?.user_id ?? null);

  const [description, setDescription] = useState('');
  const [selectedMoods, setSelectedMoods] = useState<string[]>([]);
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [historyRecommendations, setHistoryRecommendations] = useState<Recommendation[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedDrama, setSelectedDrama] = useState<Drama | null>(null);
  const [showingResults, setShowingResults] = useState(false);
  const [viewMode, setViewMode] = useState<'preferences' | 'history'>('preferences');

  const fetchRecommendations = useCallback(async () => {
    if (!user) {
      flash('Please sign in to access your recommendations.', 'info');
      nav('login');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const result = await apiClient.getRecommendations(user.user_id, null, 12);
      setRecommendations(result.recommendations || []);
    } catch (err) {
      if (err instanceof RecommendationAPIError) {
        setError(err.message);
        const fallback = await fetchDramas(1, 12, undefined, 'note_moyenne', 'desc');
        setRecommendations(fallback.items);
      } else {
        setError('An unexpected error occurred.');
      }
    } finally {
      setLoading(false);
    }
  }, [user, nav, flash]);

  const handleGetRecommendations = async () => {
    if (!user) {
      flash('Please sign in to get recommendations.', 'info');
      nav('login');
      return;
    }

    if (!description.trim() && selectedMoods.length === 0) {
      setError('Please describe what you want to watch or select a mood.');
      return;
    }

    setError(null);
    setShowingResults(true);
    setViewMode('preferences');
    await fetchRecommendations();
  };

  const fetchHistoryRecommendations = useCallback(async () => {
    if (!user || watchedDramas.length === 0) return;
    setLoading(true);
    setViewMode('history');
    setShowingResults(true);
    try {
      const result = await apiClient.getRecommendations(user.user_id, null, 12);
      setHistoryRecommendations(result.recommendations || []);
    } catch {
      const fallback = await fetchDramas(1, 12, undefined, 'note_moyenne', 'desc');
      setHistoryRecommendations(fallback.items);
    } finally {
      setLoading(false);
    }
  }, [user, watchedDramas]);

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
          Personalized Recommendations
        </h1>
        <p className="text-gray-500 max-w-lg mx-auto text-sm">
          Tell us what you're in the mood for and get AI-powered drama recommendations
        </p>
      </div>

      <div className="mb-10 bg-white rounded-3xl border border-slate-100 shadow-soft p-6 sm:p-8">
        <h2 className="text-lg font-semibold text-slate-800 mb-4">Tell us what you're in the mood for</h2>

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
              onClick={handleGetRecommendations}
              disabled={loading}
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
          onClick={handleGetRecommendations}
          disabled={loading}
          className="w-full mt-6 py-3 px-4 bg-rose-500 text-white rounded-2xl font-medium hover:bg-rose-600 disabled:bg-gray-400 transition-colors flex items-center justify-center gap-2"
        >
          <Sparkles className="w-4 h-4" aria-hidden="true" />
          Get Recommendations
        </button>
      </div>

      {(recommendations.length > 0 || historyRecommendations.length > 0) && (
        <div className="mb-6 border-b border-slate-200">
          <div className="flex gap-4">
            <button
              onClick={() => setViewMode('preferences')}
              className={`py-3 px-4 font-medium transition-colors ${
                viewMode === 'preferences'
                  ? 'text-rose-500 border-b-2 border-rose-500'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              Based on Your Preferences
            </button>
            {watchedDramas.length > 0 && (
              <button
                onClick={() => fetchHistoryRecommendations()}
                className={`py-3 px-4 font-medium transition-colors ${
                  viewMode === 'history'
                    ? 'text-rose-500 border-b-2 border-rose-500'
                    : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                Based on Your Watch History
              </button>
            )}
          </div>
        </div>
      )}

      {error && (
        <div
          role="alert"
          aria-live="assertive"
          className="mb-6 bg-red-50 border border-red-200 rounded-2xl p-4 flex items-center gap-3"
        >
          <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0" aria-hidden="true" />
          <p className="text-sm text-red-700 flex-1">{error}</p>
          <button
            onClick={fetchRecommendations}
            className="flex items-center gap-1 text-sm text-red-600 font-medium hover:text-red-700"
          >
            <RefreshCw className="w-4 h-4" aria-hidden="true" /> Retry
          </button>
        </div>
      )}

      {loading ? (
        <LoadingSkeleton count={12} />
      ) : showingResults && ((viewMode === 'preferences' && recommendations.length > 0) || (viewMode === 'history' && historyRecommendations.length > 0)) ? (
        <div role="list" className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
          {(viewMode === 'preferences' ? recommendations : historyRecommendations).map((d, i) => (
            <DramaCard
              key={d.id}
              drama={d}
              isFav={isFavorite(d.id)}
              onToggleFav={toggleFav}
              onViewDetails={setSelectedDrama}
              rank={i + 1}
              predictedRating={d.predicted_rating}
              score={d.score}
              isWatched={isWatched(d.id)}
            />
          ))}
        </div>
      ) : showingResults ? (
        <div className="text-center py-12 text-gray-400">
          <Sparkles className="w-12 h-12 mx-auto mb-4 opacity-40" aria-hidden="true" />
          <p>No recommendations found. Try adjusting your preferences.</p>
        </div>
      ) : (
        <div className="text-center py-12 text-gray-400">
          <Sparkles className="w-12 h-12 mx-auto mb-4 opacity-40" aria-hidden="true" />
          <p>Enter your preferences to get AI recommendations</p>
        </div>
      )}

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
