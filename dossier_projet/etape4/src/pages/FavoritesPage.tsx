import { Heart, Trash2 } from 'lucide-react';
import type { Page } from '../types';
import { useAuth } from '../auth';
import { useFavorites } from '../useFavorites';

interface FavoritesPageProps {
  nav: (p: Page) => void;
}

export function FavoritesPage({ nav }: FavoritesPageProps) {
  const { user, flash } = useAuth();
  const { favorites, removeFavorite } = useFavorites(user?.user_id ?? null);

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
        <ul className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4 list-none p-0">
          {favorites.map((fav) => (
            <li
              key={fav.id}
              className="group relative bg-white rounded-3xl overflow-hidden shadow-soft border border-slate-100 hover:shadow-card transition-all"
            >
              <div className="relative aspect-[2/3] overflow-hidden">
                <img
                  src={fav.drama_poster}
                  alt={`Affiche du K-Drama ${fav.drama_title}`}
                  loading="lazy"
                  className="w-full h-full object-cover"
                />
              </div>
              <div className="p-3">
                <h3 className="font-display font-semibold text-sm text-slate-800 line-clamp-1 mb-2">
                  {fav.drama_title}
                </h3>
                <button
                  onClick={() => {
                    removeFavorite(fav.id);
                    flash(`Removed "${fav.drama_title}" from your favorites.`, 'info');
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
      )}
    </div>
  );
}
