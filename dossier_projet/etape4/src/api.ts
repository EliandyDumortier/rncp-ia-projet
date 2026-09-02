import type {
  Recommendation,
  ModelInfo,
  PaginatedDramas,
  ApiDrama,
  RegisteredUser,
  RatingResponse,
  PaginatedRatings,
  UserProfile,
  PreferencesUpdateRequest,
  FavoriResponse,
  HistoriqueVisionnageResponse,
  InteretResponse,
} from './types';

export class RecommendationAPIError extends Error {
  status_code: number | null;

  constructor(message: string, status_code: number | null = null) {
    super(message);
    this.name = 'RecommendationAPIError';
    this.status_code = status_code;
  }
}

export class DataAPIError extends Error {
  status_code: number | null;

  constructor(message: string, status_code: number | null = null) {
    super(message);
    this.name = 'DataAPIError';
    this.status_code = status_code;
  }
}

const API_IA_URL = (import.meta.env.VITE_API_IA_URL as string) || 'http://localhost:8001';
const API_DATA_URL = (import.meta.env.VITE_API_DATA_URL as string) || 'http://localhost:8000';
const API_TIMEOUT = 5000;

function getStoredToken(): string | null {
  return localStorage.getItem('jwt_token');
}

function setStoredToken(token: string): void {
  localStorage.setItem('jwt_token', token);
}

function clearStoredToken(): void {
  localStorage.removeItem('jwt_token');
}

async function fetchWithTimeout(
  url: string,
  options: RequestInit = {},
  timeout: number = API_TIMEOUT
): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);
  try {
    const response = await fetch(url, { ...options, signal: controller.signal });
    return response;
  } catch (err: unknown) {
    if (err instanceof DOMException && err.name === 'AbortError') {
      throw new RecommendationAPIError('AI API not responding (timeout).', null);
    }
    throw new RecommendationAPIError('Cannot reach AI API (connection refused).', null);
  } finally {
    clearTimeout(timer);
  }
}

