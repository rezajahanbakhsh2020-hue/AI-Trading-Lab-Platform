import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import { describe, it, expect, vi, afterEach } from 'vitest';
import { MarketScreener } from './MarketScreener';
import { I18nProvider } from '../../i18n';

describe('MarketScreener UI Component', () => {
  afterEach(() => {
    cleanup();
  });

  it('renders screener controls and heatmap tiles by default', () => {
    const { container } = render(
      <I18nProvider>
        <MarketScreener />
      </I18nProvider>
    );
    expect(container.textContent).toContain('24h Market Performance Heatmap');
    expect(container.textContent).toContain('BTCUSD');
    expect(container.textContent).toContain('XAUUSD');
  });

  it('allows switching between list and heatmap views', () => {
    const { container } = render(
      <I18nProvider>
        <MarketScreener />
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
  });

  it('triggers onSelectSymbol callback when asset tile button is clicked', () => {
    const handleSelect = vi.fn();
    render(
      <I18nProvider>
        <MarketScreener onSelectSymbol={handleSelect} />
      </I18nProvider>
    );

    const buttons = screen.getAllByRole('button');
    const btcBtn = buttons.find((btn) => btn.textContent?.includes('BTCUSD'));
    expect(btcBtn).toBeDefined();

    if (btcBtn) {
      fireEvent.click(btcBtn);
    }

    expect(handleSelect).toHaveBeenCalledWith('BTCUSD');
  });
});
