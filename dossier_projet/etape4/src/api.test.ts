import { afterEach, describe, expect, it, vi } from 'vitest';
import { apiClient, dataApi, DataAPIError, RecommendationAPIError } from './api';

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

afterEach(() => {
  localStorage.clear();
  vi.unstubAllGlobals();
});

describe('apiClient', () => {
  it('authenticates against the data API and stores the JWT', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ access_token: 'jwt-value' }));
    vi.stubGlobal('fetch', fetchMock);

    await expect(apiClient.authenticate('alice', 'secret')).resolves.toEqual({ access_token: 'jwt-value' });
    expect(localStorage.getItem('jwt_token')).toBe('jwt-value');
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/auth/login'),
      expect.objectContaining({ method: 'POST' })
    );
  });

  it('rejects an invalid login with a typed error', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({}, 401)));

    await expect(apiClient.authenticate('alice', 'wrong')).rejects.toMatchObject({
      name: 'RecommendationAPIError',
      status_code: 401,
    });
  });

  it('requires a JWT before requesting recommendations', async () => {
    await expect(apiClient.getRecommendations()).rejects.toBeInstanceOf(RecommendationAPIError);
  });

  it('maps a recommendation response and includes the authorization header', async () => {
    localStorage.setItem('jwt_token', 'jwt-value');
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({
      mode: 'user',
      recommendations: [{ kdrama_id: 7, titre: 'Signal', note_moyenne: 9.2, genres: ['Crime'] }],
    }));
    vi.stubGlobal('fetch', fetchMock);

    const result = await apiClient.getRecommendations({ user_id: 3, top_k: 5, genres: ['Crime'] });

    expect(result.mode).toBe('user');
    expect(result.recommendations[0]).toMatchObject({ id: 7, title: 'Signal', rating: 9.2 });
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/recommend'),
      expect.objectContaining({ headers: expect.objectContaining({ Authorization: 'Bearer jwt-value' }) })
    );
  });

  it('clears an expired JWT', async () => {
    localStorage.setItem('jwt_token', 'expired');
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({}, 401)));

    await expect(apiClient.getRecommendations()).rejects.toMatchObject({ status_code: 401 });
    expect(apiClient.isAuthenticated()).toBe(false);
  });

  it('returns model information and a successful health status with a JWT', async () => {
    localStorage.setItem('jwt_token', 'jwt-value');
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse({ version: '4.0', status: 'ready' }))
      .mockResolvedValueOnce(jsonResponse({ status: 'ok' }));
    vi.stubGlobal('fetch', fetchMock);

    await expect(apiClient.getModelInfo()).resolves.toMatchObject({ version: '4.0' });
    await expect(apiClient.healthCheck()).resolves.toBe(true);
  });
});

describe('dataApi', () => {
  it('serializes pagination, search and multiple genres', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ items: [], total: 0, total_pages: 0 }));
    vi.stubGlobal('fetch', fetchMock);

    await expect(dataApi.listDramas(2, 10, 'signal', 'titre', 'asc', ['Crime', 'Drama']))
      .resolves.toMatchObject({ total: 0 });
    expect(fetchMock.mock.calls[0][0]).toContain('page=2');
    expect(fetchMock.mock.calls[0][0]).toContain('genre=Crime%2CDrama');
  });

  it('reports a typed error for a missing drama', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({}, 404)));

    await expect(dataApi.getDrama(404)).rejects.toBeInstanceOf(DataAPIError);
  });

  it('requires authentication before changing a rating', async () => {
    await expect(dataApi.createRating(1, 9)).rejects.toMatchObject({ status_code: 401 });
  });

  it('posts a rating with the stored JWT', async () => {
    localStorage.setItem('jwt_token', 'jwt-value');
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ id: 1, note: 8 }));
    vi.stubGlobal('fetch', fetchMock);

    await expect(dataApi.createRating(1, 8, 'Great')).resolves.toMatchObject({ note: 8 });
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/kdramas/1/notes'),
      expect.objectContaining({ method: 'POST' })
    );
  });

  it('returns false when a health check cannot reach the API', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('offline')));

    await expect(dataApi.healthCheck()).resolves.toBe(false);
  });

  it('requires a JWT before accessing favorites', async () => {
    await expect(dataApi.listFavoris()).rejects.toMatchObject({ status_code: 401 });
  });

  it('adds a favorite and accepts a no-content deletion response', async () => {
    localStorage.setItem('jwt_token', 'jwt-value');
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse({ id: 4, kdrama_id: 1 }))
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    vi.stubGlobal('fetch', fetchMock);

    await expect(dataApi.addFavori(1)).resolves.toMatchObject({ kdrama_id: 1 });
    await expect(dataApi.removeFavori(1)).resolves.toBeUndefined();
    expect(fetchMock.mock.calls[0][1]).toMatchObject({ method: 'POST' });
    expect(fetchMock.mock.calls[1][1]).toMatchObject({ method: 'DELETE' });
  });
});
