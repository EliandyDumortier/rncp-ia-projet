import { Sparkles, AlertCircle, RefreshCw } from 'lucide-react';
import { useState, useEffect, useCallback } from 'react';
import type { Drama, Recommendation, Page } from '../types';
import { fetchDramas } from '../data';
import { DramaCard } from '../components/DramaCard';
import { DramaDetailModal } from '../components/DramaDetailModal';
import { LoadingSkeleton } from '../components/LoadingSkeleton';
import { apiClient, RecommendationAPIError } from '../api';
import { useAuth } from '../auth';
import { useFavorites } from '../useFavorites';

interface RecommendationsPageProps {
  nav: (p: Page) => void;
}

export function RecommendationsPage({ nav }: RecommendationsPageProps) {
  const { user, flash } = useAuth();
  const { favorites, isFavorite, addFavorite, removeFavorite } = useFavorites(user?.user_id ?? null);
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<string>('user');
  const [selectedDrama, setSelectedDrama] = useState<Drama | null>(null);

  const fetchRecommendations = useCallback(async () => {
    if (!user) {
      flash('Please sign in to access your recommendations.', 'info');
      nav('login');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const result = await apiClient.getRecommendations(user.user_id, null, 10);
      setRecommendations(result.recommendations || []);
      setMode(result.mode || 'user');
    } catch (err) {
      if (err instanceof RecommendationAPIError) {
        setError(err.message);
        const fallback = await fetchDramas(1, 8, undefined, 'note_moyenne', 'desc');
        setRecommendations(fallback.items);
        setMode('fallback');
      } else {
        setError('An unexpected error occurred.');
      }
    } finally {
      setLoading(false);
    }
  }, [user, nav, flash]);

  useEffect(() => {
    fetchRecommendations();
  }, [fetchRecommendations]);

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
          {mode === 'fallback'
            ? 'Fallback mode — showing popular dramas (AI API unavailable).'
            : 'Our hybrid AI combines collaborative filtering and semantic analysis of synopses to suggest series tailored to your taste.'}
        </p>
      </div>

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
        <LoadingSkeleton count={8} />
      ) : (
        <div role="list" className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
          {recommendations.map((d, i) => (
            <DramaCard
              key={d.id}
              drama={d}
              isFav={isFavorite(d.id)}
              onToggleFav={toggleFav}
              onViewDetails={setSelectedDrama}
              rank={i + 1}
              predictedRating={d.predicted_rating}
              score={d.score}
            />
          ))}
        </div>
      )}

      <DramaDetailModal
        drama={selectedDrama}
        isFav={selectedDrama ? isFavorite(selectedDrama.id) : false}
        onClose={() => setSelectedDrama(null)}
        onToggleFav={toggleFav}
      />
    </div>
  );
}
