import { createClient } from '@supabase/supabase-js';

const SUPABASE_URL = 'https://vnwgqqhoxppurcvelmhu.supabase.co';
const SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZud2dxcWhveHBwdXJjdmVsbWh1Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3MzAwOTc0NDUsImV4cCI6MTg4Nzg2NTQ0NX0.B5P9PzvLwJnuKnnCaJk8-tqqZJoYKKDpT_Y8VLMxAoA';

const supabase = createClient(SUPABASE_URL, SUPABASE_KEY);

export async function fetchDramasFromSupabase(
  page: number = 1,
  pageSize: number = 20,
  search?: string,
  sortBy: string = 'note_moyenne',
  sortOrder: 'asc' | 'desc' = 'desc'
) {
  try {
    console.log(`[Supabase] Fetching dramas: page=${page}, pageSize=${pageSize}, search=${search}`);

    let query = supabase
      .from('kdramas')
      .select('*', { count: 'exact' })
      .schema('kdrama');

    // Add search filter
    if (search) {
      query = query.or(`titre.ilike.%${search}%,titre_original.ilike.%${search}%`);
    }

    // Add sorting
    query = query.order(sortBy, { ascending: sortOrder === 'asc' });

    // Add pagination
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
        } catch (e) {
          console.warn('Failed to parse genres:', e);
        }

        const poster = kdrama.poster && kdrama.poster.trim() ? kdrama.poster : 'https://via.placeholder.com/400x600?text=No+Poster';

        return {
          id: kdrama.id,
          title: kdrama.titre || kdrama.title || 'Unknown',
          genres: Array.isArray(genres) ? genres : [],
          rating: kdrama.note_moyenne || 0,
          year: kdrama.annee_diffusion || (kdrama.date_diffusion ? new Date(kdrama.date_diffusion).getFullYear() : 0),
          episodes: kdrama.nb_episodes || 0,
          synopsis: kdrama.synopsis || '',
          poster: poster,
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
