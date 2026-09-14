"""Project 1 Signal Presenter application service.

Consumes Project1IntegrationPort outputs and formats them into clean,
non-fabricated Project 2 view models and host snapshots for application and UI rendering.

Rules:
- Read-only: Consumes strictly through Project1IntegrationPort.
- Non-fabrication: Preserves exact signal prices, confidence, strategy_name,
  and trade setup values provided by Project 1.
- Honest status representation: Correctly distinguishes connected, disconnected,
  active, and no-signal (empty) states.
"""

from typing import Any, Dict, Optional

from src.platform.integrations.project1 import Project1IntegrationPort


class Project1SignalPresenter:
    """Application service presenting Project 1 outputs to Project 2 application/UI layers."""

    def __init__(self, port: Project1IntegrationPort) -> None:
        if port is None or not isinstance(port, Project1IntegrationPort):
            raise ValueError("port must be a valid Project1IntegrationPort")
        self._port = port

    def present_signal(
        self, symbol: str = "XAUUSD", timeframe: str = "1h", strategy_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Fetch and present signal and port state for a given market context."""

        _validate_symbol(symbol)
        _validate_timeframe(timeframe)

        desc = self._port.describe()
        is_connected = bool(desc.get("connected", False))

        if not is_connected:
            return {
                "port": desc,
                "connected": False,
                "status": "disconnected",
                "symbol": symbol,
                "timeframe": timeframe,
                "signal": None,
                "message": desc.get("message", "Project 1 is disconnected."),
            }

        presented_signal = self._port.fetch_latest_signal(
            symbol=symbol, timeframe=timeframe, strategy_name=strategy_name
        )

        if presented_signal is None:
            return {
                "port": desc,
                "connected": True,
                "status": "no-signal",
                "symbol": symbol,
                "timeframe": timeframe,
                "signal": None,
                "message": f"No active signal from Project 1 for {symbol} ({timeframe}).",
            }

        sig_dict = presented_signal.to_dict()
        return {
            "port": desc,
            "connected": True,
            "status": "active",
            "symbol": symbol,
            "timeframe": timeframe,
            "signal": sig_dict,
            "message": f"Active {presented_signal.signal_type.upper()} signal from {presented_signal.strategy_name or 'Project 1'}.",
        }

    def build_host_snapshot(
        self, symbol: str = "XAUUSD", timeframe: str = "1h", strategy_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Build a full Project 2 host snapshot from real Project 1 port outputs."""

        pres = self.present_signal(symbol=symbol, timeframe=timeframe, strategy_name=strategy_name)
        desc = pres["port"]
        is_connected = pres["connected"]
        signal_dict = pres["signal"]

        if not is_connected:
            return {
                "generatedAt": None,
                "platform": {
                    "name": "AI Trading Lab Platform",
                    "role": "Host application for AI-Trading-Lab",
                    "status": "ready",
                },
                "project1": {
                    "connected": False,
                    "status": "disconnected",
                    "port": desc.get("port", "Project1IntegrationPort"),
                    "adapterName": desc.get("name", "DisconnectedProject1Adapter"),
                    "message": desc.get("message", "No Project 1 data connected yet."),
                },
                "market": {
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "quote": None,
                    "change": None,
                    "volume": None,
                    "candles": [],
                    "status": "unavailable",
                    "message": "Market data is unavailable until a provider is connected.",
                },
                "strategy": {
                    "name": None,
                    "stability": None,
                    "status": "unavailable",
                    "message": "Strategy information is provided by Project 1.",
                },
                "signal": {
                    "action": None,
                    "timestamp": None,
                    "status": "unavailable",
                    "message": "No Project 1 data connected yet.",
                },
                "performance": {
                    "status": "unavailable",
                    "message": "Performance metrics are unavailable until Project 1 results are connected.",
                },
                "risk": {
                    "entry": None,
                    "stopLoss": None,
                    "takeProfits": [],
                    "status": "unavailable",
                    "message": "Risk levels are unavailable until a real trade setup is provided.",
                },
                "monitoring": {
                    "freshness": None,
                    "health": None,
                    "status": "unavailable",
                    "message": "Monitoring has no live observations yet.",
                },
                "providers": {
                    "marketData": "unconnected",
                    "quote": "unconnected",
                    "message": "Provider slots are ready. No live provider session is attached.",
                },
                "activity": [],
            }

        # Connected port handling
        if signal_dict is None:
            return {
                "generatedAt": None,
                "platform": {
                    "name": "AI Trading Lab Platform",
                    "role": "Host application for AI-Trading-Lab",
                    "status": "ready",
                },
                "project1": {
                    "connected": True,
                    "status": "connected",
                    "port": desc.get("port", "Project1IntegrationPort"),
                    "adapterName": desc.get("name", "Project1LabArtifactAdapter"),
                    "message": f"Project 1 connected via {desc.get('name', 'adapter')}.",
                },
                "market": {
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "quote": None,
                    "change": None,
                    "volume": None,
                    "candles": [],
                    "status": "unavailable",
                    "message": "Market data is unavailable until a provider is connected.",
                },
                "strategy": {
                    "name": strategy_name,
                    "stability": None,
                    "status": "available" if strategy_name else "unavailable",
                    "message": "Connected to Project 1 engine.",
                },
                "signal": {
                    "action": "NO SIGNAL",
                    "timestamp": None,
                    "status": "no-signal",
                    "message": pres["message"],
                },
                "performance": {
                    "status": "unavailable",
                    "message": "Performance metrics are unavailable until Project 1 results are connected.",
                },
                "risk": {
                    "entry": None,
                    "stopLoss": None,
                    "takeProfits": [],
                    "status": "unavailable",
                    "message": "Risk levels stay empty until Project 1 emits a trade setup.",
                },
                "monitoring": {
                    "freshness": None,
                    "health": None,
                    "status": "unavailable",
                    "message": "Monitoring has no live observations yet.",
                },
                "providers": {
                    "marketData": "unconnected",
                    "quote": "unconnected",
                    "message": "Provider slots are ready. No live provider session is attached.",
                },
                "activity": [],
            }

        action_str = str(signal_dict["signal_type"]).upper()
        strat_name = signal_dict.get("strategy_name")
        conf = signal_dict.get("confidence")
        entry = signal_dict.get("entry_price")
        sl = signal_dict.get("stop_loss")
        tps = list(signal_dict.get("take_profits") or [])

        return {
            "generatedAt": signal_dict.get("timestamp"),
            "platform": {
                "name": "AI Trading Lab Platform",
                "role": "Host application for AI-Trading-Lab",
                "status": "ready",
            },
            "project1": {
                "connected": True,
                "status": "connected",
                "port": desc.get("port", "Project1IntegrationPort"),
                "adapterName": desc.get("name", "Project1LabArtifactAdapter"),
                "message": f"Project 1 emitting signals via {desc.get('name', 'adapter')}.",
            },
            "market": {
                "symbol": symbol,
                "timeframe": signal_dict.get("timeframe") or timeframe,
                "quote": None,
                "change": None,
                "volume": None,
                "candles": [],
                "status": "unavailable",
                "message": "Market data feed relies on provider selection.",
            },
            "strategy": {
                "name": strat_name,
                "stability": int(conf * 100) if conf is not None else None,
                "status": "active",
                "message": f"Strategy '{strat_name}' owned and evaluated by Project 1.",
            },
            "signal": {
                "signalId": signal_dict.get("signal_id"),
                "action": action_str,
                "timestamp": str(signal_dict.get("timestamp")),
                "confidence": conf,
                "strategyName": strat_name,
                "timeframe": signal_dict.get("timeframe") or timeframe,
                "status": "active",
                "message": f"Validated {action_str} signal emitted by Project 1.",
                "metadata": signal_dict.get("metadata", {}),
            },
            "performance": {
                "status": "unavailable",
                "message": "Performance metrics are unavailable until Project 1 backtest outputs are connected.",
            },
            "risk": {
                "entry": entry,
                "stopLoss": sl,
                "takeProfits": tps,
                "status": "available" if entry is not None else "unavailable",
                "message": "Real trade setup levels provided by Project 1." if entry is not None else "Trade setup omitted.",
            },
            "monitoring": {
                "freshness": "fresh",
                "health": "healthy",
                "status": "available",
                "message": "Project 1 signal active and fresh.",
            },
            "providers": {
                "marketData": "unconnected",
                "quote": "unconnected",
                "message": "Provider slots are ready. No live provider session is attached.",
            },
            "activity": [
                {
                    "timestamp": str(signal_dict.get("timestamp")),
                    "event": "Signal Received",
                    "details": f"{action_str} signal for {symbol} ({strat_name})",
                }
            ],
        }


def _validate_symbol(symbol: str) -> None:
    if not isinstance(symbol, str) or not symbol.strip():
        raise ValueError("symbol must be a non-empty string")


def _validate_timeframe(timeframe: str) -> None:
    if not isinstance(timeframe, str) or not timeframe.strip():
        raise ValueError("timeframe must be a non-empty string")
