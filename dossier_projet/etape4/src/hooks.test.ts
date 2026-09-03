import { act, renderHook } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { dramas } from './data';
import { useFavorites } from './useFavorites';
import { useWatchedDramas } from './useWatchedDramas';

afterEach(() => {
  localStorage.clear();
});

describe('useFavorites', () => {
  it('adds and removes a favorite in the local offline cache', () => {
    const { result } = renderHook(() => useFavorites(null));
    const drama = dramas[0];

    act(() => result.current.addFavorite(drama));

    expect(result.current.favoriteCount).toBe(1);
    expect(result.current.isFavorite(drama.id)).toBe(true);
    expect(result.current.favorites[0]).toMatchObject({ drama_id: drama.id, drama_title: drama.title });

    act(() => result.current.removeFavorite(result.current.favorites[0].id));

    expect(result.current.favoriteCount).toBe(0);
    expect(result.current.isFavorite(drama.id)).toBe(false);
  });

  it('loads the persisted local favorite cache', () => {
    localStorage.setItem('kdrama_favorites', JSON.stringify([
      { id: 10, drama_id: dramas[1].id, drama_title: dramas[1].title, drama_poster: '', added_at: '2026-01-01' },
    ]));

    const { result } = renderHook(() => useFavorites(null));

    expect(result.current.favoriteCount).toBe(1);
    expect(result.current.isFavorite(dramas[1].id)).toBe(true);
  });
});

describe('useWatchedDramas', () => {
  it('adds, updates and removes a watched drama in the local offline cache', () => {
    const { result } = renderHook(() => useWatchedDramas(null));
    const drama = dramas[2];

    act(() => result.current.addWatchedDrama(drama, 7, 'First viewing'));

    expect(result.current.isWatched(drama.id)).toBe(true);
    expect(result.current.getWatchedDrama(drama.id)).toMatchObject({ rating: 7, notes: 'First viewing' });

    act(() => result.current.addWatchedDrama(drama, 9, 'Updated rating'));

    expect(result.current.watched).toHaveLength(1);
    expect(result.current.getWatchedDrama(drama.id)).toMatchObject({ rating: 9, notes: 'Updated rating' });

    act(() => result.current.removeWatchedDrama(result.current.watched[0].id));

    expect(result.current.watched).toHaveLength(0);
    expect(result.current.isWatched(drama.id)).toBe(false);
  });

  it('loads the persisted watched-drama cache', () => {
    localStorage.setItem('kdrama_watched', JSON.stringify([
      {
        id: 11,
        drama_id: dramas[3].id,
        drama_title: dramas[3].title,
        drama_poster: '',
        rating: 8,
        notes: '',
        watched_at: '2026-01-01T00:00:00Z',
        watched_date: '01/01/2026',
      },
    ]));

    const { result } = renderHook(() => useWatchedDramas(null));

    expect(result.current.getWatchedDrama(dramas[3].id)?.rating).toBe(8);
  });
});
