import { X } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import type { ActeurSummary } from '../types';
import { dataApi } from '../api';

interface ActorAutocompleteProps {
  id?: string;
  selected: ActeurSummary[];
  onChange: (selected: ActeurSummary[]) => void;
  maxSelections: number;
  placeholder?: string;
}

/**
 * Autocomplete input for favorite actors/actresses: the user types a name,
 * suggestions are fetched from the existing actors search endpoint
 * (GET /api/v1/acteurs?search=), and selecting one adds it as a removable
 * chip, up to `maxSelections`.
 */
export function ActorAutocomplete({
  id = 'actor-autocomplete',
  selected,
  onChange,
  maxSelections,
  placeholder = 'Search for an actor or actress…',
}: ActorAutocompleteProps) {
  const [query, setQuery] = useState('');
  const [suggestions, setSuggestions] = useState<ActeurSummary[]>([]);
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
        const selectedIds = new Set(selected.map((a) => a.id));
        setSuggestions(results.filter((a) => !selectedIds.has(a.id)));
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

  const selectActor = (actor: ActeurSummary) => {
    if (atLimit) return;
    onChange([...selected, actor]);
    setQuery('');
    setSuggestions([]);
    setOpen(false);
  };

  const removeActor = (actorId: number) => {
    onChange(selected.filter((a) => a.id !== actorId));
  };

  return (
    <div ref={containerRef} className="relative">
      <label htmlFor={id} className="sr-only">Favorite actors/actresses</label>

      {selected.length > 0 && (
        <ul className="flex flex-wrap gap-2 mb-2" aria-label="Selected actors">
          {selected.map((actor) => (
            <li
              key={actor.id}
              className="flex items-center gap-1 pl-3 pr-1 py-1 bg-rose-50 text-rose-600 rounded-full text-sm font-medium"
            >
              {actor.nom}
              <button
                type="button"
                onClick={() => removeActor(actor.id)}
                className="p-1 hover:bg-rose-100 rounded-full"
                aria-label={`Remove ${actor.nom}`}
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
            suggestions.map((actor) => (
              <li key={actor.id}>
                <button
                  type="button"
                  onClick={() => selectActor(actor)}
                  className="w-full text-left px-3 py-2 text-sm hover:bg-rose-50"
                >
                  {actor.nom}
                  {actor.nom_original && actor.nom_original !== actor.nom && (
                    <span className="text-gray-400"> ({actor.nom_original})</span>
                  )}
                </button>
              </li>
            ))
          )}
        </ul>
      )}
    </div>
  );
}
