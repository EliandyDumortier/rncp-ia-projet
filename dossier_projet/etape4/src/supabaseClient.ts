import { createClient } from '@supabase/supabase-js';

const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL?.trim();
const SUPABASE_PUBLISHABLE_KEY = import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY?.trim();

const supabase = SUPABASE_URL && SUPABASE_PUBLISHABLE_KEY
  ? createClient(SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY)
  : null;

export async function fetchDramasFromSupabase(
  page: number = 1,
  pageSize: number = 20,
  search?: string,
  sortBy: string = 'note_moyenne',
  sortOrder: 'asc' | 'desc' = 'desc'
) {
  if (!supabase) {
    throw new Error('Supabase browser fallback is not configured.');
  }

  try {
    console.log(`[Supabase] Fetching dramas: page=${page}, pageSize=${pageSize}, search=${search}`);

    let query = supabase
      .from('kdramas', { schema: 'kdrama' })
      .select('*', { count: 'exact' });

    if (search) {
      query = query.or(`titre.ilike.%${search}%,titre_original.ilike.%${search}%`);
    }

    query = query.order(sortBy, { ascending: sortOrder === 'asc' });

    const offset = (page - 1) * pageSize;
    query = query.range(offset, offset + pageSize - 1);

    const { data, count, error } = await query;

    if (error) {
      console.error('[Supabase] Query error:', error);
      throw error;
    }

    console.log(`[Supabase] Got ${data?.length || 0} dramas, total=${count}`);

    return {
      items: (data || []).map((kdrama) => {
        let genres: string[] = [];
        try {
          if (typeof kdrama.genres === 'string') {
            genres = JSON.parse(kdrama.genres);
          } else if (Array.isArray(kdrama.genres)) {
            genres = kdrama.genres;
          }
        } catch (error) {
          console.warn('Failed to parse genres:', error);
        }

        const poster = kdrama.poster && kdrama.poster.trim()
          ? kdrama.poster
          : 'https://via.placeholder.com/400x600?text=No+Poster';

        return {
          id: kdrama.id,
          title: kdrama.titre || kdrama.title || 'Unknown',
          genres: Array.isArray(genres) ? genres : [],
          rating: kdrama.note_moyenne || 0,
          year: kdrama.annee_diffusion
            || (kdrama.date_diffusion ? new Date(kdrama.date_diffusion).getFullYear() : 0),
          episodes: kdrama.nb_episodes || 0,
          synopsis: kdrama.synopsis || '',
          poster,
        };
      }),
      total: count || 0,
      totalPages: Math.ceil((count || 0) / pageSize),
      fallback: false,
    };
  } catch (error) {
    console.error('[Supabase] Error fetching dramas:', error);
    throw error;
  }
}
