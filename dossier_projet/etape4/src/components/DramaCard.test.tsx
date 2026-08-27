import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { DramaCard } from '../DramaCard';
import type { Drama } from './types';

const mockDrama: Drama = {
  id: 1,
  title: 'Test Drama',
  genres: ['Romance', 'Drama'],
  rating: 9.0,
  year: 2020,
  episodes: 16,
  synopsis: 'A test synopsis.',
  poster: 'https://example.com/poster.jpg',
};

describe('DramaCard', () => {
  it('renders drama title and rating', () => {
    render(
      <DramaCard
        drama={mockDrama}
        isFav={false}
        onToggleFav={() => {}}
      />
    );
    expect(screen.getByText('Test Drama')).toBeInTheDocument();
    expect(screen.getByText('9.0 / 10')).toBeInTheDocument();
  });

  it('renders descriptive alt text for poster (RGAA 1.2)', () => {
    render(
      <DramaCard
        drama={mockDrama}
        isFav={false}
        onToggleFav={() => {}}
      />
    );
    expect(screen.getByAlt('Affiche du K-Drama Test Drama')).toBeInTheDocument();
  });

  it('renders favorite button with aria-label (RGAA 7.1)', () => {
    render(
      <DramaCard
        drama={mockDrama}
        isFav={false}
        onToggleFav={() => {}}
      />
    );
    expect(screen.getByLabelText('Ajouter Test Drama aux favoris')).toBeInTheDocument();
  });

  it('renders h3 title (RGAA 9.1)', () => {
    render(
      <DramaCard
        drama={mockDrama}
        isFav={false}
        onToggleFav={() => {}}
      />
    );
    expect(screen.getByRole('heading', { level: 3 })).toBeInTheDocument();
  });

  it('renders genres as list items (RGAA 9.3)', () => {
    render(
      <DramaCard
        drama={mockDrama}
        isFav={false}
        onToggleFav={() => {}}
      />
    );
    expect(screen.getByText('Romance')).toBeInTheDocument();
    expect(screen.getByText('Drama')).toBeInTheDocument();
  });
});
