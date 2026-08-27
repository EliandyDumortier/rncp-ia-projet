import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { App } from './App';

describe('App — Accessibility (RGAA 4.1)', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('renders skip link (RGAA 1.6)', () => {
    render(<App />);
    expect(screen.getByText('Aller au contenu principal')).toBeInTheDocument();
  });

  it('renders main landmark with id (RGAA)', () => {
    render(<App />);
    expect(document.getElementById('contenu-principal')).toBeInTheDocument();
  });

  it('renders header banner landmark (RGAA)', () => {
    render(<App />);
    expect(document.querySelector('[role="banner"]')).toBeInTheDocument();
  });

  it('renders footer contentinfo landmark (RGAA)', () => {
    render(<App />);
    expect(document.querySelector('[role="contentinfo"]')).toBeInTheDocument();
  });

  it('renders nav with aria-label (RGAA 1.3)', () => {
    render(<App />);
    expect(screen.getByLabelText('Menu principal')).toBeInTheDocument();
  });

  it('renders h1 on home page (RGAA 9.1)', () => {
    render(<App />);
    expect(screen.getByRole('heading', { level: 1 })).toBeInTheDocument();
  });
});

describe('App — Home page (US-03)', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('displays popular dramas on home page', () => {
    render(<App />);
    expect(screen.getByText('Crash Landing on You')).toBeInTheDocument();
    expect(screen.getByText('Goblin (Guardian: The Lonely and Great God)')).toBeInTheDocument();
  });

  it('displays trending section with h2 (RGAA 9.1)', () => {
    render(<App />);
    expect(screen.getByText('Dramas populaires')).toBeInTheDocument();
  });
});

describe('App — Navigation', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('navigates to search page when clicking nav', async () => {
    const user = userEvent.setup();
    render(<App />);
    const navButtons = screen.getAllByText('Recherche');
    await user.click(navButtons[0]);
    expect(screen.getByPlaceholderText('Titre, mot-clé...')).toBeInTheDocument();
  });

  it('navigates to login page when clicking Connexion', async () => {
    const user = userEvent.setup();
    render(<App />);
    await user.click(screen.getByText('Connexion'));
    expect(screen.getByLabelText('Nom d\'utilisateur')).toBeInTheDocument();
    expect(screen.getByLabelText('Mot de passe')).toBeInTheDocument();
  });
});

describe('App — Search (US-01, US-02)', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('filters results by keyword', async () => {
    const user = userEvent.setup();
    render(<App />);
    await user.click(screen.getByText('Recherche'));
    const input = screen.getByLabelText('Rechercher un K-Drama');
    await user.type(input, 'crash');
    expect(screen.getByText('Crash Landing on You')).toBeInTheDocument();
    expect(screen.queryByText('Goblin (Guardian: The Lonely and Great God)')).not.toBeInTheDocument();
  });

  it('shows no results message', async () => {
    const user = userEvent.setup();
    render(<App />);
    await user.click(screen.getByText('Recherche'));
    const input = screen.getByLabelText('Rechercher un K-Drama');
    await user.type(input, 'zzzznonexistent');
    expect(screen.getByText('Aucun résultat trouvé.')).toBeInTheDocument();
  });
});

describe('App — Login (US-10)', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('shows error when fields are empty', async () => {
    const user = userEvent.setup();
    render(<App />);
    const navButtons = screen.getAllByText('Connexion');
    await user.click(navButtons[0]);
    await user.click(screen.getByRole('button', { name: 'Se connecter' }));
    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });
  });

  it('shows demo credentials hint', async () => {
    const user = userEvent.setup();
    render(<App />);
    const navButtons = screen.getAllByText('Connexion');
    await user.click(navButtons[0]);
    expect(screen.getByText(/user \/ user123/i)).toBeInTheDocument();
  });
});
