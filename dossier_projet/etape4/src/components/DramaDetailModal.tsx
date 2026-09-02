import { X, Heart, Star, Eye, ThumbsUp, ThumbsDown } from 'lucide-react';
import { useEffect, useState } from 'react';
import type { Drama } from '../types';
import { formatRating } from '../data';
import { useAuth } from '../auth';
import { dataApi } from '../api';

interface DramaDetailModalProps {
  drama: Drama | null;
  isFav: boolean;
  onClose: () => void;
  onToggleFav: (drama: Drama) => void;
  isWatched?: boolean;
  onAddToWatched?: (drama: Drama) => void;
  onInterestChange?: (dramaId: number, interesse: boolean) => void;
}

export function DramaDetailModal({
  drama,
  isFav,
  onClose,
  onToggleFav,
  isWatched = false,
  onAddToWatched,
  onInterestChange,
}: DramaDetailModalProps) {
  const { user } = useAuth();
  const [interest, setInterest] = useState<boolean | null>(null);
  const [savingInterest, setSavingInterest] = useState(false);

  // Load any existing "want to watch / not interested" feedback for this
  // drama whenever the modal opens on a new drama.
  useEffect(() => {
    setInterest(null);
    if (!drama || !user) return;
    let cancelled = false;
    dataApi
      .getInteret(drama.id)
      .then((res) => {
        if (!cancelled) setInterest(res ? res.interesse : null);
      })
      .catch(() => {
        if (!cancelled) setInterest(null);
      });
    return () => {
      cancelled = true;
    };
  }, [drama, user]);

  if (!drama) return null;

  const handleSetInterest = async (interesse: boolean) => {
    if (!user) return;
    setSavingInterest(true);
    try {
      await dataApi.setInteret(drama.id, interesse);
      setInterest(interesse);
      onInterestChange?.(drama.id, interesse);
      if (!interesse) onClose();
    } catch {
      // Non-blocking: feedback is a nice-to-have signal, failing silently
      // keeps the modal usable even if the API call fails.
    } finally {
      setSavingInterest(false);
    }
  };

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

              {user && (
                <div>
                  <p className="text-sm text-gray-500 mb-2">Want to watch this?</p>
                  <div className="grid grid-cols-2 gap-2">
                    <button
                      onClick={() => handleSetInterest(true)}
                      disabled={savingInterest}
                      aria-pressed={interest === true}
                      className={`py-2 px-3 rounded-xl font-medium text-sm transition-all flex items-center justify-center gap-1.5 disabled:opacity-50 ${
                        interest === true
                          ? 'bg-emerald-500 text-white hover:bg-emerald-600'
                          : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                      }`}
                    >
                      <ThumbsUp className="w-4 h-4" aria-hidden="true" />
                      Want to watch
                    </button>
                    <button
                      onClick={() => handleSetInterest(false)}
                      disabled={savingInterest}
                      aria-pressed={interest === false}
                      className={`py-2 px-3 rounded-xl font-medium text-sm transition-all flex items-center justify-center gap-1.5 disabled:opacity-50 ${
                        interest === false
                          ? 'bg-slate-500 text-white hover:bg-slate-600'
                          : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                      }`}
                    >
                      <ThumbsDown className="w-4 h-4" aria-hidden="true" />
                      Not interested
                    </button>
                  </div>
                </div>
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
