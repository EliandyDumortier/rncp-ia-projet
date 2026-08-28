import { TrendingUp, ArrowRight, Sparkles, Star } from 'lucide-react';
import type { Drama, Page } from '../types';
import { dramas, carouselSlides, fetchDramas } from '../data';
import { DramaCard } from '../components/DramaCard';
import { DramaDetailModal } from '../components/DramaDetailModal';
import { FeatureCarousel } from '../components/FeatureCarousel';
import { LoadingSkeleton } from '../components/LoadingSkeleton';
import { useAuth } from '../auth';
import { useFavorites } from '../useFavorites';
import { useWatchedDramas } from '../useWatchedDramas';
import { useState, useEffect, useCallback } from 'react';

interface HomePageProps {
  nav: (p: Page) => void;
}

export function HomePage({ nav }: HomePageProps) {
  const { user, flash } = useAuth();
  const { favorites, isFavorite, addFavorite, removeFavorite } = useFavorites(user?.user_id ?? null);
  const { isWatched, addWatchedDrama } = useWatchedDramas(user?.user_id ?? null);
  const [carouselIndex, setCarouselIndex] = useState(0);
  const [popular, setPopular] = useState<Drama[]>([]);
  const [loading, setLoading] = useState(true);
  const [fallback, setFallback] = useState(false);
  const [selectedDrama, setSelectedDrama] = useState<Drama | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      const result = await fetchDramas(1, 6, undefined, 'note_moyenne', 'desc');
      if (!cancelled) {
        setPopular(result.items);
        setFallback(result.fallback);
        setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const nextSlide = useCallback(() => setCarouselIndex((i) => (i + 1) % carouselSlides.length), []);
  const prevSlide = useCallback(() => setCarouselIndex((i) => (i - 1 + carouselSlides.length) % carouselSlides.length), []);

  useEffect(() => {
    const timer = setInterval(nextSlide, 5000);
    return () => clearInterval(timer);
  }, [nextSlide]);

  const toggleFav = (drama: Drama) => {
    if (!user) {
      flash('Please sign in to manage your favorites.', 'info');
      nav('login');
      return;
    }
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
    addWatchedDrama(drama, 0, '');
    flash(`Added "${drama.title}" to your watch list! Rate it in "My List".`, 'success');
  };

  return (
    <div>
      <FeatureCarousel
        slides={carouselSlides}
        index={carouselIndex}
        onNext={nextSlide}
        onPrev={prevSlide}
        onGoTo={setCarouselIndex}
        onCtaClick={() => nav('recommendations')}
      />

      <div className="max-w-6xl mx-auto px-4 sm:px-6">
        <section aria-labelledby="trending-title" className="grid grid-cols-3 gap-4 -mt-8 relative z-10 mb-12">
          {[
            { label: 'Dramas', value: fallback ? `${dramas.length}+` : 'API', icon: <Star className="w-5 h-5 text-rose-400" /> },
            { label: 'Genres', value: '10', icon: <Sparkles className="w-5 h-5 text-pink-400" /> },
            { label: 'IA', value: '100%', icon: <TrendingUp className="w-5 h-5 text-orange-400" /> },
          ].map((s) => (
            <div key={s.label} className="bg-white rounded-2xl p-4 shadow-soft text-center">
              <div className="flex justify-center mb-1">{s.icon}</div>
              <p className="font-display font-bold text-xl text-gray-800">{s.value}</p>
              <p className="text-xs text-gray-500">{s.label}</p>
            </div>
          ))}
        </section>

        <section aria-labelledby="trending-title" className="mb-16">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h2 id="trending-title" className="font-display text-2xl font-bold text-slate-800 flex items-center gap-2">
                <TrendingUp className="w-5 h-5 text-rose-400" aria-hidden="true" /> Popular Dramas
              </h2>
              <p className="text-sm text-gray-400 mt-1">
                {fallback ? 'Local catalog (data API unavailable)' : 'Top-rated K-Dramas'}
              </p>
            </div>
            <button
              onClick={() => nav('search')}
              className="text-sm text-rose-500 font-medium hover:text-rose-600 flex items-center gap-1"
            >
              View all <ArrowRight className="w-4 h-4" aria-hidden="true" />
            </button>
          </div>
          {loading ? (
            <LoadingSkeleton count={6} />
          ) : (
            <div role="list" className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
              {popular.map((d) => (
                <DramaCard
                  key={d.id}
                  drama={d}
                  isFav={isFavorite(d.id)}
                  onToggleFav={toggleFav}
                  onViewDetails={setSelectedDrama}
                  isWatched={isWatched(d.id)}
                />
              ))}
            </div>
          )}
        </section>

        <section
          aria-label="Recommandations IA"
          className="bg-gradient-to-br from-rose-500 to-pink-600 rounded-3xl p-8 sm:p-12 mb-16 text-center text-white"
        >
          <Sparkles className="w-10 h-10 mx-auto mb-4 text-rose-200" aria-hidden="true" />
          <h2 className="font-display text-2xl sm:text-3xl font-bold mb-3">
            Let AI find your next drama
          </h2>
          <p className="text-rose-100 max-w-md mx-auto mb-6 text-sm leading-relaxed">
            Describe your mood, favorite tropes, or dramas you enjoyed — our AI gives you personalized recommendations.
          </p>
          <button
            onClick={() => nav('recommendations')}
            className="bg-white text-rose-600 hover:bg-rose-50 font-semibold px-8 py-3 rounded-2xl transition-all hover:shadow-card active:scale-95"
          >
            Try recommendations
          </button>
        </section>
      </div>

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
