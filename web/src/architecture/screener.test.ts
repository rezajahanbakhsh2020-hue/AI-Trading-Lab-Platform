import { describe, it, expect, vi } from 'vitest';
import {
  filterScreenerItems,
  generateHeatmapTiles,
  fetchMarketScreener,
  MarketScreenerItem,
} from './screener';

const MOCK_ITEMS: MarketScreenerItem[] = [
  {
    symbol: 'XAUUSD',
    displayName: 'Gold / US Dollar',
    category: 'COMMODITIES',
    price: 2701.0,
    change24hPercent: 1.25,
    volume24hUsd: 45000000000,
    volatilityPercent: null,
    signalAction: 'BUY',
    signalConfidence: 0.85,
  },
  {
    symbol: 'EURUSD',
    displayName: 'Euro / US Dollar',
    category: 'FOREX',
    price: null,
    change24hPercent: null,
    volume24hUsd: null,
    volatilityPercent: null,
    signalAction: null,
    signalConfidence: null,
  },
];

describe('screener architecture helpers', () => {
  it('filters screener items by category', () => {
    const commOnly = filterScreenerItems(MOCK_ITEMS, 'COMMODITIES', '');
    expect(commOnly.every((i) => i.category === 'COMMODITIES')).toBe(true);
    expect(commOnly.length).toBe(1);
  });

  it('filters screener items by search query', () => {
    const goldMatches = filterScreenerItems(MOCK_ITEMS, 'ALL', 'gold');
    expect(goldMatches.length).toBe(1);
    expect(goldMatches[0].symbol).toBe('XAUUSD');
  });

  it('filters screener items by signal action', () => {
    const buyOnly = filterScreenerItems(MOCK_ITEMS, 'ALL', '', 'BUY');
    expect(buyOnly.every((i) => i.signalAction === 'BUY')).toBe(true);

    const noSig = filterScreenerItems(MOCK_ITEMS, 'ALL', '', 'NO SIGNAL');
    expect(noSig.length).toBe(1);
    expect(noSig[0].symbol).toBe('EURUSD');
  });

  it('generates heatmap tiles with normalized intensity and handles null change', () => {
    const tiles = generateHeatmapTiles(MOCK_ITEMS);
    expect(tiles.length).toBe(MOCK_ITEMS.length);

    const xauTile = tiles.find((t) => t.symbol === 'XAUUSD')!;
    expect(xauTile.intensity).toBeGreaterThan(0);
    expect(xauTile.isPositive).toBe(true);

    const eurTile = tiles.find((t) => t.symbol === 'EURUSD')!;
    expect(eurTile.change24hPercent).toBeNull();
    expect(eurTile.intensity).toBe(0);
  });

  it('fetches market screener data from API', async () => {
    const fakeResponse = {
      success: true,
      data: {
        items: [
          {
            symbol: 'XAUUSD',
            display_name: 'Gold / US Dollar',
            category: 'COMMODITIES',
            price: 2701.0,
            change_24h_percent: 1.25,
            volume_24h_usd: null,
            volatility_percent: null,
            signal_action: 'BUY',
            signal_confidence: 0.85,
          },
        ],
        heatmap_tiles: [
          {
            symbol: 'XAUUSD',
            display_name: 'Gold / US Dollar',
            category: 'COMMODITIES',
            change_24h_percent: 1.25,
            intensity: 1.0,
            is_positive: true,
            signal_action: 'BUY',
          },
        ],
        total_count: 1,
      },
    };

    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => fakeResponse,
    }));

    const res = await fetchMarketScreener('test_token', 'COMMODITIES');
    expect(res.success).toBe(true);
    expect(res.data?.items[0].symbol).toBe('XAUUSD');
    expect(res.data?.items[0].price).toBe(2701.0);
    expect(res.data?.items[0].signalAction).toBe('BUY');

    vi.unstubAllGlobals();
  });
});
