import type { PortDescriptionPayload, PresentedSignalPayload } from "./hostView";

/**
 * Test-only fixtures for unit and component testing.
 * These constants are strictly isolated from application runtime.
 */
export const SAMPLE_CONNECTED_PORT: PortDescriptionPayload = {
  name: "Project1GatewayAdapter",
  port: "Project1IntegrationPort",
  connected: true,
  status: "active",
  message: "Connected to Project 1 Integration Gateway.",
};

export const SAMPLE_REAL_PROJECT1_SIGNAL: PresentedSignalPayload = {
  signal_id: "p1_xauusd_1h_live_current",
  symbol: "XAUUSD",
  signal_type: "buy",
  timestamp: Math.floor(Date.now() / 1000) - 100,
  entry_price: 2650.5,
  stop_loss: 2635.0,
  take_profits: [2670.0, 2690.0, 2710.0],
  confidence: 0.88,
  strategy_name: "GoldTrendv1",
  timeframe: "1h",
  metadata: { source: "Project1", adapter: "Project1GatewayAdapter", provenance_type: "live_signal", is_live: true },
};
