import { useState, useCallback } from 'react';
import type { WatchedDrama, Drama } from './types';

const STORAGE_KEY = 'kdrama_watched';

function getStorageKey(userId: number | null): string {
  return userId !== null ? `${STORAGE_KEY}_${userId}` : STORAGE_KEY;
}

function loadWatchedDramas(userId: number | null): WatchedDrama[] {
  const key = getStorageKey(userId);
  const raw = localStorage.getItem(key);
  if (!raw) return [];
  try {
    return JSON.parse(raw) as WatchedDrama[];
  } catch {
    return [];
  }
}

function saveWatchedDramas(userId: number | null, dramas: WatchedDrama[]): void {
  localStorage.setItem(getStorageKey(userId), JSON.stringify(dramas));
}

export function useWatchedDramas(userId: number | null) {
  const [watched, setWatched] = useState<WatchedDrama[]>(() => loadWatchedDramas(userId));

  const addWatchedDrama = useCallback(
    (drama: Drama, rating: number, notes: string = '') => {
      setWatched((prev) => {
        // Update if already exists, otherwise add new
        const existing = prev.findIndex((w) => w.drama_id === drama.id);
        let next: WatchedDrama[];

        if (existing !== -1) {
          // Update existing entry
          next = [...prev];
          next[existing] = {
            ...next[existing],
            rating,
            notes,
            watched_at: new Date().toISOString(),
          };
        } else {
          // Add new entry
          const item: WatchedDrama = {
            id: Date.now(),
            drama_id: drama.id,
            drama_title: drama.title,
            drama_poster: drama.poster,
            rating,
            notes,
            watched_at: new Date().toISOString(),
            watched_date: new Date().toLocaleDateString(),
          };
          next = [item, ...prev];
        }

        saveWatchedDramas(userId, next);
        return next;
      });
    },
    [userId]
  );

  const removeWatchedDrama = useCallback(
    (watchedId: number) => {
      setWatched((prev) => {
        const next = prev.filter((w) => w.id !== watchedId);
        saveWatchedDramas(userId, next);
        return next;
      });
    },
    [userId]
  );

  const isWatched = useCallback(
    (dramaId: number) => watched.some((w) => w.drama_id === dramaId),
    [watched]
  );

  const getWatchedDrama = useCallback(
    (dramaId: number) => watched.find((w) => w.drama_id === dramaId),
    [watched]
  );

  return { watched, addWatchedDrama, removeWatchedDrama, isWatched, getWatchedDrama };
}
