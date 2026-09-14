import { WATCHLIST_SYMBOLS } from "../../architecture/marketData";

export function MarketPulse() {
  return (
    <div className="market-pulse-strip" aria-label="Market Pulse Ticker Strip">
      <div className="pulse-track">
        {WATCHLIST_SYMBOLS.map((item) => (
          <div className="pulse-item" key={item.symbol}>
            <span className="pulse-symbol">{item.symbol}</span>
            <span className="pulse-name">{item.category}</span>
            <span className="pulse-status">
              {item.status === "Disconnected" ? "Disconnected" : "Active"}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
