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

export interface CarouselSlide {
  id: number;
  icon: string;
  title: string;
  description: string;
  gradient: string;
  image: string;
}

export type Page = 'home' | 'search' | 'recommendations' | 'favorites' | 'profile' | 'login';
export type FlashType = 'success' | 'error' | 'info';
export interface FlashMessage {
  id: number;
  type: FlashType;
  text: string;
}
