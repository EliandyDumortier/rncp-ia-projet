import { X, Heart, Star, Eye } from 'lucide-react';
import type { Drama } from '../types';
import { formatRating } from '../data';

interface DramaDetailModalProps {
  drama: Drama | null;
  isFav: boolean;
  onClose: () => void;
  onToggleFav: (drama: Drama) => void;
  isWatched?: boolean;
  onAddToWatched?: (drama: Drama) => void;
}

export function DramaDetailModal({
  drama,
  isFav,
  onClose,
  onToggleFav,
  isWatched = false,
  onAddToWatched,
}: DramaDetailModalProps) {
  if (!drama) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
      <div className="bg-white rounded-3xl shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        <div className="sticky top-0 bg-white border-b border-slate-100 flex items-center justify-between p-4">
          <h2 className="font-display text-xl font-bold text-slate-800">{drama.title}</h2>
          <button
            onClick={onClose}
            className="p-2 hover:bg-slate-100 rounded-full transition-colors"
            aria-label="Close details"
          >
            <X className="w-5 h-5 text-slate-600" />
          </button>
        </div>

        <div className="p-6">
          <div className="grid grid-cols-3 gap-4 mb-6">
            <div className="col-span-1">
              <img
                src={drama.poster}
                alt={`Poster of K-Drama ${drama.title}`}
                className="w-full rounded-2xl shadow-lg"
              />
            </div>
            <div className="col-span-2 space-y-4">
              <div>
                <p className="text-sm text-gray-500 mb-1">Rating</p>
                <div className="flex items-center gap-2">
                  <div className="flex gap-1">
                    {[...Array(5)].map((_, i) => (
                      <Star
                        key={i}
                        className={`w-4 h-4 ${
                          i < Math.round(drama.rating / 2)
                            ? 'text-amber-400 fill-amber-400'
                            : 'text-gray-300'
                        }`}
                      />
                    ))}
                  </div>
                  <span className="font-semibold text-slate-800">
                    {formatRating(drama.rating)}
                  </span>
                </div>
              </div>

              <div>
                <p className="text-sm text-gray-500 mb-1">Year</p>
                <p className="font-semibold text-slate-800">{drama.year}</p>
              </div>

              <div>
                <p className="text-sm text-gray-500 mb-1">Episodes</p>
                <p className="font-semibold text-slate-800">{drama.episodes}</p>
              </div>

              <div>
                <p className="text-sm text-gray-500 mb-2">Genres</p>
                <div className="flex flex-wrap gap-2">
                  {drama.genres.map((g) => (
                    <span
                      key={g}
                      className="px-3 py-1 bg-rose-50 text-rose-600 rounded-full text-xs font-medium"
                    >
                      {g}
                    </span>
                  ))}
                </div>
              </div>

              <button
                onClick={() => onToggleFav(drama)}
                className={`w-full py-2 px-4 rounded-xl font-semibold transition-all flex items-center justify-center gap-2 ${
                  isFav
                    ? 'bg-rose-500 text-white hover:bg-rose-600'
                    : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                }`}
              >
                <Heart
                  className={`w-4 h-4 ${isFav ? 'fill-current' : ''}`}
                />
                {isFav ? 'Remove from Favorites' : 'Add to Favorites'}
              </button>

              {onAddToWatched && (
                <button
                  onClick={() => onAddToWatched(drama)}
                  className={`w-full py-2 px-4 rounded-xl font-semibold transition-all flex items-center justify-center gap-2 ${
                    isWatched
                      ? 'bg-violet-500 text-white hover:bg-violet-600'
                      : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                  }`}
                >
                  <Eye className="w-4 h-4" />
                  {isWatched ? 'Already Watched' : 'Add to Watched List'}
                </button>
              )}
            </div>
          </div>

          <div>
            <h3 className="font-display font-bold text-slate-800 mb-3">Synopsis</h3>
            <p className="text-slate-600 leading-relaxed text-sm">
              {drama.synopsis || 'No synopsis available.'}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
