import { X } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';

interface GenreChipPickerProps {
  id?: string;
  allGenres: string[];
  selected: string[];
  onChange: (selected: string[]) => void;
  maxSelections: number;
  placeholder?: string;
}

/**
 * Autocomplete-style picker for favorite genres: the user types to filter
 * the existing genre list (from the genres endpoint) and selects up to
 * `maxSelections` genres, shown as removable chips.
 */
export function GenreChipPicker({
  id = 'genre-chip-picker',
  allGenres,
  selected,
  onChange,
  maxSelections,
  placeholder = 'Search for a genre…',
}: GenreChipPickerProps) {
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const atLimit = selected.length >= maxSelections;

  useEffect(() => {
    if (!open) return;
    function handlePointerDown(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener('mousedown', handlePointerDown);
    return () => document.removeEventListener('mousedown', handlePointerDown);
  }, [open]);

  const suggestions = allGenres
    .filter((g) => !selected.includes(g))
    .filter((g) => (query.trim() ? g.toLowerCase().includes(query.trim().toLowerCase()) : true));

  const selectGenre = (genre: string) => {
    if (atLimit) return;
    onChange([...selected, genre]);
    setQuery('');
    setOpen(false);
  };

  const removeGenre = (genre: string) => {
    onChange(selected.filter((g) => g !== genre));
  };

  return (
    <div ref={containerRef} className="relative">
      <label htmlFor={id} className="sr-only">Favorite genres</label>

      {selected.length > 0 && (
        <ul className="flex flex-wrap gap-2 mb-2" aria-label="Selected genres">
          {selected.map((genre) => (
            <li
              key={genre}
              className="flex items-center gap-1 pl-3 pr-1 py-1 bg-rose-50 text-rose-600 rounded-full text-sm font-medium"
            >
              {genre}
              <button
                type="button"
                onClick={() => removeGenre(genre)}
                className="p-1 hover:bg-rose-100 rounded-full"
                aria-label={`Remove ${genre}`}
              >
                <X className="w-3 h-3" aria-hidden="true" />
              </button>
            </li>
          ))}
        </ul>
      )}

      <input
        id={id}
        type="text"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onFocus={() => !atLimit && setOpen(true)}
        disabled={atLimit}
        placeholder={atLimit ? `Maximum ${maxSelections} selected` : placeholder}
        className="w-full px-4 py-3 border-2 border-slate-200 rounded-2xl focus:border-rose-400 outline-none text-sm disabled:bg-slate-50 disabled:text-slate-400"
        autoComplete="off"
        role="combobox"
        aria-expanded={open}
        aria-autocomplete="list"
      />

      {open && !atLimit && suggestions.length > 0 && (
        <ul
          role="listbox"
          className="absolute z-20 mt-2 w-full bg-white border-2 border-slate-200 rounded-2xl shadow-lg overflow-hidden max-h-56 overflow-y-auto"
        >
          {suggestions.map((genre) => (
            <li key={genre}>
              <button
                type="button"
                onClick={() => selectGenre(genre)}
                className="w-full text-left px-3 py-2 text-sm hover:bg-rose-50"
              >
                {genre}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
