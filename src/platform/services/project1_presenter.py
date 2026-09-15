"""Project 1 Signal Presenter application service.

Consumes Project1IntegrationPort outputs and formats them into clean,
non-fabricated Project 2 view models and host snapshots for application and UI rendering.
Enforces security boundary authorization checks for protected signal, strategy, and trade-setup data.

Rules:
- Read-only: Consumes strictly through Project1IntegrationPort.
- Non-fabrication: Preserves exact signal prices, confidence, strategy_name,
  and trade setup values provided by Project 1.
- Honest status representation: Correctly distinguishes connected, disconnected,
  active, and no-signal (empty) states.
"""

from typing import Any, Dict, Optional

from src.platform.domain.security import Permission
from src.platform.domain.user_authorization import UserAuthorization
from src.platform.integrations.project1 import Project1IntegrationPort
from src.platform.services.security import SecretSanitizer, SecurityBoundaryService


class Project1SignalPresenter:
    """Application service presenting Project 1 outputs to Project 2 application/UI layers."""

    def __init__(
        self,
        port: Project1IntegrationPort,
        security_service: Optional[SecurityBoundaryService] = None,
    ) -> None:
        if port is None or not isinstance(port, Project1IntegrationPort):
            raise ValueError("port must be a valid Project1IntegrationPort")
        if security_service is not None and not isinstance(
            security_service, SecurityBoundaryService
        ):
            raise ValueError("security_service must be a SecurityBoundaryService instance")
        self._port = port
        self._security_service = security_service or SecurityBoundaryService()

    def present_signal(
        self,
        symbol: str = "XAUUSD",
        timeframe: str = "1h",
        strategy_name: Optional[str] = None,
        user: Optional[UserAuthorization] = None,
    ) -> Dict[str, Any]:
        """Fetch and present signal and port state for a given market context, enforcing security boundary."""

        _validate_symbol(symbol)
        _validate_timeframe(timeframe)

        desc = self._port.describe()
        is_connected = bool(desc.get("connected", False))

        if user is not None:
            allowed, reason = self._security_service.authorize(user, "signals", action="read")
            if not allowed:
                return {
                    "port": desc,
                    "connected": is_connected,
                    "status": "unauthorized",
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "signal": None,
                    "message": f"Access denied: {reason}",
                }

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

        # Check permission for trade setup levels
        if user is not None and not user.has_permission(Permission.READ_TRADE_SETUPS):
            sig_dict["entry_price"] = None
            sig_dict["stop_loss"] = None
            sig_dict["take_profits"] = []

        # Sanitize metadata for all roles and filter protected payloads for non-admins
        raw_meta = sig_dict.get("metadata", {})
        if user is not None:
            sig_dict["metadata"] = self._security_service.filter_protected_payload(user, raw_meta)
        else:
            sig_dict["metadata"] = SecretSanitizer.sanitize_data(raw_meta)

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
        self,
        symbol: str = "XAUUSD",
        timeframe: str = "1h",
        strategy_name: Optional[str] = None,
        user: Optional[UserAuthorization] = None,
    ) -> Dict[str, Any]:
        """Build a full Project 2 host snapshot from real Project 1 port outputs, respecting user permissions."""

        pres = self.present_signal(
            symbol=symbol, timeframe=timeframe, strategy_name=strategy_name, user=user
        )
        desc = pres["port"]
        is_connected = pres["connected"]
        signal_dict = pres["signal"]

        if pres["status"] == "unauthorized":
            return {
                "generatedAt": None,
                "platform": {
                    "name": "AI Trading Lab Platform",
                    "role": "Host application for AI-Trading-Lab",
                    "status": "ready",
                },
                "project1": {
                    "connected": is_connected,
                    "status": desc.get("status", "disconnected"),
                    "port": desc.get("port", "Project1IntegrationPort"),
                    "adapterName": desc.get("name", "DisconnectedProject1Adapter"),
                    "message": pres["message"],
                },
                "market": {
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "quote": None,
                    "change": None,
                    "volume": None,
                    "candles": [],
                    "status": "unavailable",
                    "message": "Market data is restricted or unavailable.",
                },
                "strategy": {
                    "name": None,
                    "stability": None,
                    "status": "unavailable",
                    "message": "Strategy details restricted.",
                },
                "signal": {
                    "action": None,
                    "timestamp": None,
                    "status": "unauthorized",
                    "message": pres["message"],
                },
                "performance": {
                    "status": "unavailable",
                    "message": "Performance metrics restricted.",
                },
                "risk": {
                    "entry": None,
                    "stopLoss": None,
                    "takeProfits": [],
                    "status": "unavailable",
                    "message": "Risk levels restricted.",
                },
                "monitoring": {
                    "freshness": None,
                    "health": None,
                    "status": "unavailable",
                    "message": "Monitoring data restricted.",
                },
                "providers": {
                    "marketData": "unconnected",
                    "quote": "unconnected",
                    "message": "Provider information restricted.",
                },
                "activity": [],
            }

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

        # Mask strategy details for normal users if strategy info is protected
        strat_msg = f"Strategy '{strat_name}' owned and evaluated by Project 1."
        if user is not None and not user.is_admin and not user.has_permission(Permission.READ_STRATEGY_PARAMETERS):
            strat_msg = "Strategy evaluated by Project 1."

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
                "message": strat_msg,
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
                "message": "Real trade setup levels provided by Project 1." if entry is not None else "Trade setup omitted or restricted.",
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
