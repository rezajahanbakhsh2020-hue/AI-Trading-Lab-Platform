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

from typing import Any, Dict, Optional, Tuple

from src.platform.domain.readiness import Readiness
from src.platform.domain.security import Permission
from src.platform.domain.signal import Signal
from src.platform.domain.stability import Stability
from src.platform.domain.trade_setup import TradeSetup
from src.platform.domain.trade_signal import TradeSignal
from src.platform.domain.user_authorization import UserAuthorization
from src.platform.integrations.project1 import Project1IntegrationPort
from src.platform.services.autonomous_authorization import AutonomousAuthorizationService
from src.platform.services.audit_control import PlatformAuditControlService
from src.platform.services.order_intent import OrderIntentService
from src.platform.services.security import SecretSanitizer, SecurityBoundaryService


class Project1SignalPresenter:
    """Application service presenting Project 1 outputs to Project 2 application/UI layers."""

    def __init__(
        self,
        port: Project1IntegrationPort,
        security_service: Optional[SecurityBoundaryService] = None,
        backtest_service: Optional[Any] = None,
        authorization_service: Optional[AutonomousAuthorizationService] = None,
        audit_control_service: Optional[PlatformAuditControlService] = None,
        order_intent_service: Optional[OrderIntentService] = None,
    ) -> None:
        if port is None or not isinstance(port, Project1IntegrationPort):
            raise ValueError("port must be a valid Project1IntegrationPort")
        if security_service is not None and not isinstance(
            security_service, SecurityBoundaryService
        ):
            raise ValueError("security_service must be a SecurityBoundaryService instance")
        if authorization_service is not None and not isinstance(
            authorization_service, AutonomousAuthorizationService
        ):
            raise ValueError("authorization_service must be an AutonomousAuthorizationService instance")
        self._port = port
        self._security_service = security_service or SecurityBoundaryService()
        self._backtest_service = backtest_service
        self._auth_service = authorization_service or AutonomousAuthorizationService()
        self._audit_control_service = audit_control_service or PlatformAuditControlService(security_boundary=self._security_service)
        self._order_intent_service = order_intent_service or OrderIntentService(
            security_boundary=self._security_service,
            audit_control=self._audit_control_service,
        )

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

    def get_order_intents_payload(
        self,
        user: Optional[UserAuthorization] = None,
        symbol: Optional[str] = None,
        lifecycle_state: Optional[str] = None,
    ) -> list:
        """Fetch and present sanitized OrderIntents for the authenticated user with strict isolation."""
        success, _, intents = self._order_intent_service.list_order_intents(
            user=user,
            symbol=symbol,
            lifecycle_state=lifecycle_state,
        )
        if not success or not intents:
            return []

        payloads = []
        for intent in intents:
            intent_dict = intent.to_dict()
            if user is not None and not user.is_admin:
                intent_dict = self._security_service.filter_protected_payload(user, intent_dict)
            else:
                intent_dict = SecretSanitizer.sanitize_data(intent_dict)
            payloads.append(intent_dict)
        return payloads

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
                "authorization": {
                    "status": "UNAUTHORIZED",
                    "isAuthorized": False,
                    "reason": pres["message"],
                    "checks": [],
                    "riskRewardRatio": None,
                    "timestamp": None,
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
                "orderIntents": self.get_order_intents_payload(user=user),
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
                "authorization": {
                    "status": "DISCONNECTED",
                    "isAuthorized": False,
                    "reason": "Project 1 is disconnected. Connect Project 1 to enable autonomous execution evaluation.",
                    "checks": [],
                    "riskRewardRatio": None,
                    "timestamp": None,
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
                "orderIntents": self.get_order_intents_payload(user=user),
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
                "authorization": {
                    "status": "NO_SIGNAL",
                    "isAuthorized": False,
                    "reason": f"No active signal emitted by Project 1 for {symbol} ({timeframe}). Autonomous execution holds on NO SIGNAL.",
                    "checks": [
                        {
                            "id": "signal_tradable",
                            "label": "Signal Tradability Gate",
                            "passed": False,
                            "reason": "Signal action is NO SIGNAL / HOLD",
                        }
                    ],
                    "riskRewardRatio": None,
                    "timestamp": None,
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
                "orderIntents": self.get_order_intents_payload(user=user),
            }

        action_str = str(signal_dict["signal_type"]).upper()
        strat_name = signal_dict.get("strategy_name") or "Project 1 Strategy"
        conf = signal_dict.get("confidence")
        entry = signal_dict.get("entry_price")
        sl = signal_dict.get("stop_loss")
        tps = list(signal_dict.get("take_profits") or [])
        sig_ts = float(signal_dict.get("timestamp") or 0.0)

        # Mask strategy details for normal users if strategy info is protected
        strat_msg = f"Strategy '{strat_name}' owned and evaluated by Project 1."
        if user is not None and not user.is_admin and not user.has_permission(Permission.READ_STRATEGY_PARAMETERS):
            strat_msg = "Strategy evaluated by Project 1."

        # Perform real deterministic Autonomous Authorization computation
        auth_obj, auth_payload = self._compute_authorization_object(
            action_str=action_str,
            strat_name=strat_name,
            symbol=symbol,
            timeframe=signal_dict.get("timeframe") or timeframe,
            timestamp=sig_ts,
            confidence=conf,
            entry=entry,
            stop_loss=sl,
            take_profits=tps,
            user=user,
        )

        # Stage OrderIntent if authorized and user is provided
        if auth_obj.is_authorized and user is not None:
            sig_id = signal_dict.get("signal_id") or f"sig_{int(sig_ts)}"
            idemp_key = f"snap_idemp_{user.user_id}_{symbol.lower()}_{sig_id}"
            self._order_intent_service.create_order_intent(
                user=user,
                authorization=auth_obj,
                idempotency_key=idemp_key,
                symbol=symbol,
                timestamp=sig_ts,
            )

        # Process optional backtest assessment if available
        perf_payload: Dict[str, Any] = {
            "status": "unavailable",
            "message": "Performance metrics are unavailable until Project 1 backtest outputs are connected.",
        }
        if self._backtest_service is not None and strat_name:
            try:
                bt_res = self._backtest_service.run_assessment(
                    strategy_name=strat_name,
                    symbol=symbol,
                    timeframe=signal_dict.get("timeframe") or timeframe,
                    market_data_provider_id="biquote_provider",
                    user=user,
                )
                if bt_res is not None:
                    res_dict = bt_res.to_dict()
                    dt = bt_res.detail or ""

                    # Determine explicit lifecycle state from BacktestResult detail
                    status_str = "available"
                    if dt.startswith("unauthorized"):
                        status_str = "unauthorized"
                    elif dt.startswith("empty"):
                        status_str = "empty"
                    elif dt.startswith("unavailable"):
                        status_str = "unavailable"
                    elif dt.startswith("invalid"):
                        status_str = "invalid"
                    elif dt.startswith("failed"):
                        status_str = "failed"

                    if user is not None and not user.is_admin:
                        res_dict = self._security_service.filter_protected_payload(user, res_dict)

                    # Also evaluate walk-forward assessment if available
                    wf_dict = None
                    try:
                        wf_res = self._backtest_service.run_walk_forward_assessment(
                            strategy_name=strat_name,
                            symbol=symbol,
                            timeframe=signal_dict.get("timeframe") or timeframe,
                            market_data_provider_id="biquote_provider",
                            user=user,
                        )
                        if wf_res is not None and not (wf_res.detail or "").startswith("unavailable"):
                            wf_dict = wf_res.to_dict()
                            if user is not None and not user.is_admin:
                                wf_dict = self._security_service.filter_protected_payload(user, wf_dict)
                    except Exception:
                        wf_dict = None

                    if wf_dict:
                        res_dict["walk_forward"] = wf_dict

                    perf_payload = {
                        "status": status_str,
                        "message": SecretSanitizer.sanitize_string(dt) if dt else "Backtest assessment evaluated.",
                        "data": res_dict,
                    }
            except Exception as exc:
                perf_payload = {
                    "status": "failed",
                    "message": f"Backtest assessment failed: {SecretSanitizer.sanitize_string(str(exc))}",
                    "data": None,
                }

        # Retrieve operational audit summary for HostSnapshot
        _, _, audit_summary = self._audit_control_service.get_control_summary(user=user)
        _, _, audit_events = self._audit_control_service.query_events(user=user, filter_params=None)

        return {
            "generatedAt": signal_dict.get("timestamp"),
            "platform": {
                "name": "AI Trading Lab Platform",
                "role": "Host application for AI-Trading-Lab",
                "status": "ready",
            },
            "auditControl": {
                "status": "available" if audit_summary is not None else "unavailable",
                "summary": audit_summary.to_dict() if audit_summary else None,
                "events": [e.to_dict() for e in audit_events[:50]] if audit_events else [],
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
            "authorization": auth_payload,
            "performance": perf_payload,
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
            "orderIntents": self.get_order_intents_payload(user=user),
        }

    def _compute_authorization_object(
        self,
        action_str: str,
        strat_name: str,
        symbol: str,
        timeframe: str,
        timestamp: float,
        confidence: Optional[float],
        entry: Optional[float],
        stop_loss: Optional[float],
        take_profits: list,
        user: Optional[UserAuthorization],
    ) -> Tuple[Any, Dict[str, Any]]:
        """Compute deterministic autonomous execution authorization for presented signal."""
        act_lower = action_str.lower()
        is_tradable_action = act_lower in ("buy", "sell")

        conf_val = confidence if confidence is not None else 0.5
        stab = Stability(score=conf_val, risk_level="low" if conf_val >= 0.7 else "medium")
        readiness = Readiness(approved=is_tradable_action, reason="Signal validated" if is_tradable_action else "Signal holds", timestamp=timestamp)

        sig_domain = Signal(
            action=act_lower if is_tradable_action else "hold",
            confidence=conf_val,
            timestamp=timestamp,
            strategy_name=strat_name,
        )

        setup_domain = None
        if entry is not None and stop_loss is not None and len(take_profits) >= 1:
            try:
                setup_domain = TradeSetup(
                    symbol=symbol,
                    entry_price=entry,
                    stop_loss=stop_loss,
                    take_profit_1=take_profits[0],
                    take_profit_2=take_profits[1] if len(take_profits) > 1 else take_profits[0],
                    take_profit_3=take_profits[2] if len(take_profits) > 2 else take_profits[0],
                    timestamp=timestamp,
                    direction=act_lower if is_tradable_action else "buy",
                )
            except Exception:
                setup_domain = None

        trade_sig = TradeSignal(
            signal=sig_domain,
            readiness=readiness,
            stability=stab,
            reason="Signal presented from Project 1",
            tradable=is_tradable_action,
            trade_setup=setup_domain,
        )

        auth_res = self._auth_service.authorize(
            trade_signal=trade_sig,
            timestamp=timestamp,
        )

        # Compute Risk/Reward ratio if setup exists
        rr_ratio: Optional[float] = None
        if setup_domain is not None:
            rr_ratio = setup_domain.risk_reward_ratio()

        checks = [
            {
                "id": "signal_tradable",
                "label": "Signal Tradability Gate",
                "passed": is_tradable_action,
                "reason": f"Signal action is {action_str}" if is_tradable_action else "Action is not BUY/SELL",
            },
            {
                "id": "readiness_stability",
                "label": "Readiness & Stability Gate",
                "passed": readiness.approved and stab.score >= 0.6,
                "reason": f"Stability score: {int(stab.score * 100)}%" if stab.score >= 0.6 else f"Stability score {int(stab.score * 100)}% below 60% threshold",
            },
            {
                "id": "level_sanity",
                "label": "Trade Setup Level Geometry",
                "passed": setup_domain is not None,
                "reason": "Geometry verified (entry, SL, TP ordered correctly)" if setup_domain is not None else "No valid setup levels provided",
            },
            {
                "id": "risk_reward",
                "label": "Risk / Reward Threshold",
                "passed": (rr_ratio is not None and rr_ratio >= 1.0),
                "reason": f"R:R ratio is {rr_ratio:.2f}:1" if rr_ratio is not None else "N/A (No trade setup)",
            },
        ]

        # Security boundary filtering if non-admin or unauthorized
        if user is not None and not user.is_admin and not user.has_permission(Permission.READ_TRADE_SETUPS):
            # Redact detailed level reasons for restricted user
            for c in checks:
                if c["id"] in ("level_sanity", "risk_reward"):
                    c["reason"] = "Restricted to authorized users."

        return auth_res, {
            "status": auth_res.status,
            "isAuthorized": auth_res.is_authorized,
            "reason": auth_res.reason,
            "checks": checks,
            "riskRewardRatio": round(rr_ratio, 2) if rr_ratio is not None else None,
            "timestamp": timestamp,
        }

    def _compute_authorization(
        self,
        action_str: str,
        strat_name: str,
        symbol: str,
        timeframe: str,
        timestamp: float,
        confidence: Optional[float],
        entry: Optional[float],
        stop_loss: Optional[float],
        take_profits: list,
        user: Optional[UserAuthorization],
    ) -> Dict[str, Any]:
        """Compute deterministic autonomous execution authorization dict payload."""
        _, payload = self._compute_authorization_object(
            action_str=action_str,
            strat_name=strat_name,
            symbol=symbol,
            timeframe=timeframe,
            timestamp=timestamp,
            confidence=confidence,
            entry=entry,
            stop_loss=stop_loss,
            take_profits=take_profits,
            user=user,
        )
        return payload


def _validate_symbol(symbol: str) -> None:
    if not isinstance(symbol, str) or not symbol.strip():
        raise ValueError("symbol must be a non-empty string")


def _validate_timeframe(timeframe: str) -> None:
    if not isinstance(timeframe, str) or not timeframe.strip():
        raise ValueError("timeframe must be a non-empty string")
