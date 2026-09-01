import { Search, ChevronLeft, ChevronRight } from 'lucide-react';
import { useState, useEffect, useRef } from 'react';
import type { Drama, Page } from '../types';
import { fetchDramas, dramas, allGenres } from '../data';
import { DramaCard } from '../components/DramaCard';
import { DramaDetailModal } from '../components/DramaDetailModal';
import { LoadingSkeleton } from '../components/LoadingSkeleton';
import { useAuth } from '../auth';
import { useFavorites } from '../useFavorites';
import { useWatchedDramas } from '../useWatchedDramas';

interface SearchPageProps {
  nav: (p: Page) => void;
}

const ITEMS_PER_PAGE = 24;

// Complete list of genres available in the database
const AVAILABLE_GENRES = [
  "Action & Adventure",
  "Action",
  "Comedy",
  "Crime",
  "Drama",
  "Family",
  "Fantasy",
  "Friendship",
  "Historical",
  "Life",
  "Medical",
  "Mystery",
  "Romance",
  "Sci-Fi & Fantasy",
  "Soap",
  "Thriller",
  "War & Politics",
  "Youth",
].sort();

export function SearchPage({ nav }: SearchPageProps) {
  const { user, flash } = useAuth();
  const { favorites, isFavorite, addFavorite, removeFavorite } = useFavorites(user?.user_id ?? null);
  const { isWatched, addWatchedDrama } = useWatchedDramas(user?.user_id ?? null);
  const [query, setQuery] = useState('');
  const [genreFilter, setGenreFilter] = useState('All genres');
  const [genres, setGenres] = useState<string[]>(AVAILABLE_GENRES);
  const [results, setResults] = useState<Drama[]>([]);
  const [loading, setLoading] = useState(true);
  const [total, setTotal] = useState(0);
  const [fallback, setFallback] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const [selectedDrama, setSelectedDrama] = useState<Drama | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    setGenres(AVAILABLE_GENRES);
  }, []);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    setCurrentPage(1); // Reset to page 1 when search/filter changes
    debounceRef.current = setTimeout(async () => {
      setLoading(true);
      const result = await fetchDramas(1, ITEMS_PER_PAGE, query || undefined, 'note_moyenne', 'desc');
      setResults(result.items);
      setTotal(result.total);
      setFallback(result.fallback);
      setLoading(false);
    }, 300);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [query]);

  // Fetch new page when currentPage changes
  useEffect(() => {
    if (currentPage === 1) return; // Already loaded on search
    setLoading(true);
    const fetchPage = async () => {
      const result = await fetchDramas(currentPage, ITEMS_PER_PAGE, query || undefined, 'note_moyenne', 'desc');
      setResults(result.items);
      setTotal(result.total);
      setLoading(false);
    };
    fetchPage();
  }, [currentPage, query]);

  const filtered = genreFilter === 'All genres'
    ? results
    : results.filter((d) => d.genres.includes(genreFilter));

  const totalPages = Math.ceil(total / ITEMS_PER_PAGE);
  const hasNextPage = currentPage < totalPages;
  const hasPrevPage = currentPage > 1;

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
    <div className="max-w-6xl mx-auto px-4 sm:px-6 py-8">
      <h1 className="font-display text-2xl font-bold text-slate-800 mb-6">Search</h1>

      <div className="flex gap-3 flex-wrap mb-8">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" aria-hidden="true" />
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Title, keyword..."
            aria-label="Search a K-Drama"
            className="w-full pl-10 pr-4 py-3 border-2 border-slate-200 rounded-2xl focus:border-rose-400 outline-none text-sm"
          />
        </div>
        <label htmlFor="genre-select" className="sr-only">Filter by genre</label>
        <select
          id="genre-select"
          value={genreFilter}
          onChange={(e) => setGenreFilter(e.target.value)}
          className="px-4 py-3 border-2 border-slate-200 rounded-2xl focus:border-rose-400 outline-none text-sm bg-white"
        >
          <option value="All genres">All genres</option>
          {genres.map((g) => (
            <option key={g} value={g}>{g}</option>
          ))}
        </select>
      </div>

      <p className="text-sm text-gray-500 mb-4" aria-live="polite">
        {fallback && 'Local catalog — '}
        {loading
          ? 'Searching...'
          : `${filtered.length} result${filtered.length > 1 ? 's' : ''}${query ? ` for "${query}"` : ''}${genreFilter !== 'All genres' ? ` in ${genreFilter}` : ''}`}
      </p>

      {loading ? (
        <LoadingSkeleton count={8} />
      ) : filtered.length === 0 ? (
        <div className="text-center py-16 text-gray-400">
          <Search className="w-12 h-12 mx-auto mb-4 opacity-40" aria-hidden="true" />
          <p>No results found.</p>
        </div>
      ) : (
        <>
          <div role="list" className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4 mb-8">
            {filtered.map((d) => (
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

          {/* Pagination Controls */}
          <div className="flex items-center justify-between py-8 border-t border-slate-200">
            <button
              onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
              disabled={!hasPrevPage}
              className="flex items-center gap-2 px-4 py-2 border-2 border-rose-400 text-rose-500 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed hover:bg-rose-50 transition-colors"
              aria-label="Previous page"
            >
              <ChevronLeft className="w-5 h-5" aria-hidden="true" />
              Previous
            </button>

            <div className="text-sm text-gray-600">
              Page <span className="font-semibold">{currentPage}</span> of <span className="font-semibold">{totalPages || 1}</span>
              <span className="text-gray-400 mx-2">•</span>
              <span className="font-semibold">{total}</span> dramas total
            </div>

            <button
              onClick={() => setCurrentPage(prev => Math.min(totalPages, prev + 1))}
              disabled={!hasNextPage}
              className="flex items-center gap-2 px-4 py-2 border-2 border-rose-400 text-rose-500 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed hover:bg-rose-50 transition-colors"
              aria-label="Next page"
            >
              Next
              <ChevronRight className="w-5 h-5" aria-hidden="true" />
            </button>
          </div>
        </>
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
