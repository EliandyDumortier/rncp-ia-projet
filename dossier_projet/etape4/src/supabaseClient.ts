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
      console.error('Supabase query error:', error);
      throw error;
    }

    return {
      items: (data || []).map((kdrama) => ({
        id: kdrama.id,
        title: kdrama.titre,
        genres: kdrama.genres ? JSON.parse(kdrama.genres) : [],
        rating: kdrama.note_moyenne || 0,
        year: kdrama.annee_diffusion || new Date(kdrama.date_diffusion).getFullYear(),
        episodes: kdrama.nb_episodes || 0,
        synopsis: kdrama.synopsis || '',
        poster: kdrama.poster || 'https://via.placeholder.com/400x600?text=No+Poster',
      })),
      total: count || 0,
      totalPages: Math.ceil((count || 0) / pageSize),
      fallback: false,
    };
  } catch (error) {
    console.error('Error fetching from Supabase:', error);
    throw error;
  }
}
