import { describe, it, expect } from 'vitest';
import { dramas, allGenres, truncateChars, formatRating, stars } from './data';

describe('Data module', () => {
  it('has a non-empty drama catalogue', () => {
    expect(dramas.length).toBeGreaterThan(0);
  });

  it('each drama has required fields', () => {
    for (const d of dramas) {
      expect(d.id).toBeDefined();
      expect(d.title).toBeDefined();
      expect(d.genres).toBeInstanceOf(Array);
      expect(d.rating).toBeGreaterThan(0);
      expect(d.synopsis).toBeDefined();
      expect(d.poster).toBeDefined();
    }
  });

  it('allGenres contains all unique genres', () => {
    const expected = new Set<string>();
    dramas.forEach((d) => d.genres.forEach((g) => expected.add(g)));
    expect(new Set(allGenres)).toEqual(expected);
  });
});

describe('Utility functions', () => {
  it('truncateChars does not truncate short text', () => {
    expect(truncateChars('Court', 150)).toBe('Court');
  });

  it('truncateChars truncates long text', () => {
    const long = 'a'.repeat(200);
    const result = truncateChars(long, 50);
    expect(result.length).toBeLessThanOrEqual(51);
    expect(result.endsWith('…')).toBe(true);
  });

  it('truncateChars handles null', () => {
    expect(truncateChars(null as unknown as string, 50)).toBe('');
  });

  it('formatRating formats correctly', () => {
    expect(formatRating(9.5)).toBe('9.5 / 10');
  });

  it('formatRating handles null', () => {
    expect(formatRating(null)).toBe('Not rated');
  });

  it('stars converts rating to stars', () => {
    const result = stars(8.0);
    expect(result).toContain('★');
    expect(result).toContain('☆');
  });

  it('stars handles null', () => {
    expect(stars(null)).toBe('Not rated');
  });
});
