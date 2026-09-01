import { useState, useCallback, useEffect } from 'react';
import type { FavoriteItem, Drama } from './types';
import { dataApi, DataAPIError } from './api';

const STORAGE_KEY = 'kdrama_favorites';

function getStorageKey(userId: number | null): string {
  return userId !== null ? `${STORAGE_KEY}_${userId}` : STORAGE_KEY;
}

function loadFavorites(userId: number | null): FavoriteItem[] {
  const key = getStorageKey(userId);
  const raw = localStorage.getItem(key);
  if (!raw) return [];
  try {
    return JSON.parse(raw) as FavoriteItem[];
  } catch {
    return [];
  }
}

function saveFavorites(userId: number | null, favorites: FavoriteItem[]): void {
  localStorage.setItem(getStorageKey(userId), JSON.stringify(favorites));
}

export function useFavorites(userId: number | null) {
  const [favorites, setFavorites] = useState<FavoriteItem[]>(() => loadFavorites(userId));

  // When signed in, sync from the real backend (source of truth). Falls
  // back silently to whatever is already in localStorage if the API is
  // unreachable, so the app keeps working offline/degraded.
  useEffect(() => {
    if (userId === null) return;
    let cancelled = false;
    dataApi
      .listFavoris()
      .then((remote) => {
        if (cancelled) return;
        const mapped: FavoriteItem[] = remote.map((f) => ({
          id: f.id,
          drama_id: f.kdrama_id,
          drama_title: '',
          drama_poster: '',
          added_at: f.date_ajout,
        }));
        setFavorites((prev) => {
          // Preserve locally-known title/poster (backend doesn't return them).
          const localById = new Map(prev.map((f) => [f.drama_id, f]));
          const merged = mapped.map((f) => ({
            ...f,
            drama_title: localById.get(f.drama_id)?.drama_title ?? f.drama_title,
            drama_poster: localById.get(f.drama_id)?.drama_poster ?? f.drama_poster,
          }));
          saveFavorites(userId, merged);
          return merged;
        });
      })
      .catch(() => {
        // Keep local cache as-is on failure (offline fallback).
      });
    return () => {
      cancelled = true;
    };
  }, [userId]);

  const addFavorite = useCallback(
    (drama: Drama) => {
      setFavorites((prev) => {
        if (prev.some((f) => f.drama_id === drama.id)) return prev;
        const item: FavoriteItem = {
          id: Date.now(),
          drama_id: drama.id,
          drama_title: drama.title,
          drama_poster: drama.poster,
          added_at: new Date().toISOString(),
        };
        const next = [item, ...prev];
        saveFavorites(userId, next);
        return next;
      });
      if (userId !== null) {
        dataApi.addFavori(drama.id).catch((err) => {
          if (!(err instanceof DataAPIError)) throw err;
          // Non-blocking: the UI already reflects the favorite locally even
          // if the backend call fails (e.g. offline).
        });
      }
    },
    [userId]
  );

  const removeFavorite = useCallback(
    (favoriteId: number) => {
      let removedDramaId: number | null = null;
      setFavorites((prev) => {
        const removed = prev.find((f) => f.id === favoriteId);
        removedDramaId = removed ? removed.drama_id : null;
        const next = prev.filter((f) => f.id !== favoriteId);
        saveFavorites(userId, next);
        return next;
      });
      if (userId !== null && removedDramaId !== null) {
        dataApi.removeFavori(removedDramaId).catch((err) => {
          if (!(err instanceof DataAPIError)) throw err;
        });
      }
    },
    [userId]
  );

  const isFavorite = useCallback(
    (dramaId: number) => favorites.some((f) => f.drama_id === dramaId),
    [favorites]
  );

  const favoriteCount = favorites.length;

  return { favorites, addFavorite, removeFavorite, isFavorite, favoriteCount };
}
