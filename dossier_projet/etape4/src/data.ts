import type { Drama, CarouselSlide, ApiDrama, GenreResponse } from "./types";
import { dataApi } from "./api";
import { fetchDramasFromSupabase } from "./supabaseClient";

export const dramas: Drama[] = [
  {
    id: 1,
    title: "Crash Landing on You",
    genres: ["Romance", "Drama", "Comedy"],
    rating: 9.5,
    year: 2019,
    episodes: 16,
    synopsis:
      "A South Korean heiress accidentally crash-lands in North Korea after a paragliding storm. A North Korean officer hides her and helps her return home, as they fall in love.",
    poster:
      "https://images.pexels.com/photos/1520760/pexels-photo-1520760.jpeg?auto=compress&cs=tinysrgb&w=400&h=600&fit=crop",
  },
  {
    id: 2,
    title: "Goblin (Guardian: The Lonely and Great God)",
    genres: ["Fantasy", "Romance", "Drama"],
    rating: 9.3,
    year: 2016,
    episodes: 16,
    synopsis:
      "An immortal general, cursed to live eternally, seeks his human bride, the only person who can end his curse.",
    poster:
      "https://images.pexels.com/photos/1704488/pexels-photo-1704488.jpeg?auto=compress&cs=tinysrgb&w=400&h=600&fit=crop",
  },
  {
    id: 3,
    title: "Itaewon Class",
    genres: ["Drama", "Business", "Revenge"],
    rating: 8.9,
    year: 2020,
    episodes: 16,
    synopsis:
      "A young man with a turbulent past opens a bar in Itaewon and seeks to avenge his father while building an empire.",
    poster:
      "https://images.pexels.com/photos/1858175/pexels-photo-1858175.jpeg?auto=compress&cs=tinysrgb&w=400&h=600&fit=crop",
  },
  {
    id: 4,
    title: "Descendants of the Sun",
    genres: ["Romance", "Action", "Military"],
    rating: 9.1,
    year: 2016,
    episodes: 16,
    synopsis:
      "A special forces soldier and a surgeon fall in love in a war-torn country.",
    poster:
      "https://images.pexels.com/photos/1382731/pexels-photo-1382731.jpeg?auto=compress&cs=tinysrgb&w=400&h=600&fit=crop",
  },
  {
    id: 5,
    title: "Vincenzo",
    genres: ["Crime", "Drama", "Comedy"],
    rating: 9.0,
    year: 2021,
    episodes: 20,
    synopsis:
      "An Italian mafia lawyer returns to South Korea to recover a hidden treasure, and finds himself fighting a corrupt conglomerate.",
    poster:
      "https://images.pexels.com/photos/1043471/pexels-photo-1043471.jpeg?auto=compress&cs=tinysrgb&w=400&h=600&fit=crop",
  },
  {
    id: 6,
    title: "Start-Up",
    genres: ["Romance", "Business", "Drama"],
    rating: 8.5,
    year: 2020,
    episodes: 16,
    synopsis:
      "Young entrepreneurs launch their startup in Korea's Silicon Valley, navigating between ambition and love.",
    poster:
      "https://images.pexels.com/photos/1130626/pexels-photo-1130626.jpeg?auto=compress&cs=tinysrgb&w=400&h=600&fit=crop",
  },
  {
    id: 7,
    title: "Kingdom",
    genres: ["Horror", "Historical", "Thriller"],
    rating: 8.8,
    year: 2019,
    episodes: 6,
    synopsis:
      "In medieval Korea, a mysterious plague turns people into zombies. The crown prince investigates to save his kingdom.",
    poster:
      "https://images.pexels.com/photos/1670977/pexels-photo-1670977.jpeg?auto=compress&cs=tinysrgb&w=400&h=600&fit=crop",
  },
  {
    id: 8,
    title: "Hometown Cha-Cha-Cha",
    genres: ["Romance", "Comedy", "Slice of Life"],
    rating: 8.7,
    year: 2021,
    episodes: 16,
    synopsis:
      "A Seoul dentist moves to a seaside village and meets a handyman who helps her adapt.",
    poster:
      "https://images.pexels.com/photos/1450353/pexels-photo-1450353.jpeg?auto=compress&cs=tinysrgb&w=400&h=600&fit=crop",
  },
  {
    id: 9,
    title: "The World of the Married",
    genres: ["Drama", "Romance", "Infidelity"],
    rating: 8.4,
    year: 2020,
    episodes: 16,
    synopsis:
      "A seemingly perfect couple's life unravels when secrets of infidelity are revealed.",
    poster:
      "https://images.pexels.com/photos/13074682/pexels-photo-13074682.jpeg?auto=compress&cs=tinysrgb&w=400&h=600&fit=crop",
  },
  {
    id: 10,
    title: "Signal",
    genres: ["Crime", "Mystery", "Thriller"],
    rating: 9.2,
    year: 2016,
    episodes: 16,
    synopsis:
      "A detective communicates with a detective from the past via a walkie-talkie, solving cold cases.",
    poster:
      "https://images.pexels.com/photos/1105666/pexels-photo-1105666.jpeg?auto=compress&cs=tinysrgb&w=400&h=600&fit=crop",
  },
];

export const allGenres: string[] = sortedUniqueGenres(dramas);

function sortedUniqueGenres(list: Drama[]): string[] {
  const set = new Set<string>();
  list.forEach((d) => d.genres.forEach((g) => set.add(g)));
  return Array.from(set).sort();
}

