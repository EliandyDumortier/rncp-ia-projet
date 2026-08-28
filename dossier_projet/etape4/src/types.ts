export interface Drama {
  id: number;
  title: string;
  genres: string[];
  rating: number;
  year: number;
  episodes: number;
  synopsis: string;
  poster: string;
}

export interface Recommendation extends Drama {
  predicted_rating?: number;
  score?: number;
}

export interface FavoriteItem {
  id: number;
  drama_id: number;
  drama_title: string;
  drama_poster: string;
  added_at: string;
}

export interface WatchedDrama {
  id: number;
  drama_id: number;
  drama_title: string;
  drama_poster: string;
  rating: number;
  notes: string;
  watched_at: string;
  watched_date: string;
}

export interface User {
  user_id: number;
  username: string;
  jwt_token: string;
}

export interface ModelInfo {
  model_type: string;
  version: string;
  metrics: Record<string, number>;
}

export interface PaginatedDramas {
  items: ApiDrama[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface ApiDrama {
  id: number;
  tmdb_id: number | null;
  titre: string;
  titre_original: string | null;
  date_diffusion: string | null;
  nb_episodes: number | null;
  nb_saisons: number | null;
  synopsis: string | null;
  note_moyenne: number | null;
  nb_votes: number | null;
  langue_originale: string | null;
  pays_origine: string | null;
  source: string;
  date_creation: string;
  date_modification: string;
}

export interface GenreResponse {
  id: number;
  nom: string;
  description: string | null;
}

export interface RegisteredUser {
  id: number;
  pseudonyme: string;
  date_inscription: string;
  role: string;
  consentement_collecte: boolean;
  consentement_marketing: boolean;
}

export interface RatingResponse {
  id: number;
  utilisateur_id: number;
  kdrama_id: number;
  note: number;
  commentaire: string | null;
  date_note: string;
}

export interface PaginatedRatings {
  items: RatingResponse[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface CarouselSlide {
  id: number;
  icon: string;
  title: string;
  description: string;
  gradient: string;
  image: string;
}

export type Page = 'home' | 'search' | 'recommendations' | 'favorites' | 'history' | 'profile' | 'login';
export type FlashType = 'success' | 'error' | 'info';
export interface FlashMessage {
  id: number;
  type: FlashType;
  text: string;
}
