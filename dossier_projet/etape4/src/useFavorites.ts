import { useState, useCallback } from 'react';
import type { FavoriteItem, Drama } from './types';

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
    },
    [userId]
  );

  const removeFavorite = useCallback(
    (favoriteId: number) => {
      setFavorites((prev) => {
        const next = prev.filter((f) => f.id !== favoriteId);
        saveFavorites(userId, next);
        return next;
      });
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