export const apiClient = {
  /**
   * Authenticates against the data-api (etape1), the single source of truth
   * for real user accounts (kdrama.utilisateurs). The resulting JWT (sub =
   * real numeric user id, signed with the shared JWT secret) is also valid
   * for the model-api (etape3) /recommend and /predict endpoints.
   */
  async authenticate(username: string, password: string): Promise<{ access_token: string }> {
    const body = new URLSearchParams();
    body.set('username', username);
    body.set('password', password);

    const response = await fetchWithTimeout(`${API_DATA_URL}/api/v1/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: body.toString(),
    });

    if (response.status === 401) {
      throw new RecommendationAPIError('Identifiants incorrects.', 401);
    }
    if (!response.ok) {
      throw new RecommendationAPIError(`Authentication error (HTTP ${response.status}).`, response.status);
    }

    const data = await response.json();
    setStoredToken(data.access_token);
    return data;
  },

  async getRecommendations(
    options: {
      user_id?: number | null;
      drama_id?: number | null;
      top_k?: number;
      mood?: string | null;
      text?: string | null;
      genres?: string[] | null;
      actor_names?: string[] | null;
      happy_ending_only?: boolean | null;
    } = {}
  ): Promise<{ recommendations: Recommendation[]; mode: string }> {
    const token = getStoredToken();
    if (!token) {
      throw new RecommendationAPIError('No JWT token. Authentication required.', 401);
    }

    const {
      user_id = null,
      drama_id = null,
      top_k = 10,
      mood = null,
      text = null,
      genres = null,
      actor_names = null,
      happy_ending_only = null,
    } = options;

    const payload: Record<string, unknown> = { top_k };
    if (user_id !== null) payload.user_id = user_id;
    if (drama_id !== null) payload.drama_id = drama_id;
    if (mood) payload.mood = mood;
    if (text) payload.text = text;
    if (genres && genres.length > 0) payload.genres = genres;
    if (actor_names && actor_names.length > 0) payload.actor_names = actor_names;
    if (happy_ending_only !== null) payload.happy_ending_only = happy_ending_only;

    const response = await fetchWithTimeout(`${API_IA_URL}/recommend`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(payload),
    });

    if (response.status === 401) {
      clearStoredToken();
      throw new RecommendationAPIError('JWT token expired or invalid. Please log in again.', 401);
    }
    if (response.status === 503) {
      throw new RecommendationAPIError('Recommendation model is unavailable.', 503);
    }
    if (!response.ok) {
      throw new RecommendationAPIError(`AI API error (HTTP ${response.status}).`, response.status);
    }

    const data = await response.json();
    return {
      recommendations: (data.recommendations || []).map((r: any) => {
        // Handle various field name combinations from etape3 API
        const id = r.id || r.kdrama_id || r.drama_id || 0;
        const title = r.title || r.titre || 'Unknown';
        const genres = r.genres || [];
        const rating = r.note_moyenne || r.rating || 0;
        const year = r.year || (r.date_diffusion ? parseInt(r.date_diffusion.split('-')[0]) : new Date().getFullYear());
        const episodes = r.nb_episodes || r.episodes || 0;
        const synopsis = r.synopsis || '';
        const poster = r.poster || r.poster_url || r.affiche || 'https://via.placeholder.com/400x600?text=No+Poster';
        const score = r.score || 0;
        const explanation = r.explanation || undefined;

        return {
          id,
          title,
          genres,
          rating,
          year,
          episodes,
          synopsis,
          poster,
          predicted_rating: score,
          score,
          explanation,
        };
      }),
      mode: data.mode || 'user',
    };
  },

  async getModelInfo(): Promise<ModelInfo> {
    const token = getStoredToken();
    if (!token) {
      throw new RecommendationAPIError('No JWT token. Authentication required.', 401);
    }

    const response = await fetchWithTimeout(`${API_IA_URL}/model/info`, {
      headers: { Authorization: `Bearer ${token}` },
    });

    if (!response.ok) {
      throw new RecommendationAPIError(`AI API error (HTTP ${response.status}).`, response.status);
    }

    return response.json();
  },

  async healthCheck(): Promise<boolean> {
    try {
      const response = await fetchWithTimeout(`${API_IA_URL}/health`, {}, 3000);
      return response.ok;
    } catch {
      return false;
    }
  },

  logout(): void {
    clearStoredToken();
  },

  isAuthenticated(): boolean {
    return getStoredToken() !== null;
  },
};

export const dataApi = {
  async listDramas(
    page: number = 1,
    pageSize: number = 20,
    search?: string,
    sortBy: string = 'note_moyenne',
    sortOrder: 'asc' | 'desc' = 'desc',
    genre?: string | string[]
  ): Promise<PaginatedDramas> {
    const params = new URLSearchParams({
      page: String(page),
      page_size: String(pageSize),
      sort_by: sortBy,
      sort_order: sortOrder,
    });
    if (search) params.set('search', search);
    const genreList = (Array.isArray(genre) ? genre : genre ? [genre] : []).filter(
      (g) => g && g !== 'All genres'
    );
    if (genreList.length > 0) params.set('genre', genreList.join(','));

    const response = await fetchWithTimeout(
      `${API_DATA_URL}/api/v1/kdramas?${params.toString()}`
    );
    if (!response.ok) {
      throw new DataAPIError(`Data API error (HTTP ${response.status}).`, response.status);
    }
    return response.json();
  },

  async getDrama(id: number): Promise<ApiDrama> {
    const response = await fetchWithTimeout(`${API_DATA_URL}/api/v1/kdramas/${id}`);
    if (response.status === 404) {
      throw new DataAPIError(`K-Drama with ID ${id} not found.`, 404);
    }
    if (!response.ok) {
      throw new DataAPIError(`Data API error (HTTP ${response.status}).`, response.status);
    }
    return response.json();
  },

  async listGenres(): Promise<string[]> {
    const response = await fetchWithTimeout(`${API_DATA_URL}/api/v1/kdramas/genres`);
    if (!response.ok) {
      throw new DataAPIError(`Data API error (HTTP ${response.status}).`, response.status);
    }
    return response.json();
  },

  async register(data: {
    pseudonyme: string;
    email: string;
    mot_de_passe: string;
    consentement_collecte: boolean;
    consentement_marketing?: boolean;
  }): Promise<RegisteredUser> {
    const response = await fetchWithTimeout(`${API_DATA_URL}/api/v1/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (response.status === 400) {
      const body = await response.json().catch(() => null);
      throw new DataAPIError(body?.detail ?? 'Registration failed.', 400);
    }
    if (!response.ok) {
      throw new DataAPIError(`Data API error (HTTP ${response.status}).`, response.status);
    }
    return response.json();
  },

  async getRatings(kdramaId: number, page: number = 1, pageSize: number = 20): Promise<PaginatedRatings> {
    const params = new URLSearchParams({
      page: String(page),
      page_size: String(pageSize),
    });
    const token = getStoredToken();
    const headers: Record<string, string> = {};
    if (token) headers.Authorization = `Bearer ${token}`;

    const response = await fetchWithTimeout(
      `${API_DATA_URL}/api/v1/kdramas/${kdramaId}/notes?${params.toString()}`,
      { headers }
    );
    if (!response.ok) {
      throw new DataAPIError(`Data API error (HTTP ${response.status}).`, response.status);
    }
    return response.json();
  },

  async createRating(kdramaId: number, note: number, commentaire?: string): Promise<RatingResponse> {
    const token = getStoredToken();
    if (!token) {
      throw new DataAPIError('No JWT token. Authentication required.', 401);
    }
    const response = await fetchWithTimeout(
      `${API_DATA_URL}/api/v1/kdramas/${kdramaId}/notes`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ note, commentaire: commentaire ?? null }),
      }
    );
    if (response.status === 400) {
      const body = await response.json().catch(() => null);
      throw new DataAPIError(body?.detail ?? 'Rating failed.', 400);
    }
    if (!response.ok) {
      throw new DataAPIError(`Data API error (HTTP ${response.status}).`, response.status);
    }
    return response.json();
  },

  async healthCheck(): Promise<boolean> {
    try {
      const response = await fetchWithTimeout(`${API_DATA_URL}/health`, {}, 3000);
      return response.ok;
    } catch {
      return false;
    }
  },

  async getMe(): Promise<UserProfile> {
    const token = getStoredToken();
    if (!token) {
      throw new DataAPIError('No JWT token. Authentication required.', 401);
    }
    const response = await fetchWithTimeout(`${API_DATA_URL}/api/v1/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!response.ok) {
      throw new DataAPIError(`Data API error (HTTP ${response.status}).`, response.status);
    }
    return response.json();
  },

  async updatePreferences(prefs: PreferencesUpdateRequest): Promise<UserProfile> {
    const token = getStoredToken();
    if (!token) {
      throw new DataAPIError('No JWT token. Authentication required.', 401);
    }
    const response = await fetchWithTimeout(`${API_DATA_URL}/api/v1/auth/me/preferences`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}` },
      body: JSON.stringify(prefs),
    });
    if (response.status === 400 || response.status === 422) {
      const body = await response.json().catch(() => null);
      throw new DataAPIError(body?.detail ?? 'Preferences update failed.', response.status);
    }
    if (!response.ok) {
      throw new DataAPIError(`Data API error (HTTP ${response.status}).`, response.status);
    }
    return response.json();
  },

  /**
   * Actor autocomplete: derives names live from the K-Drama catalog
   * (GET /api/v1/kdramas/actors), the actor equivalent of listGenres()'s
   * GET /api/v1/kdramas/genres — the kdrama.acteurs reference table isn't
   * populated by the collection pipeline, so catalog-derived names are the
   * real source of truth (see actor_preferences_by_name_schema.sql).
   */
  async searchActeurs(search: string, limit: number = 10): Promise<string[]> {
    const params = new URLSearchParams({ limit: String(limit) });
    if (search) params.set('search', search);
    const response = await fetchWithTimeout(
      `${API_DATA_URL}/api/v1/kdramas/actors?${params.toString()}`
    );
    if (!response.ok) {
      throw new DataAPIError(`Data API error (HTTP ${response.status}).`, response.status);
    }
    return response.json();
  },

  async listFavoris(): Promise<FavoriResponse[]> {
    const token = getStoredToken();
    if (!token) {
      throw new DataAPIError('No JWT token. Authentication required.', 401);
    }
    const response = await fetchWithTimeout(`${API_DATA_URL}/api/v1/favoris`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!response.ok) {
      throw new DataAPIError(`Data API error (HTTP ${response.status}).`, response.status);
    }
    return response.json();
  },

  async addFavori(kdramaId: number): Promise<FavoriResponse> {
    const token = getStoredToken();
    if (!token) {
      throw new DataAPIError('No JWT token. Authentication required.', 401);
    }
    const response = await fetchWithTimeout(`${API_DATA_URL}/api/v1/favoris/${kdramaId}`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!response.ok) {
      throw new DataAPIError(`Data API error (HTTP ${response.status}).`, response.status);
    }
    return response.json();
  },

  async removeFavori(kdramaId: number): Promise<void> {
    const token = getStoredToken();
    if (!token) {
      throw new DataAPIError('No JWT token. Authentication required.', 401);
    }
    const response = await fetchWithTimeout(`${API_DATA_URL}/api/v1/favoris/${kdramaId}`, {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!response.ok && response.status !== 204) {
      throw new DataAPIError(`Data API error (HTTP ${response.status}).`, response.status);
    }
  },

  async listHistorique(): Promise<HistoriqueVisionnageResponse[]> {
    const token = getStoredToken();
    if (!token) {
      throw new DataAPIError('No JWT token. Authentication required.', 401);
    }
    const response = await fetchWithTimeout(`${API_DATA_URL}/api/v1/historique`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!response.ok) {
      throw new DataAPIError(`Data API error (HTTP ${response.status}).`, response.status);
    }
    return response.json();
  },

  async upsertHistorique(
    kdramaId: number,
    statut: 'a_voir' | 'en_cours' | 'termine' | 'abandonne',
    episodesVus: number = 0
  ): Promise<HistoriqueVisionnageResponse> {
    const token = getStoredToken();
    if (!token) {
      throw new DataAPIError('No JWT token. Authentication required.', 401);
    }
    const response = await fetchWithTimeout(`${API_DATA_URL}/api/v1/historique/${kdramaId}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}` },
      body: JSON.stringify({ kdrama_id: kdramaId, episodes_vus: episodesVus, statut }),
    });
    if (!response.ok) {
      throw new DataAPIError(`Data API error (HTTP ${response.status}).`, response.status);
    }
    return response.json();
  },

  async getInteret(kdramaId: number): Promise<InteretResponse | null> {
    const token = getStoredToken();
    if (!token) {
      throw new DataAPIError('No JWT token. Authentication required.', 401);
    }
    const response = await fetchWithTimeout(`${API_DATA_URL}/api/v1/kdramas/${kdramaId}/interet`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!response.ok) {
      throw new DataAPIError(`Data API error (HTTP ${response.status}).`, response.status);
    }
    return response.json();
  },

  async setInteret(kdramaId: number, interesse: boolean): Promise<InteretResponse> {
    const token = getStoredToken();
    if (!token) {
      throw new DataAPIError('No JWT token. Authentication required.', 401);
    }
    const response = await fetchWithTimeout(`${API_DATA_URL}/api/v1/kdramas/${kdramaId}/interet`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}` },
      body: JSON.stringify({ interesse }),
    });
    if (!response.ok) {
      throw new DataAPIError(`Data API error (HTTP ${response.status}).`, response.status);
    }
    return response.json();
  },
};
