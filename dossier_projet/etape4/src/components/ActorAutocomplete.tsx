import { X } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { dataApi } from '../api';

interface ActorAutocompleteProps {
  id?: string;
  selected: string[];
  onChange: (selected: string[]) => void;
  maxSelections: number;
  placeholder?: string;
}

/**
 * Autocomplete input for favorite actors/actresses: the user types a name,
 * suggestions are fetched live from the K-Drama catalog
 * (GET /api/v1/kdramas/actors?search=, derived from kdramas.acteurs — the
 * actor equivalent of the genres-from-catalog endpoint), and selecting one
 * adds it as a removable chip, up to `maxSelections`.
 */
export function ActorAutocomplete({
  id = 'actor-autocomplete',
  selected,
  onChange,
  maxSelections,
  placeholder = 'Search for an actor or actress…',
}: ActorAutocompleteProps) {
  const [query, setQuery] = useState('');
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

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

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (!query.trim() || atLimit) {
      setSuggestions([]);
      return;
    }
    debounceRef.current = setTimeout(async () => {
      setLoading(true);
      try {
        const results = await dataApi.searchActeurs(query.trim(), 8);
        const selectedSet = new Set(selected);
        setSuggestions(results.filter((name) => !selectedSet.has(name)));
        setOpen(true);
      } catch {
        setSuggestions([]);
      } finally {
        setLoading(false);
      }
    }, 300);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query, atLimit]);

  const selectActor = (name: string) => {
    if (atLimit) return;
    onChange([...selected, name]);
    setQuery('');
    setSuggestions([]);
    setOpen(false);
  };

  const removeActor = (name: string) => {
    onChange(selected.filter((a) => a !== name));
  };

  return (
    <div ref={containerRef} className="relative">
      <label htmlFor={id} className="sr-only">Favorite actors/actresses</label>

      {selected.length > 0 && (
        <ul className="flex flex-wrap gap-2 mb-2" aria-label="Selected actors">
          {selected.map((name) => (
            <li
              key={name}
              className="flex items-center gap-1 pl-3 pr-1 py-1 bg-rose-50 text-rose-600 rounded-full text-sm font-medium"
            >
              {name}
              <button
                type="button"
                onClick={() => removeActor(name)}
                className="p-1 hover:bg-rose-100 rounded-full"
                aria-label={`Remove ${name}`}
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
        onFocus={() => suggestions.length > 0 && setOpen(true)}
        disabled={atLimit}
        placeholder={atLimit ? `Maximum ${maxSelections} selected` : placeholder}
        className="w-full px-4 py-3 border-2 border-slate-200 rounded-2xl focus:border-rose-400 outline-none text-sm disabled:bg-slate-50 disabled:text-slate-400"
        autoComplete="off"
        role="combobox"
        aria-expanded={open}
        aria-autocomplete="list"
      />

      {open && (loading || suggestions.length > 0) && (
        <ul
          role="listbox"
          className="absolute z-20 mt-2 w-full bg-white border-2 border-slate-200 rounded-2xl shadow-lg overflow-hidden max-h-56 overflow-y-auto"
        >
          {loading ? (
            <li className="px-3 py-2 text-sm text-gray-400">Searching…</li>
          ) : (
            suggestions.map((name) => (
              <li key={name}>
                <button
                  type="button"
                  onClick={() => selectActor(name)}
                  className="w-full text-left px-3 py-2 text-sm hover:bg-rose-50"
                >
                  {name}
                </button>
              </li>
            ))
          )}
        </ul>
      )}
    </div>
  );
}
