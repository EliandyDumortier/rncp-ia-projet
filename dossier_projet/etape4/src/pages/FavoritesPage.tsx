import { Heart, Trash2 } from 'lucide-react';
import { useState } from 'react';
import type { Drama, Page } from '../types';
import { useAuth } from '../auth';
import { useFavorites } from '../useFavorites';
import { useWatchedDramas } from '../useWatchedDramas';
import { DramaDetailModal } from '../components/DramaDetailModal';

interface FavoritesPageProps {
  nav: (p: Page) => void;
}

export function FavoritesPage({ nav }: FavoritesPageProps) {
  const { user, flash } = useAuth();
  const { favorites, removeFavorite, isFavorite, addFavorite } = useFavorites(user?.user_id ?? null);
  const { isWatched, addWatchedDrama } = useWatchedDramas(user?.user_id ?? null);
  const [selectedDrama, setSelectedDrama] = useState<Drama | null>(null);

  const handleRemoveFavorite = (favId: number, title: string) => {
    removeFavorite(favId);
    flash(`Removed "${title}" from your favorites.`, 'info');
  };

  const toggleFav = (drama: Drama) => {
    if (isFavorite(drama.id)) {
      const fav = favorites.find((f) => f.drama_id === drama.id);
      if (fav) handleRemoveFavorite(fav.id, drama.title);
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

  if (!user) {
    return (
      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-16 text-center">
        <Heart className="w-12 h-12 mx-auto mb-4 text-rose-400" aria-hidden="true" />
        <p className="text-gray-500 mb-4">Please sign in to manage your favorites.</p>
        <button onClick={() => nav('login')} className="text-rose-500 font-medium hover:text-rose-600">
          Sign in
        </button>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 py-8">
      <h1 className="font-display text-2xl font-bold text-slate-800 mb-6 flex items-center gap-2">
        <Heart className="w-5 h-5 text-rose-500" aria-hidden="true" /> My Favorites
      </h1>

      {favorites.length === 0 ? (
        <div className="text-center py-16 text-gray-400">
          <Heart className="w-12 h-12 mx-auto mb-4 opacity-40" aria-hidden="true" />
          <p className="mb-4">You don't have any favorites yet.</p>
          <button onClick={() => nav('search')} className="text-rose-500 font-medium hover:text-rose-600">
            Discover K-Dramas
          </button>
        </div>
      ) : (
        <>
          <ul className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4 list-none p-0">
            {favorites.map((fav) => (
              <li
                key={fav.id}
                className="group relative bg-white rounded-3xl overflow-hidden shadow-soft border border-slate-100 hover:shadow-card transition-all cursor-pointer hover:-translate-y-1"
                onClick={() => setSelectedDrama({
                  id: fav.drama_id,
                  title: fav.drama_title,
                  poster: fav.drama_poster,
                  genres: [],
                  rating: 0,
                  year: 0,
                  episodes: 0,
                  synopsis: ''
                })}
              >
                <div className="relative aspect-[2/3] overflow-hidden">
                  <img
                    src={fav.drama_poster}
                    alt={`Affiche du K-Drama ${fav.drama_title}`}
                    loading="lazy"
                    className="w-full h-full object-cover group-hover:scale-105 transition-transform"
                  />
                </div>
                <div className="p-3">
                  <h3 className="font-display font-semibold text-sm text-slate-800 line-clamp-1 mb-2">
                    {fav.drama_title}
                  </h3>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleRemoveFavorite(fav.id, fav.drama_title);
                    }}
                    className="flex items-center gap-1 text-xs text-red-500 font-medium hover:text-red-600"
                    aria-label={`Remove ${fav.drama_title} from favorites`}
                  >
                    <Trash2 className="w-3.5 h-3.5" aria-hidden="true" /> Remove
                  </button>
                </div>
              </li>
            ))}
          </ul>

          <DramaDetailModal
            drama={selectedDrama}
            isFav={selectedDrama ? isFavorite(selectedDrama.id) : false}
            onClose={() => setSelectedDrama(null)}
            onToggleFav={toggleFav}
            isWatched={selectedDrama ? isWatched(selectedDrama.id) : false}
            onAddToWatched={handleAddToWatched}
          />
        </>
      )}
    </div>
  );
}
