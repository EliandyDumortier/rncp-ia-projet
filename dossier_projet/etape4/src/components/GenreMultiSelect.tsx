import { ChevronDown } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';

interface GenreMultiSelectProps {
  id?: string;
  genres: string[];
  selected: string[];
  onChange: (selected: string[]) => void;
}

/**
 * Excel-style filter dropdown: a checklist of genres with "Select all" /
 * "Unselect all" shortcuts, letting the user pick one or several values at once.
 */
export function GenreMultiSelect({ id = 'genre-select', genres, selected, onChange }: GenreMultiSelectProps) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState('');
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function handlePointerDown(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') setOpen(false);
    }
    document.addEventListener('mousedown', handlePointerDown);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('mousedown', handlePointerDown);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [open]);

  useEffect(() => {
    if (!open) setSearch('');
  }, [open]);

  const allSelected = genres.length > 0 && selected.length === genres.length;
  const noneSelected = selected.length === 0;

  const label = allSelected
    ? 'All genres'
    : noneSelected
    ? 'No genres selected'
    : selected.length === 1
    ? selected[0]
    : `${selected.length} genres selected`;

  const toggleGenre = (g: string) => {
    onChange(selected.includes(g) ? selected.filter((s) => s !== g) : [...selected, g]);
  };

  const visibleGenres = search
    ? genres.filter((g) => g.toLowerCase().includes(search.toLowerCase()))
    : genres;

  return (
    <div ref={containerRef} className="relative">
      <label htmlFor={id} className="sr-only">Filter by genre</label>
      <button
        id={id}
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="listbox"
        aria-expanded={open}
        className="flex items-center justify-between gap-2 px-4 py-3 border-2 border-slate-200 rounded-2xl focus:border-rose-400 outline-none text-sm bg-white min-w-[180px] text-left"
      >
        <span className="truncate">{label}</span>
        <ChevronDown
          className={`w-4 h-4 text-gray-400 transition-transform shrink-0 ${open ? 'rotate-180' : ''}`}
          aria-hidden="true"
        />
      </button>

      {open && (
        <div
          role="listbox"
          aria-multiselectable="true"
          className="absolute z-20 mt-2 w-64 bg-white border-2 border-slate-200 rounded-2xl shadow-lg overflow-hidden"
        >
          <div className="p-2 border-b border-slate-100">
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search genres..."
              aria-label="Search genres"
              className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:border-rose-400 outline-none"
            />
          </div>

          <div className="flex items-center justify-between px-3 py-2 border-b border-slate-100 text-xs font-semibold text-rose-500">
            <button type="button" onClick={() => onChange([...genres])} className="hover:underline">
              Select all
            </button>
            <button type="button" onClick={() => onChange([])} className="hover:underline">
              Unselect all
            </button>
          </div>

          <ul className="max-h-56 overflow-y-auto py-1">
            {visibleGenres.length === 0 ? (
              <li className="px-3 py-2 text-sm text-gray-400">No genres match.</li>
            ) : (
              visibleGenres.map((g) => (
                <li key={g}>
                  <label className="flex items-center gap-2 px-3 py-2 text-sm hover:bg-rose-50 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={selected.includes(g)}
                      onChange={() => toggleGenre(g)}
                      className="w-4 h-4 accent-rose-500"
                    />
                    <span className="truncate">{g}</span>
                  </label>
                </li>
              ))
            )}
          </ul>

          <div className="border-t border-slate-100 px-3 py-2 text-right">
            <button
              type="button"
              onClick={() => setOpen(false)}
              className="px-3 py-1.5 text-xs font-semibold rounded-lg bg-rose-500 text-white hover:bg-rose-600 transition-colors"
            >
              Done
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
