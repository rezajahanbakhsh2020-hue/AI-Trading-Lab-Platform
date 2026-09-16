import { describe, it, expect } from 'vitest';
import {
  INITIAL_SCREENER_ITEMS,
  filterScreenerItems,
  generateHeatmapTiles,
} from './screener';

describe('screener architecture helpers', () => {
  it('contains initial screener items across asset categories', () => {
    expect(INITIAL_SCREENER_ITEMS.length).toBeGreaterThan(0);
    const categories = new Set(INITIAL_SCREENER_ITEMS.map((item) => item.category));
    expect(categories.has('CRYPTO')).toBe(true);
    expect(categories.has('COMMODITIES')).toBe(true);
    expect(categories.has('FOREX')).toBe(true);
    expect(categories.has('INDICES')).toBe(true);
  });

  it('filters screener items by category', () => {
    const cryptoOnly = filterScreenerItems(INITIAL_SCREENER_ITEMS, 'CRYPTO', '');
    expect(cryptoOnly.every((i) => i.category === 'CRYPTO')).toBe(true);
  });

  it('filters screener items by search query', () => {
    const goldMatches = filterScreenerItems(INITIAL_SCREENER_ITEMS, 'ALL', 'gold');
    expect(goldMatches.length).toBe(1);
    expect(goldMatches[0].symbol).toBe('XAUUSD');
  });

  it('filters screener items by signal action', () => {
    const buyOnly = filterScreenerItems(INITIAL_SCREENER_ITEMS, 'ALL', '', 'BUY');
    expect(buyOnly.every((i) => i.signalAction === 'BUY')).toBe(true);
  });

  it('generates heatmap tiles with normalized intensity', () => {
    const tiles = generateHeatmapTiles(INITIAL_SCREENER_ITEMS);
    expect(tiles.length).toBe(INITIAL_SCREENER_ITEMS.length);
    tiles.forEach((tile) => {
      expect(tile.intensity).toBeGreaterThanOrEqual(0.0);
      expect(tile.intensity).toBeLessThanOrEqual(1.0);
    });
  });
});
