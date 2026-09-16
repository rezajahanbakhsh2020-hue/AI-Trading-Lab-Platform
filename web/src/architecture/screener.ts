export type AssetCategory = 'ALL' | 'COMMODITIES' | 'FOREX' | 'CRYPTO' | 'INDICES';

export interface MarketScreenerItem {
  symbol: string;
  displayName: string;
  category: Exclude<AssetCategory, 'ALL'>;
  price: number;
  change24hPercent: number;
  volume24hUsd: number;
  volatilityPercent: number;
  signalAction?: 'BUY' | 'SELL' | 'HOLD' | null;
  signalConfidence?: number | null;
}

export interface HeatmapTile {
  symbol: string;
  displayName: string;
  category: Exclude<AssetCategory, 'ALL'>;
  change24hPercent: number;
  intensity: number; // 0.0 to 1.0
  isPositive: boolean;
  signalAction?: 'BUY' | 'SELL' | 'HOLD' | null;
}

export const INITIAL_SCREENER_ITEMS: MarketScreenerItem[] = [
  {
    symbol: 'BTCUSD',
    displayName: 'Bitcoin / US Dollar',
    category: 'CRYPTO',
    price: 68450.0,
    change24hPercent: 3.85,
    volume24hUsd: 38000000000.0,
    volatilityPercent: 3.1,
    signalAction: 'BUY',
    signalConfidence: 0.92,
  },
  {
    symbol: 'ETHUSD',
    displayName: 'Ethereum / US Dollar',
    category: 'CRYPTO',
    price: 2640.0,
    change24hPercent: -1.2,
    volume24hUsd: 19000000000.0,
    volatilityPercent: 3.65,
    signalAction: 'SELL',
    signalConfidence: 0.74,
  },
  {
    symbol: 'SOLUSD',
    displayName: 'Solana / US Dollar',
    category: 'CRYPTO',
    price: 175.2,
    change24hPercent: 5.4,
    volume24hUsd: 6200000000.0,
    volatilityPercent: 4.8,
    signalAction: 'BUY',
    signalConfidence: 0.85,
  },
  {
    symbol: 'XAUUSD',
    displayName: 'Gold / US Dollar',
    category: 'COMMODITIES',
    price: 2685.5,
    change24hPercent: 1.42,
    volume24hUsd: 45200000000.0,
    volatilityPercent: 1.12,
    signalAction: 'BUY',
    signalConfidence: 0.88,
  },
  {
    symbol: 'XAGUSD',
    displayName: 'Silver / US Dollar',
    category: 'COMMODITIES',
    price: 31.4,
    change24hPercent: 2.15,
    volume24hUsd: 8700000000.0,
    volatilityPercent: 1.85,
    signalAction: 'BUY',
    signalConfidence: 0.81,
  },
  {
    symbol: 'EURUSD',
    displayName: 'Euro / US Dollar',
    category: 'FOREX',
    price: 1.0845,
    change24hPercent: -0.35,
    volume24hUsd: 120000000000.0,
    volatilityPercent: 0.45,
    signalAction: 'HOLD',
    signalConfidence: 0.6,
  },
  {
    symbol: 'GBPUSD',
    displayName: 'British Pound / US Dollar',
    category: 'FOREX',
    price: 1.298,
    change24hPercent: 0.12,
    volume24hUsd: 85000000000.0,
    volatilityPercent: 0.58,
    signalAction: 'HOLD',
    signalConfidence: 0.65,
  },
  {
    symbol: 'USDJPY',
    displayName: 'US Dollar / Japanese Yen',
    category: 'FOREX',
    price: 152.3,
    change24hPercent: 0.78,
    volume24hUsd: 98000000000.0,
    volatilityPercent: 0.72,
    signalAction: 'BUY',
    signalConfidence: 0.79,
  },
  {
    symbol: 'SPX500',
    displayName: 'S&P 500 Index',
    category: 'INDICES',
    price: 5860.2,
    change24hPercent: 0.45,
    volume24hUsd: 65000000000.0,
    volatilityPercent: 0.82,
    signalAction: 'BUY',
    signalConfidence: 0.77,
  },
  {
    symbol: 'NAS100',
    displayName: 'Nasdaq 100 Index',
    category: 'INDICES',
    price: 20350.8,
    change24hPercent: 0.92,
    volume24hUsd: 72000000000.0,
    volatilityPercent: 1.15,
    signalAction: 'BUY',
    signalConfidence: 0.83,
  },
];

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
      if (item.signalAction !== signalFilter) {
        return false;
      }
    }
    return true;
  });
}

export function generateHeatmapTiles(items: MarketScreenerItem[]): HeatmapTile[] {
  if (items.length === 0) return [];
  const maxAbsChange = Math.max(...items.map((i) => Math.abs(i.change24hPercent))) || 1.0;

  return items.map((item) => {
    const intensity = Math.min(1.0, Math.abs(item.change24hPercent) / maxAbsChange);
    return {
      symbol: item.symbol,
      displayName: item.displayName,
      category: item.category,
      change24hPercent: item.change24hPercent,
      intensity: Math.round(intensity * 100) / 100,
      isPositive: item.change24hPercent >= 0,
      signalAction: item.signalAction,
    };
  });
}