export const carouselSlides: CarouselSlide[] = [
  {
    id: 1,
    icon: "Search",
    title: "Smart Search",
    description:
      "Find the perfect K-Drama by title, keyword, or genre. Our catalog is regularly updated with top-rated community picks.",
    gradient: "from-rose-500 to-pink-600",
    image:
      "https://images.pexels.com/photos/6608885/pexels-photo-6608885.jpeg?auto=compress&cs=tinysrgb&w=1280&h=720&fit=crop",
  },
  {
    id: 2,
    icon: "Sparkles",
    title: "AI Recommendations",
    description:
      "Our hybrid model combines collaborative filtering and semantic synopsis analysis to recommend series tailored to your taste.",
    gradient: "from-violet-500 to-purple-600",
    image:
      "https://images.pexels.com/photos/8386440/pexels-photo-8386440.jpeg?auto=compress&cs=tinysrgb&w=1280&h=720&fit=crop",
  },
  {
    id: 3,
    icon: "Star",
    title: "Favorites Management",
    description:
      "Build your personal watchlist. Add or remove dramas in one click and find your favorites anytime.",
    gradient: "from-amber-500 to-orange-600",
    image:
      "https://images.pexels.com/photos/13074682/pexels-photo-13074682.jpeg?auto=compress&cs=tinysrgb&w=1280&h=720&fit=crop",
  },
  {
    id: 4,
    icon: "ShieldCheck",
    title: "Secure Authentication",
    description:
      "Your data is protected. Authentication is delegated to the AI API using JWT tokens, and favorites are stored locally with persistence.",
    gradient: "from-teal-500 to-cyan-600",
    image:
      "https://images.pexels.com/photos/36740854/pexels-photo-36740854.jpeg?auto=compress&cs=tinysrgb&w=1280&h=720&fit=crop",
  },
];

const PLACEHOLDER_POSTER =
  "https://images.pexels.com/photos/2873486/pexels-photo-2873486.jpeg?auto=compress&cs=tinysrgb&w=400&h=600&fit=crop";

function extractGenres(api: ApiDrama): string[] {
  const a = api as ApiDrama & {
    genre_names?: string[] | null;
    genres?: Array<{ nom?: string | null } | string> | null;
  };

  if (Array.isArray(a.genre_names)) {
    return a.genre_names.filter(
      (g): g is string => typeof g === "string" && g.trim().length > 0,
    );
  }

  if (Array.isArray(a.genres)) {
    return a.genres
      .map((g) => (typeof g === "string" ? g : (g?.nom ?? "")))
      .filter((g): g is string => typeof g === "string" && g.trim().length > 0);
  }

  return [];
}

export function apiDramaToDrama(api: ApiDrama): Drama {
  return {
    id: api.id,
    title: api.titre,
    genres: extractGenres(api),
    rating: api.note_moyenne ?? 0,
    year: api.date_diffusion ? new Date(api.date_diffusion).getFullYear() : 0,
    episodes: api.nb_episodes ?? 0,
    synopsis: api.synopsis ?? "",
    poster: (api as any).poster && ((api as any).poster as string).trim() ? (api as any).poster : PLACEHOLDER_POSTER,
  };
}

export async function fetchDramas(
  page: number = 1,
  pageSize: number = 20,
  search?: string,
  sortBy: string = "note_moyenne",
  sortOrder: "asc" | "desc" = "desc",
): Promise<{
  items: Drama[];
  total: number;
  totalPages: number;
  fallback: boolean;
}> {
  // Try Supabase first (real data source)
  try {
    const result = await fetchDramasFromSupabase(page, pageSize, search, sortBy, sortOrder);
    return {
      items: result.items,
      total: result.total,
      totalPages: result.totalPages,
      fallback: false,
    };
  } catch (supabaseError) {
    console.warn('Supabase fetch failed, trying API:', supabaseError);
  }

  // Fall back to API
  try {
    const result = await dataApi.listDramas(
      page,
      pageSize,
      search,
      sortBy,
      sortOrder,
    );

    // Always return API results if successful, even if empty
    return {
      items: result.items.map(apiDramaToDrama),
      total: result.total,
      totalPages: result.total_pages,
      fallback: false,
    };
  } catch (apiError) {
    console.warn('API fetch failed, using fallback data:', apiError);
  }

  // Final fallback to local hardcoded data
  let filtered = [...dramas];
  if (search) {
    const q = search.toLowerCase();
    filtered = filtered.filter((d) =>
      d.title.toLowerCase().includes(q) ||
      d.synopsis.toLowerCase().includes(q) ||
      d.genres.some((g) => g.toLowerCase().includes(q))
    );
  }
  filtered = filtered.sort((a, b) =>
    sortOrder === 'desc' ? b.rating - a.rating : a.rating - b.rating
  ).slice(0, pageSize);

  return {
    items: filtered,
    total: filtered.length,
    totalPages: 1,
    fallback: true,
  };
}

export async function fetchGenres(): Promise<string[]> {
  try {
    const genres: GenreResponse[] = await dataApi.listGenres();
    return genres.map((g) => g.nom).sort();
  } catch {
    return allGenres;
  }
}

export function truncateChars(text: string, length: number = 150): string {
  if (!text) return "";
  if (text.length <= length) return text;
  const slice = text.slice(0, length);
  const lastSpace = slice.lastIndexOf(" ");
  return (lastSpace > 0 ? slice.slice(0, lastSpace) : slice) + "…";
}

export function formatRating(rating: number | null | undefined): string {
  if (rating == null) return "Not rated";
  return `${rating.toFixed(1)} / 10`;
}

export function stars(rating: number | null | undefined): string {
  if (rating == null) return "Not rated";
  const full = Math.round(rating / 2);
  return "★".repeat(full) + "☆".repeat(5 - full);
}
