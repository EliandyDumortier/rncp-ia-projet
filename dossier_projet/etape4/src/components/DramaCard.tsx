import { Star, Heart, Eye } from 'lucide-react';
import type { Drama } from '../types';
import { formatRating } from '../data';

interface DramaCardProps {
  drama: Drama;
  isFav: boolean;
  onToggleFav: (drama: Drama) => void;
  onViewDetails?: (drama: Drama) => void;
  showAddButton?: boolean;
  rank?: number;
  predictedRating?: number;
  score?: number;
  isWatched?: boolean;
  explanation?: string;
}

export function DramaCard({
  drama,
  isFav,
  onToggleFav,
  onViewDetails,
  showAddButton = true,
  rank,
  predictedRating,
  score,
  isWatched = false,
  explanation,
}: DramaCardProps) {
  const handleCardClick = () => {
    if (onViewDetails) {
      onViewDetails(drama);
    }
  };

  return (
    <div
      role="listitem"
      className="group relative bg-white rounded-3xl overflow-hidden shadow-soft border border-slate-100 hover:shadow-card transition-all hover:-translate-y-1 cursor-pointer"
      onClick={handleCardClick}
    >
      {rank !== undefined && (
        <span className="absolute -top-2 -left-2 z-10 w-7 h-7 rounded-full bg-rose-500 text-white text-xs font-bold flex items-center justify-center shadow-soft">
          {rank}
        </span>
      )}
      {isWatched && (
        <span className="absolute top-2 left-2 z-10 flex items-center gap-1 px-2 py-1 rounded-full bg-violet-500/90 text-white text-xs font-medium backdrop-blur-sm shadow-soft">
          <Eye className="w-3 h-3" aria-hidden="true" />
          Watched
        </span>
      )}
      <div className="relative aspect-[2/3] overflow-hidden">
        <img
          src={drama.poster}
          alt={`Poster of K-Drama ${drama.title}`}
          loading="lazy"
          className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
        />
        {showAddButton && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              onToggleFav(drama);
            }}
            className="absolute top-2 right-2 w-9 h-9 rounded-full bg-white/90 backdrop-blur-sm flex items-center justify-center shadow-soft transition-all hover:scale-110"
            aria-label={isFav ? `Remove ${drama.title} from favorites` : `Add ${drama.title} to favorites`}
          >
            <Heart
              className={`w-4 h-4 transition-colors ${isFav ? 'text-rose-500 fill-rose-500' : 'text-gray-400'}`}
            />
          </button>
        )}
      </div>
      <div className="p-3">
        <h3 className="font-display font-semibold text-sm text-slate-800 line-clamp-1 mb-1">
          {drama.title}
        </h3>
        <div className="flex items-center gap-1 mb-2">
          <Star className="w-3.5 h-3.5 text-amber-400 fill-amber-400" aria-hidden="true" />
          <span className="text-xs font-medium text-slate-600">{formatRating(drama.rating)}</span>
          <span className="text-xs text-gray-400" aria-hidden="true">&middot;</span>
          <span className="text-xs text-gray-400">{drama.year}</span>
        </div>
        {predictedRating !== undefined && (
          <p className="text-xs text-rose-500 font-medium mb-1">
            Predicted rating: {predictedRating.toFixed(1)}/10
          </p>
        )}
        {score !== undefined && (
          <p className="text-xs text-violet-500 font-medium mb-1">
            Score: {(score * 100).toFixed(0)}%
          </p>
        )}
        <div className="flex flex-wrap gap-1" role="list" aria-label="Genres">
          {drama.genres.slice(0, 2).map((g) => (
            <span key={g} role="listitem" className="text-[10px] px-2 py-0.5 bg-rose-50 text-rose-600 rounded-full font-medium">
              {g}
            </span>
          ))}
        </div>
        {explanation && (
          <p className="text-[11px] text-gray-400 mt-2 line-clamp-2 italic">
            {explanation}
          </p>
        )}
      </div>
    </div>
  );
}
