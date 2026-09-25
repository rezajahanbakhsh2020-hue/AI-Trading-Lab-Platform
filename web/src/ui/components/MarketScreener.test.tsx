import { render, screen, fireEvent, cleanup, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, afterEach } from 'vitest';
import { MarketScreener } from './MarketScreener';
import { I18nProvider } from '../../i18n';
import { MarketScreenerItem } from '../../architecture/screener';

const TEST_ITEMS: MarketScreenerItem[] = [
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

describe('MarketScreener UI Component', () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it('renders screener controls and heatmap tiles by default after loading API dataset', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        success: true,
        data: {
          items: TEST_ITEMS.map(i => ({
            symbol: i.symbol,
            display_name: i.displayName,
            category: i.category,
            price: i.price,
            change_24h_percent: i.change24hPercent,
            volume_24h_usd: i.volume24hUsd,
            volatility_percent: i.volatilityPercent,
            signal_action: i.signalAction,
            signal_confidence: i.signalConfidence,
          })),
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
          total_count: 2,
        },
      }),
    }));

    const { container } = render(
      <I18nProvider>
        <MarketScreener />
      </I18nProvider>
    );

    await waitFor(() => {
      expect(container.textContent).toContain('24h Market Performance Heatmap');
    });
    expect(container.textContent).toContain('XAUUSD');
  });

  it('renders with itemsOverride without API call', () => {
    const { container } = render(
      <I18nProvider>
        <MarketScreener itemsOverride={TEST_ITEMS} />
      </I18nProvider>
    );
    expect(container.textContent).toContain('24h Market Performance Heatmap');
    expect(container.textContent).toContain('XAUUSD');
    expect(container.textContent).toContain('EURUSD');
  });

  it('allows switching between list and heatmap views and renders truthful unavailable states', () => {
    const { container } = render(
      <I18nProvider>
        <MarketScreener itemsOverride={TEST_ITEMS} />
      </I18nProvider>
    );

    const buttons = screen.getAllByRole('button');
    const listViewBtn = buttons.find((btn) => btn.textContent?.includes('List View'));
    expect(listViewBtn).toBeDefined();

    if (listViewBtn) {
      fireEvent.click(listViewBtn);
    }

    // Should display table headers in list view
    expect(container.textContent).toContain('24h Volume');
    expect(container.textContent).toContain('Category');
    // Should display truthful "NO SIGNAL" and "—" for unavailable EURUSD fields
    expect(container.textContent).toContain('NO SIGNAL');
    expect(container.textContent).toContain('—');
  });

  it('triggers onSelectSymbol callback when asset tile button is clicked', () => {
    const handleSelect = vi.fn();
    render(
      <I18nProvider>
        <MarketScreener itemsOverride={TEST_ITEMS} onSelectSymbol={handleSelect} />
      </I18nProvider>
    );

    const buttons = screen.getAllByRole('button');
    const xauBtn = buttons.find((btn) => btn.textContent?.includes('XAUUSD'));
    expect(xauBtn).toBeDefined();

    if (xauBtn) {
      fireEvent.click(xauBtn);
    }

    expect(handleSelect).toHaveBeenCalledWith('XAUUSD');
  });
});
