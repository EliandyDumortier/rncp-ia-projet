import { useState, useCallback, useEffect } from 'react';
import type { WatchedDrama, Drama } from './types';
import { dataApi, DataAPIError } from './api';

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

  // When signed in, sync from the real watch-history backend (source of
  // truth for the recommendation model). Falls back silently to whatever is
  // already in localStorage if the API is unreachable.
  useEffect(() => {
    if (userId === null) return;
    let cancelled = false;
    dataApi
      .listHistorique()
      .then((remote) => {
        if (cancelled) return;
        const mapped: WatchedDrama[] = remote.map((h) => ({
          id: h.id,
          drama_id: h.kdrama_id,
          drama_title: '',
          drama_poster: '',
          rating: 0,
          notes: '',
          watched_at: h.date_modification,
          watched_date: new Date(h.date_modification).toLocaleDateString(),
        }));
        setWatched((prev) => {
          const localById = new Map(prev.map((w) => [w.drama_id, w]));
          const merged = mapped.map((w) => {
            const local = localById.get(w.drama_id);
            return {
              ...w,
              drama_title: local?.drama_title ?? w.drama_title,
              drama_poster: local?.drama_poster ?? w.drama_poster,
              rating: local?.rating ?? w.rating,
              notes: local?.notes ?? w.notes,
            };
          });
          saveWatchedDramas(userId, merged);
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

  const addWatchedDrama = useCallback(
    (drama: Drama, rating: number = 0, notes: string = '') => {
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
      if (userId !== null) {
        dataApi.upsertHistorique(drama.id, 'termine').catch((err) => {
          if (!(err instanceof DataAPIError)) throw err;
        });
      }
    },
    [userId]
  );

  const removeWatchedDrama = useCallback(
    (watchedId: number) => {
      setWatched((prev) => {
        const drama = prev.find((w) => w.id === watchedId);
        const next = prev.filter((w) => w.id !== watchedId);
        saveWatchedDramas(userId, next);

        if (drama && userId !== null) {
          dataApi.deleteHistorique(drama.drama_id).catch((err) => {
            if (!(err instanceof DataAPIError)) throw err;
          });
        }

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
