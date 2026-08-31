import { Trash2, Star, Plus } from 'lucide-react';
import { useState, useEffect } from 'react';
import type { Drama, Page } from '../types';
import { fetchDramas, fetchDramaByTitle } from '../data';
import { useAuth } from '../auth';
import { useWatchedDramas } from '../useWatchedDramas';
import { useFavorites } from '../useFavorites';
import { DramaDetailModal } from '../components/DramaDetailModal';
import { LoadingSkeleton } from '../components/LoadingSkeleton';

interface HistoryPageProps {
  nav: (p: Page) => void;
}

export function HistoryPage({ nav }: HistoryPageProps) {
  const { user, flash } = useAuth();
  const { watched, addWatchedDrama, removeWatchedDrama, getWatchedDrama } = useWatchedDramas(
    user?.user_id ?? null
  );
  const { favorites, isFavorite, addFavorite, removeFavorite } = useFavorites(user?.user_id ?? null);
  const [allDramas, setAllDramas] = useState<Drama[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedDrama, setSelectedDrama] = useState<Drama | null>(null);
  const [selectedDetailDrama, setSelectedDetailDrama] = useState<Drama | null>(null);
  const [rating, setRating] = useState(0);
  const [notes, setNotes] = useState('');
  const [showForm, setShowForm] = useState(false);

  useEffect(() => {
    const loadDramas = async () => {
      const result = await fetchDramas(1, 1000, undefined, 'titre', 'asc');
      setAllDramas(result.items);
      setLoading(false);
    };
    loadDramas();
  }, []);

  const handleAddDrama = (drama: Drama) => {
    const existing = getWatchedDrama(drama.id);
    setSelectedDrama(drama);
    setRating(existing?.rating ?? 0);
    setNotes(existing?.notes ?? '');
    setShowForm(true);
  };

  const handleSaveRating = () => {
    if (!selectedDrama) return;
    addWatchedDrama(selectedDrama, rating, notes);
    flash(
      rating === 0
        ? `Added "${selectedDrama.title}" to your watched list!`
        : `Saved rating for "${selectedDrama.title}"!`,
      'success'
    );
    setShowForm(false);
    setRating(0);
    setNotes('');
    setSelectedDrama(null);
  };

  const toggleFav = (drama: Drama) => {
    if (!user) {
      flash('Please sign in to manage favorites.', 'info');
      nav('login');
      return;
    }
    if (isFavorite(drama.id)) {
      const fav = favorites.find((f) => f.drama_id === drama.id);
      if (fav) removeFavorite(fav.id);
      flash(`Removed "${drama.title}" from favorites.`, 'info');
    } else {
      addFavorite(drama);
      flash(`Added "${drama.title}" to favorites.`, 'success');
    }
  };

  if (!user) {
    return (
      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-16 text-center">
        <Star className="w-12 h-12 mx-auto mb-4 text-rose-400" aria-hidden="true" />
        <p className="text-gray-500 mb-4">Please sign in to track your watched dramas.</p>
        <button onClick={() => nav('login')} className="text-rose-500 font-medium hover:text-rose-600">
          Sign in
        </button>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 py-8">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="font-display text-3xl font-bold text-slate-800 mb-2">My Watched Dramas</h1>
          <p className="text-gray-500">Rate the dramas you've watched to improve recommendations</p>
        </div>
        <button
          onClick={() => nav('search')}
          className="flex items-center gap-2 bg-rose-500 text-white px-6 py-3 rounded-2xl font-semibold hover:bg-rose-600 transition-colors"
        >
          <Plus className="w-4 h-4" /> Add Drama
        </button>
      </div>

      {showForm && (
        <div className="bg-white rounded-3xl shadow-lg p-6 mb-8 border border-slate-100">
          <h2 className="font-display text-xl font-bold mb-4 text-slate-800">
            {selectedDrama ? `Rate "${selectedDrama.title}"` : 'Add a Drama to Your Watched List'}
          </h2>

          {!selectedDrama ? (
            <div className="mb-4">
              <input
                type="text"
                placeholder="Search for a drama..."
                className="w-full px-4 py-2 border-2 border-slate-200 rounded-xl focus:border-rose-400 outline-none mb-4"
                onChange={(e) => {
                  if (!e.target.value) return;
                }}
              />
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 max-h-96 overflow-y-auto">
                {allDramas.slice(0, 20).map((d) => (
                  <button
                    key={d.id}
                    onClick={() => handleAddDrama(d)}
                    className="text-left hover:opacity-80 transition-opacity"
                  >
                    <img src={d.poster} alt={d.title} className="w-full rounded-lg mb-2" />
                    <p className="text-sm font-medium text-slate-700 line-clamp-2">{d.title}</p>
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="flex gap-4">
                <img
                  src={selectedDrama.poster}
                  alt={selectedDrama.title}
                  className="w-24 h-36 object-cover rounded-lg"
                />
                <div className="flex-1">
                  <p className="text-sm text-gray-500 mb-1">Rating</p>
                  <div className="flex gap-1 mb-4">
                    {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((num) => (
                      <button
                        key={num}
                        onClick={() => setRating(num)}
                        className={`w-8 h-8 rounded-lg font-semibold transition-colors ${
                          rating >= num
                            ? 'bg-rose-500 text-white'
                            : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                        }`}
                      >
                        {num}
                      </button>
                    ))}
                  </div>

                  <p className="text-sm text-gray-500 mb-1">Notes</p>
                  <textarea
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                    placeholder="What did you think about this drama?"
                    className="w-full px-3 py-2 border-2 border-slate-200 rounded-lg focus:border-rose-400 outline-none resize-none h-16 text-sm"
                  />
                </div>
              </div>

              <div className="flex gap-2 justify-end">
                <button
                  onClick={() => {
                    setShowForm(false);
                    setSelectedDrama(null);
                    setRating(0);
                    setNotes('');
                  }}
                  className="px-4 py-2 text-slate-700 bg-slate-100 rounded-lg hover:bg-slate-200 transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={handleSaveRating}
                  className="px-4 py-2 bg-rose-500 text-white rounded-lg hover:bg-rose-600 transition-colors font-semibold"
                >
                  {rating === 0 ? 'Save' : 'Save Rating'}
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {loading ? (
        <LoadingSkeleton count={6} />
      ) : watched.length === 0 ? (
        <div className="text-center py-16">
          <Star className="w-12 h-12 mx-auto mb-4 text-rose-400 opacity-40" aria-hidden="true" />
          <h2 className="text-xl font-semibold text-slate-800 mb-2">No dramas added yet</h2>
          <p className="text-gray-500 mb-6">Start adding dramas to your watchlist to track ratings and get personalized recommendations</p>
          <button
            onClick={() => nav('search')}
            className="inline-flex items-center gap-2 bg-rose-500 text-white px-6 py-3 rounded-2xl font-semibold hover:bg-rose-600 transition-colors"
          >
            <Plus className="w-4 h-4" /> Add Your First Drama
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {watched.map((w) => (
            <div
              key={w.id}
              className="bg-white rounded-3xl shadow-soft border border-slate-100 p-4 hover:shadow-card transition-all"
            >
              <div className="flex gap-4">
                <img
                  src={w.drama_poster}
                  alt={w.drama_title}
                  className="w-20 h-32 object-cover rounded-lg flex-shrink-0 cursor-pointer hover:opacity-80 transition-opacity"
                  onClick={async () => {
                    const fullDrama = await fetchDramaByTitle(w.drama_title);
                    if (fullDrama) {
                      setSelectedDetailDrama(fullDrama);
                    }
                  }}
                />
                <div className="flex-1 min-w-0">
                  <h3
                    className="font-display font-bold text-slate-800 line-clamp-2 mb-2 cursor-pointer hover:text-rose-600 transition-colors"
                    onClick={async () => {
                      const fullDrama = await fetchDramaByTitle(w.drama_title);
                      if (fullDrama) {
                        setSelectedDetailDrama(fullDrama);
                      }
                    }}
                  >
                    {w.drama_title}
                  </h3>

                  <div className="flex gap-1 mb-3">
                    {[1, 2, 3, 4, 5].map((num) => (
                      <Star
                        key={num}
                        className={`w-4 h-4 ${
                          w.rating > 0 && num <= Math.round(w.rating / 2)
                            ? 'text-amber-400 fill-amber-400'
                            : 'text-gray-300'
                        }`}
                      />
                    ))}
                  </div>

                  <p className="text-sm font-semibold mb-1">
                    {w.rating > 0 ? (
                      <span className="text-rose-600">{w.rating}/10</span>
                    ) : (
                      <span className="text-gray-400">Not rated yet</span>
                    )}
                  </p>

                  {w.notes && (
                    <p className="text-xs text-gray-600 line-clamp-2 mb-2">"{w.notes}"</p>
                  )}

                  <p className="text-xs text-gray-400 mb-3">{w.watched_date}</p>

                  <div className="flex gap-2">
                    <button
                      onClick={() => handleAddDrama({
                        id: w.drama_id,
                        title: w.drama_title,
                        poster: w.drama_poster,
                        genres: [],
                        rating: w.rating,
                        year: 0,
                        episodes: 0,
                        synopsis: ''
                      })}
                      className="flex-1 px-2 py-1 text-xs bg-slate-100 text-slate-700 rounded-lg hover:bg-slate-200 transition-colors"
                    >
                      {w.rating > 0 ? 'Edit' : 'Add Rating'}
                    </button>
                    <button
                      onClick={() => {
                        removeWatchedDrama(w.id);
                        flash('Removed from watched list.', 'info');
                      }}
                      className="px-2 py-1 text-xs bg-red-50 text-red-600 rounded-lg hover:bg-red-100 transition-colors"
                    >
                      <Trash2 className="w-3 h-3" />
                    </button>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      <DramaDetailModal
        drama={selectedDetailDrama}
        isFav={selectedDetailDrama ? isFavorite(selectedDetailDrama.id) : false}
        onClose={() => setSelectedDetailDrama(null)}
        onToggleFav={toggleFav}
        isWatched={selectedDetailDrama ? true : false}
      />
    </div>
  );
}
