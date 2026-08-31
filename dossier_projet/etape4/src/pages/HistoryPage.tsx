import { Trash2, Star, Plus } from 'lucide-react';
import { useAuth } from '../auth';
import { useWatchedDramas } from '../useWatchedDramas';
import { LoadingSkeleton } from '../components/LoadingSkeleton';

interface HistoryPageProps {
  nav: (p: Page) => void;
}

export function HistoryPage({ nav }: HistoryPageProps) {
  const { user, flash } = useAuth();
  const { watched, removeWatchedDrama } = useWatchedDramas(
    user?.user_id ?? null
  );

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

      {watched.length === 0 ? (
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
                  className="w-20 h-32 object-cover rounded-lg flex-shrink-0"
                />
                <div className="flex-1 min-w-0">
                  <h3 className="font-display font-bold text-slate-800 line-clamp-2 mb-2">
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

                  <div className="flex gap-2 justify-end">
                    <button
                      onClick={() => {
                        removeWatchedDrama(w.id);
                        flash('Removed from watched list.', 'info');
                      }}
                      className="px-3 py-1 text-xs bg-red-50 text-red-600 rounded-lg hover:bg-red-100 transition-colors flex items-center gap-1"
                    >
                      <Trash2 className="w-3 h-3" /> Remove
                    </button>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
