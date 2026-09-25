export type AssetCategory = 'ALL' | 'COMMODITIES' | 'FOREX' | 'CRYPTO' | 'INDICES';

export interface MarketScreenerItem {
  symbol: string;
  displayName: string;
  category: Exclude<AssetCategory, 'ALL'>;
  price?: number | null;
  change24hPercent?: number | null;
  volume24hUsd?: number | null;
  volatilityPercent?: number | null;
  signalAction?: 'BUY' | 'SELL' | 'HOLD' | null;
  signalConfidence?: number | null;
}

export interface HeatmapTile {
  symbol: string;
  displayName: string;
  category: Exclude<AssetCategory, 'ALL'>;
  change24hPercent?: number | null;
  intensity: number; // 0.0 to 1.0
  isPositive: boolean;
  signalAction?: 'BUY' | 'SELL' | 'HOLD' | null;
}

export interface MarketScreenerResult {
  items: MarketScreenerItem[];
  heatmapTiles: HeatmapTile[];
  totalCount: number;
  appliedCategory?: string | null;
  appliedSearch?: string | null;
}

export function filterScreenerItems(
  items: MarketScreenerItem[],
  category: AssetCategory,
  searchQuery: string,
  signalFilter?: string
): MarketScreenerItem[] {
  const query = searchQuery.trim().toLowerCase();
  return items.filter((item) => {
    if (category !== 'ALL' && item.category !== category) {
      return false;
    }
    if (query) {
      const matchSymbol = item.symbol.toLowerCase().includes(query);
      const matchName = item.displayName.toLowerCase().includes(query);
      if (!matchSymbol && !matchName) {
        return false;
      }
    }
    if (signalFilter && signalFilter !== 'ALL') {
      if (signalFilter === 'NO_SIGNAL' || signalFilter === 'NO SIGNAL') {
        if (item.signalAction) {
          return false;
        }
      } else if (item.signalAction !== signalFilter) {
        return false;
      }
    }
    return true;
  });
}

export function generateHeatmapTiles(items: MarketScreenerItem[]): HeatmapTile[] {
  if (items.length === 0) return [];
  const validChanges = items
    .map((i) => (i.change24hPercent != null ? Math.abs(i.change24hPercent) : null))
    .filter((val): val is number => val != null);

  const maxAbsChange = validChanges.length > 0 ? Math.max(...validChanges) : 1.0;
  const safeMax = maxAbsChange > 0 ? maxAbsChange : 1.0;

  return items.map((item) => {
    const chg = item.change24hPercent;
    const intensity = chg != null ? Math.min(1.0, Math.abs(chg) / safeMax) : 0;
    return {
      symbol: item.symbol,
      displayName: item.displayName,
      category: item.category,
      change24hPercent: chg ?? null,
      intensity: Math.round(intensity * 100) / 100,
      isPositive: chg != null ? chg >= 0 : true,
      signalAction: item.signalAction ?? null,
    };
  });
}

export async function fetchMarketScreener(
  token?: string | null,
  category?: AssetCategory,
  searchQuery?: string,
  signalFilter?: string
): Promise<{ success: boolean; data?: MarketScreenerResult; message?: string }> {
  try {
    const params = new URLSearchParams();
    if (category && category !== 'ALL') params.set('category', category);
    if (searchQuery) params.set('search_query', searchQuery);
    if (signalFilter && signalFilter !== 'ALL') params.set('signal_filter', signalFilter);

    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const resp = await fetch(`/api/v1/screener?${params.toString()}`, {
      method: 'GET',
      headers,
    });

    if (!resp.ok) {
      return { success: false, message: `HTTP error ${resp.status}` };
    }

    const json = await resp.json();
    if (!json.success || !json.data) {
      return { success: false, message: json.error || 'Failed to fetch screener dataset' };
    }

    const rawData = json.data;
    const items: MarketScreenerItem[] = (rawData.items || []).map((it: any) => ({
      symbol: it.symbol,
      displayName: it.display_name,
      category: it.category,
      price: it.price ?? null,
      change24hPercent: it.change_24h_percent ?? null,
      volume24hUsd: it.volume_24h_usd ?? null,
      volatilityPercent: it.volatility_percent ?? null,
      signalAction: it.signal_action ?? null,
      signalConfidence: it.signal_confidence ?? null,
    }));

    const heatmapTiles: HeatmapTile[] = (rawData.heatmap_tiles || []).map((tile: any) => ({
      symbol: tile.symbol,
      displayName: tile.display_name,
      category: tile.category,
      change24hPercent: tile.change_24h_percent ?? null,
      intensity: tile.intensity ?? 0,
      isPositive: tile.is_positive ?? true,
      signalAction: tile.signal_action ?? null,
    }));

    return {
      success: true,
      data: {
        items,
        heatmapTiles,
        totalCount: rawData.total_count || items.length,
        appliedCategory: rawData.applied_category,
        appliedSearch: rawData.applied_search,
      },
    };
  } catch (err) {
    return { success: false, message: (err as Error).message };
  }
}
