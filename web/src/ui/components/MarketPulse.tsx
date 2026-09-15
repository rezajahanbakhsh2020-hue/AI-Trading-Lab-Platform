import type { MarketSymbol, MarketDataStatus } from "../../architecture/marketData";
import { useI18n } from "../../i18n";

type MarketPulseProps = {
  symbols?: MarketSymbol[];
  status?: MarketDataStatus;
  quotePrice?: number | null;
  change24hPct?: number | null;
};

export function MarketPulse({ symbols, quotePrice, change24hPct }: MarketPulseProps) {
  const { t, formatCurrency, formatPercent } = useI18n();

  const displaySymbols = symbols || [
    {
      symbol: "XAUUSD",
      name: "Spot Gold / US Dollar",
      category: "Commodities",
      status: quotePrice != null ? "connected" : "disconnected",
      lastPrice: quotePrice ?? null,
      change24hPct: change24hPct ?? null,
      primary: true,
    },
    {
      symbol: "EURUSD",
      name: "Euro / US Dollar",
      category: "Forex",
      status: "disconnected",
    },
    {
      symbol: "GBPUSD",
      name: "British Pound / US Dollar",
      category: "Forex",
      status: "disconnected",
    },
    {
      symbol: "BTCUSD",
      name: "Bitcoin / US Dollar",
      category: "Crypto",
      status: "disconnected",
    },
    {
      symbol: "SPX500",
      name: "S&P 500 Index",
      category: "Indices",
      status: "disconnected",
    },
  ] as MarketSymbol[];

  return (
    <div className="market-pulse-strip" aria-label="Market Pulse Ticker Strip">
      <div className="pulse-track">
        {displaySymbols.map((item) => {
          const isConnected = item.status === "connected";
          const priceText = item.lastPrice != null ? formatCurrency(item.lastPrice) : null;
          const changeText =
            item.change24hPct != null ? formatPercent(item.change24hPct) : null;

          return (
            <div className="pulse-item" key={item.symbol}>
              <span className="pulse-symbol">{item.symbol}</span>
              <span className="pulse-name">{item.category}</span>
              {isConnected && priceText ? (
                <span className="pulse-price" style={{ fontWeight: 600, color: "var(--accent-blue, #3B82F6)" }}>
                  {priceText} {changeText ? `(${changeText})` : ""}
                </span>
              ) : (
                <span className="pulse-status">
                  {item.status === "connected" ? t("status.connected") : t("status.disconnected")}
                </span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
