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
- Sole Decision Authority: Project 1 is the sole decision authority.
  Project 2 does not reconstruct trading decisions or recalculate risk/reward ratios.
"""

from typing import Any, Dict, Optional, Tuple

import time
from src.platform.domain.security import Permission
from src.platform.domain.user_authorization import UserAuthorization
from src.platform.integrations.project1 import Project1IntegrationPort
from src.platform.services.clock import SystemClock, default_clock
from src.platform.services.audit_control import PlatformAuditControlService
from src.platform.services.execution_gateway import ExecutionGatewayService
from src.platform.services.health_operations import SystemHealthService
from src.platform.services.order_intent import OrderIntentService
from src.platform.services.project1_gateway import Project1IntegrationGatewayService
from src.platform.services.provider_operations import ProviderOperations
from src.platform.services.market_overview import MarketOverviewService
from src.platform.services.security import SecretSanitizer, SecurityBoundaryService

LIVE_SIGNAL_MAX_AGE_SECONDS = 300.0  # 5 minutes currentness threshold for live signals


def _evaluate_signal_live_status(
    sig_dict: Dict[str, Any],
    requested_symbol: Optional[str] = None,
    clock: Optional[SystemClock] = None,
) -> Tuple[bool, str]:
    """Evaluate whether a signal record satisfies all Current Signal eligibility requirements."""
    if not sig_dict:
        return False, "No signal data available."

    clk = clock or default_clock
    now_ts = clk.get_current_timestamp()

    sig_symbol = str(sig_dict.get("symbol") or "").strip().upper()
    if not sig_symbol:
        return False, "Signal missing authoritative instrument identity (symbol)."

    if requested_symbol:
        req_sym = str(requested_symbol).strip().upper()
        if not req_sym:
            return False, "Requested market symbol is empty."
        if sig_symbol != req_sym:
            return False, f"Signal symbol '{sig_symbol}' does not match requested market symbol '{req_sym}'."

    sig_ts = float(sig_dict.get("timestamp") or 0.0)
    if sig_ts <= 0:
        return False, "Signal missing valid event timestamp."

    if sig_ts > now_ts + 5.0:
        return False, f"Signal timestamp {sig_ts} is in the future relative to system clock {now_ts}."

    meta = sig_dict.get("metadata") if isinstance(sig_dict.get("metadata"), dict) else {}
    prov = meta.get("provenance_type") or meta.get("source") or ""

    if prov in ("lab_artifact", "historical_snapshot", "backtest_record") or meta.get("is_historical"):
        return False, f"Signal is a historical artifact ({prov or 'historical'}, emitted at timestamp {sig_ts})."

    if prov != "live_signal":
        return False, f"Signal provenance '{prov}' is not an authorized live signal."

    if meta.get("is_live") is False:
        return False, "Signal metadata explicitly marks signal as non-live."
    if meta.get("is_live") is not True:
        return False, "Signal metadata does not authoritatively mark the publication as live."

    # Determine publication / production timestamp vs market/bar timestamp
    pub_ts: Optional[float] = None
    raw_pub_ts = (
        meta.get("produced_at")
        or meta.get("authorized_at_utc")
        or meta.get("publication_timestamp")
        or sig_dict.get("produced_at")
    )
    if raw_pub_ts is not None:
        if isinstance(raw_pub_ts, (int, float)) and not isinstance(raw_pub_ts, bool):
            pub_ts = float(raw_pub_ts)
        elif isinstance(raw_pub_ts, str) and raw_pub_ts.strip():
            try:
                from src.platform.domain.project1_contract import parse_iso8601_to_utc_epoch
                pub_ts = parse_iso8601_to_utc_epoch(raw_pub_ts, max_future_skew_seconds=5.0, current_time_fn=clk.get_current_timestamp)
            except Exception:
                pub_ts = None

    # Check explicit expiration / validity bounds if provided in contract
    raw_valid_until = meta.get("valid_until") or meta.get("expires_at") or sig_dict.get("valid_until") or sig_dict.get("expires_at")
    if raw_valid_until is not None:
        valid_until_ts: Optional[float] = None
        if isinstance(raw_valid_until, (int, float)) and not isinstance(raw_valid_until, bool):
            valid_until_ts = float(raw_valid_until)
        elif isinstance(raw_valid_until, str) and raw_valid_until.strip():
            try:
                from src.platform.domain.project1_contract import parse_iso8601_to_utc_epoch
                valid_until_ts = parse_iso8601_to_utc_epoch(raw_valid_until, max_future_skew_seconds=86400.0, current_time_fn=clk.get_current_timestamp)
            except Exception:
                return False, "Signal valid_until/expires_at timestamp is malformed."
        if valid_until_ts is not None and now_ts > valid_until_ts:
            return False, f"Signal publication has passed authoritative valid_until threshold ({valid_until_ts})."

    if pub_ts is not None and pub_ts > now_ts + 5.0:
        return False, f"Signal publication timestamp {pub_ts} is in the future relative to system clock {now_ts}."

    return True, "Verified current live signal."


class Project1SignalPresenter:
    """Application service presenting Project 1 outputs to Project 2 application/UI layers."""

    def __init__(
        self,
        port: Project1IntegrationPort,
        security_service: Optional[SecurityBoundaryService] = None,
        backtest_service: Optional[Any] = None,
        audit_control_service: Optional[PlatformAuditControlService] = None,
        order_intent_service: Optional[OrderIntentService] = None,
        health_service: Optional[SystemHealthService] = None,
        gateway_service: Optional[Project1IntegrationGatewayService] = None,
        provider_operations: Optional[ProviderOperations] = None,
        market_overview_service: Optional[MarketOverviewService] = None,
    ) -> None:
        if port is None or not isinstance(port, Project1IntegrationPort):
            raise ValueError("port must be a valid Project1IntegrationPort")
        if security_service is not None and not isinstance(
            security_service, SecurityBoundaryService
        ):
            raise ValueError("security_service must be a SecurityBoundaryService instance")

        self._clock = default_clock
        self._port = port
        self._security_service = security_service or SecurityBoundaryService()
        self._backtest_service = backtest_service
        self._audit_control_service = audit_control_service or PlatformAuditControlService(security_boundary=self._security_service)
        self._health_service = health_service or SystemHealthService()
        self._order_intent_service = order_intent_service or OrderIntentService(
            security_boundary=self._security_service,
            audit_control=self._audit_control_service,
        )
        self._gateway_service = gateway_service or Project1IntegrationGatewayService(
            security_boundary=self._security_service,
            audit_control=self._audit_control_service,
        )
        self._execution_gateway_service = ExecutionGatewayService(
            order_intent_service=self._order_intent_service,
            security_boundary=self._security_service,
            audit_control=self._audit_control_service,
        )
        self._provider_ops = provider_operations
        self._overview_service = market_overview_service

    def _get_market_state(
        self,
        symbol: str,
        timeframe: str,
        candles_provider_id: str = "biquote",
        quote_provider_id: str = "biquote",
    ) -> Dict[str, Any]:
        """Fetch real normalized market data state via ProviderOperations / MarketOverviewService."""
        if self._overview_service is not None:
            try:
                ov = self._overview_service.get_overview(
                    symbol=symbol,
                    timeframe=timeframe,
                    candles_provider_id=candles_provider_id,
                    quote_provider_id=quote_provider_id,
                )
                candles_dicts = [c.to_dict() for c in ov.candles]
                quote_dict = ov.quote.to_dict() if ov.quote else None
                if quote_dict and quote_dict.get("symbol"):
                    q_sym = str(quote_dict["symbol"]).strip().upper()
                    if q_sym != symbol.strip().upper():
                        quote_dict = None
                q_avail = quote_dict.get("availability") if quote_dict else None
                status = "connected"
                if q_avail and isinstance(q_avail, dict) and q_avail.get("status") in ("stale", "delayed", "unavailable"):
                    status = q_avail["status"]
                elif not candles_dicts and not quote_dict:
                    status = "empty"

                return {
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "provider": {
                        "id": candles_provider_id,
                        "name": "BiQuoteProvider",
                        "provider": "biquote",
                        "status": status,
                        "supportedTimeframes": ["1m", "5m", "15m", "30m", "1h", "4h", "1d"],
                        "lastUpdated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    },
                    "quote": quote_dict,
                    "change": quote_dict.get("change_percent") if quote_dict else None,
                    "volume": quote_dict.get("volume24h") if quote_dict else (candles_dicts[-1].get("volume") if candles_dicts and "volume" in candles_dicts[-1] else None),
                    "candles": candles_dicts,
                    "status": status,
                    "message": f"Market data active from {candles_provider_id}.",
                    "lastFetchedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                }
            except Exception as exc:
                return {
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "provider": {
                        "id": candles_provider_id,
                        "name": "BiQuoteProvider",
                        "provider": "biquote",
                        "status": "error",
                        "supportedTimeframes": ["1m", "5m", "15m", "30m", "1h", "4h", "1d"],
                        "errorMessage": SecretSanitizer.sanitize_string(str(exc)),
                    },
                    "quote": None,
                    "change": None,
                    "volume": None,
                    "candles": [],
                    "status": "error",
                    "message": f"Market data provider error: {SecretSanitizer.sanitize_string(str(exc))}",
                    "lastFetchedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                }

        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "provider": None,
            "quote": None,
            "change": None,
            "volume": None,
            "candles": [],
            "status": "disconnected",
            "message": "Market data feed relies on provider selection.",
            "lastFetchedAt": None,
        }

    def _get_providers_status(self, mkt_state: Dict[str, Any]) -> Dict[str, Any]:
        """Format truthful provider connectivity status for HostSnapshot."""
        mkt_status = mkt_state.get("status", "unconnected") if isinstance(mkt_state, dict) else "unconnected"
        mkt_prov = mkt_state.get("provider") if isinstance(mkt_state, dict) else None
        prov_id = mkt_prov.get("id", "biquote") if isinstance(mkt_prov, dict) else "biquote"
        is_connected = (mkt_status == "connected")

        return {
            "marketData": "connected" if is_connected else mkt_status,
            "quote": "connected" if is_connected else mkt_status,
            "message": f"Market data provider '{prov_id}' session active." if is_connected else "Provider slots are ready. No live provider session is attached.",
        }

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

        user_id = user.user_id if user else None
        try:
            desc = self._port.describe(user_id=user_id)
        except TypeError:
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

        try:
            presented_signal = self._port.fetch_latest_signal(
                symbol=symbol, timeframe=timeframe, strategy_name=strategy_name, user_id=user_id
            )
        except TypeError:
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

        # Evaluate signal live provenance and currentness against system clock
        is_live, live_reason = _evaluate_signal_live_status(
            sig_dict, requested_symbol=symbol, clock=self._clock
        )
        sig_dict["is_live"] = is_live
        sig_dict["live_reason"] = live_reason

        # Sanitize metadata for all roles and filter protected payloads for non-admins
        raw_meta = sig_dict.get("metadata", {})
        if user is not None:
            sig_dict["metadata"] = self._security_service.filter_protected_payload(user, raw_meta)
        else:
            sig_dict["metadata"] = SecretSanitizer.sanitize_data(raw_meta)

        sig_type_lower = presented_signal.signal_type.lower()
        if not is_live or sig_type_lower == "no-signal":
            return {
                "port": desc,
                "connected": True,
                "status": "no-signal",
                "symbol": symbol,
                "timeframe": timeframe,
                "signal": None,
                "message": f"No active current Project 1 signal for {symbol} ({timeframe}). {live_reason}",
            }

        if sig_type_lower == "no-trade":
            return {
                "port": desc,
                "connected": True,
                "status": "no-trade",
                "symbol": symbol,
                "timeframe": timeframe,
                "signal": sig_dict,
                "message": f"Project 1 evaluated {symbol} ({timeframe}) and emitted an authoritative NO TRADE decision.",
            }

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
            ok_att, _, attempts = self._execution_gateway_service.get_execution_attempts(
                user=user,
                order_intent_id=intent.order_intent_id,
            )
            intent_dict["execution_attempts"] = attempts if ok_att else []

            ok_rec, _, rec_record = self._execution_gateway_service.get_reconciliation_record(
                user=user,
                order_intent_id=intent.order_intent_id,
            )
            intent_dict["reconciliation"] = rec_record if ok_rec else None

            if user is not None and not user.is_admin:
                intent_dict = self._security_service.filter_protected_payload(user, intent_dict)
            else:
                intent_dict = SecretSanitizer.sanitize_data(intent_dict)
            payloads.append(intent_dict)
        return payloads

    def request_execution(
        self,
        user: Optional[UserAuthorization],
        order_intent_id: str,
        execution_command_id: Optional[str] = None,
        timestamp: Optional[float] = None,
    ):
        """Submit an execution request for a staged OrderIntent through the execution gateway boundary."""
        return self._execution_gateway_service.request_execution(
            user=user,
            order_intent_id=order_intent_id,
            execution_command_id=execution_command_id,
            timestamp=timestamp,
        )

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
                "market": self._get_market_state(symbol, timeframe) if pres["status"] != "unauthorized" else {
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "provider": None,
                    "quote": None,
                    "change": None,
                    "volume": None,
                    "candles": [],
                    "status": "unavailable",
                    "message": "Market data is restricted or unavailable.",
                    "lastFetchedAt": None,
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
                    "authority": "PROJECT1",
                    "status": "UNAUTHORIZED",
                    "isAuthorized": None,
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
                "executionGateway": self._execution_gateway_service.get_boundary_status(user=user),
                "project1Gateway": self._gateway_service.get_gateway_monitoring_summary(user=user),
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
                "market": self._get_market_state(symbol, timeframe),
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
                    "authority": "PROJECT1",
                    "status": "DISCONNECTED",
                    "isAuthorized": None,
                    "reason": "Project 1 is disconnected. Connect Project 1 to receive authoritative trading signals.",
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
                "providers": self._get_providers_status(self._get_market_state(symbol, timeframe)),
                "activity": [],
                "orderIntents": self.get_order_intents_payload(user=user),
                "project1Gateway": self._gateway_service.get_gateway_monitoring_summary(user=user),
            }

        # Connected port handling
        mkt_state = self._get_market_state(symbol, timeframe)
        prov_status = self._get_providers_status(mkt_state)

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
                    "adapterName": desc.get("name", "Project1GatewayAdapter"),
                    "message": f"Project 1 connected via {desc.get('name', 'adapter')}.",
                },
                "market": mkt_state,
                "strategy": {
                    "name": strategy_name,
                    "stability": None,
                    "status": "available" if strategy_name else "unavailable",
                    "message": "Connected to Project 1 engine.",
                },
                "signal": {
                    "signalId": None,
                    "publicationId": None,
                    "symbol": symbol,
                    "action": "NO SIGNAL",
                    "timestamp": None,
                    "status": "no-signal",
                    "message": pres["message"],
                },
                "authorization": {
                    "authority": "PROJECT1",
                    "status": "NO_SIGNAL",
                    "isAuthorized": None,
                    "reason": f"No active signal emitted by Project 1 for {symbol} ({timeframe}).",
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
                    "message": "Risk levels stay empty until Project 1 emits a trade setup.",
                },
                "monitoring": {
                    "freshness": None,
                    "health": None,
                    "status": "unavailable",
                    "message": "Monitoring has no live observations yet.",
                },
                "providers": prov_status,
                "activity": [],
                "orderIntents": self.get_order_intents_payload(user=user),
                "project1Gateway": self._gateway_service.get_gateway_monitoring_summary(user=user),
            }

        sig_type_raw = str(signal_dict.get("signal_type") or "").strip().lower()
        is_no_trade = (sig_type_raw in ("no-trade", "no_trade"))
        action_str = "NO TRADE" if is_no_trade else str(signal_dict["signal_type"]).upper()
        sig_status_str = "no-trade" if is_no_trade else "active"
        strat_name = signal_dict.get("strategy_name") or "Project 1 Strategy"
        conf = signal_dict.get("confidence")
        entry = signal_dict.get("entry_price")
        sl = signal_dict.get("stop_loss")
        tps = list(signal_dict.get("take_profits") or [])
        sig_ts = float(signal_dict.get("timestamp") or 0.0)

        is_live, live_reason = _evaluate_signal_live_status(signal_dict)
        signal_dict["is_live"] = is_live
        signal_dict["live_reason"] = live_reason

        # Mask strategy details for normal users if strategy info is protected
        strat_msg = f"Strategy '{strat_name}' owned and evaluated by Project 1."
        if user is not None and not user.is_admin and not user.has_permission(Permission.READ_STRATEGY_PARAMETERS):
            strat_msg = "Strategy evaluated by Project 1."

        # Extract authoritative P1 risk_reward_ratio (if provided by P1; never calculated by P2)
        raw_meta = signal_dict.get("metadata") or {}
        p1_publication_id = signal_dict.get("publication_id") or raw_meta.get("publication_id")
        p1_rr = (
            signal_dict.get("risk_reward_ratio")
            if signal_dict.get("risk_reward_ratio") is not None
            else raw_meta.get("risk_reward_ratio")
        )
        if p1_rr is not None:
            try:
                p1_rr = float(p1_rr)
            except (ValueError, TypeError):
                p1_rr = None

        # Extract authoritative P1 operational_stability_score (if provided by P1; never derived from confidence)
        p1_stability = (
            signal_dict.get("operational_stability_score")
            if signal_dict.get("operational_stability_score") is not None
            else raw_meta.get("operational_stability_score")
        )
        if p1_stability is not None:
            try:
                p1_stability = float(p1_stability)
            except (ValueError, TypeError):
                p1_stability = None

        p1_auth_fingerprint = signal_dict.get("runtime_authorization_fingerprint") or raw_meta.get("runtime_authorization_fingerprint")
        p1_decision_fingerprint = signal_dict.get("canonical_live_decision_fingerprint") or raw_meta.get("canonical_live_decision_fingerprint")
        p1_decision_id = signal_dict.get("decision_id") or raw_meta.get("decision_id")
        p1_candidate_id = signal_dict.get("candidate_id") or raw_meta.get("candidate_id")
        p1_research_id = signal_dict.get("research_evidence_id") or raw_meta.get("research_evidence_id")

        auth_payload = {
            "authority": "PROJECT1",
            "status": "PROJECT1_AUTHORITATIVE" if is_live else "SIGNAL_STALE",
            "isAuthorized": None,
            "reason": (
                "Project 1 evaluated market conditions and decided NO TRADE."
                if (is_live and is_no_trade)
                else (
                    "Authorization decision is owned by Project 1; Project 2 does not recompute it."
                    if is_live
                    else f"Signal for {symbol} is historical/stale: {live_reason}"
                )
            ),
            "checks": [],
            "riskRewardRatio": p1_rr if not is_no_trade else None,
            "timestamp": sig_ts,
            "runtime_authorization_fingerprint": p1_auth_fingerprint,
            "canonical_live_decision_fingerprint": p1_decision_fingerprint,
            "decision_id": p1_decision_id,
            "candidate_id": p1_candidate_id,
            "research_evidence_id": p1_research_id,
            "runtimeAuthorizationFingerprint": p1_auth_fingerprint,
            "canonicalLiveDecisionFingerprint": p1_decision_fingerprint,
            "decisionId": p1_decision_id,
            "candidateId": p1_candidate_id,
            "researchEvidenceId": p1_research_id,
        }

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

        # Retrieve operational audit summary and observability report for HostSnapshot
        _, _, audit_summary = self._audit_control_service.get_control_summary(user=user)
        _, _, audit_events = self._audit_control_service.query_events(user=user, filter_params=None)
        _, _, operational_failures = self._audit_control_service.query_failures(user=user, limit=50)
        persistence_rec = self._health_service.validate_persistence_integrity()
        mkt_state = self._get_market_state(symbol, timeframe)

        observability_rep = self._health_service.get_unified_observability_report(
            active_sessions_count=1 if user else 0,
            project1_gateway_connected=is_connected,
            execution_boundary_status=self._execution_gateway_service.get_boundary_status(user=user),
            market_data_status=mkt_state,
            recent_failures_count=len(operational_failures),
        )

        return {
            "generatedAt": signal_dict.get("timestamp"),
            "platform": {
                "name": "AI Trading Lab Platform",
                "role": "Host application for AI-Trading-Lab",
                "status": "ready",
            },
            "persistenceRecovery": persistence_rec.to_dict(),
            "operationalFailures": [f.to_dict() for f in operational_failures],
            "observability": observability_rep.to_dict(),
            "auditControl": {
                "status": "available" if audit_summary is not None else "unavailable",
                "summary": audit_summary.to_dict() if audit_summary else None,
                "events": [e.to_dict() for e in audit_events[:50]] if audit_events else [],
            },
            "project1": {
                "connected": True,
                "status": "connected",
                "port": desc.get("port", "Project1IntegrationPort"),
                "adapterName": desc.get("name", "Project1GatewayAdapter"),
                "message": f"Project 1 emitting signals via {desc.get('name', 'adapter')}.",
            },
            "market": self._get_market_state(symbol, timeframe),
            "strategy": {
                "name": strat_name,
                "stability": p1_stability,
                "status": "active",
                "message": strat_msg,
            },
            "signal": {
                "signalId": signal_dict.get("signal_id"),
                "publicationId": p1_publication_id,
                "symbol": signal_dict.get("symbol") or symbol,
                "action": action_str,
                "timestamp": str(signal_dict.get("timestamp")),
                "confidence": conf if not is_no_trade else None,
                "strategyName": strat_name,
                "timeframe": signal_dict.get("timeframe") or timeframe,
                "status": sig_status_str,
                "message": (
                    f"Project 1 evaluated {symbol} ({timeframe}) and emitted a NO TRADE decision."
                    if is_no_trade
                    else f"Validated {action_str} signal emitted by Project 1."
                ),
                "metadata": signal_dict.get("metadata", {}),
            },
            "authorization": auth_payload,
            "performance": perf_payload,
            "risk": {
                "entry": entry if (is_live and not is_no_trade) else None,
                "stopLoss": sl if (is_live and not is_no_trade) else None,
                "takeProfits": tps if (is_live and not is_no_trade) else [],
                "status": ("available" if entry is not None else "unavailable") if (is_live and not is_no_trade) else "unavailable",
                "message": (
                    "No trade setup provided for NO TRADE decision."
                    if is_no_trade
                    else (
                        ("Real trade setup levels provided by Project 1." if entry is not None else "Trade setup omitted or restricted.")
                        if is_live
                        else "Trade setup levels held because signal is historical/stale."
                    )
                ),
            },
            "monitoring": {
                "freshness": "fresh" if is_live else "stale",
                "health": "healthy" if is_live else "stale",
                "status": "no-trade" if (is_live and is_no_trade) else ("available" if is_live else "stale"),
                "message": (
                    f"Project 1 signal for {symbol} ({timeframe}) is active and fresh (NO TRADE)."
                    if (is_live and is_no_trade)
                    else (
                        "Project 1 signal active and fresh."
                        if is_live
                        else f"Project 1 signal for {symbol} is historical/stale. Live signal data is unavailable."
                    )
                ),
            },
            "providers": prov_status,
            "activity": [
                {
                    "timestamp": str(signal_dict.get("timestamp")),
                    "event": "Signal Received",
                    "details": f"{action_str} signal for {symbol} ({strat_name})",
                }
            ],
            "orderIntents": self.get_order_intents_payload(user=user),
            "executionGateway": self._execution_gateway_service.get_boundary_status(user=user),
            "executionMonitoring": self._execution_gateway_service.get_execution_monitoring_summary(user=user),
            "project1Gateway": self._gateway_service.get_gateway_monitoring_summary(user=user),
        }


def _validate_symbol(symbol: str) -> None:
    if not isinstance(symbol, str) or not symbol.strip():
        raise ValueError("symbol must be a non-empty string")


def _validate_timeframe(timeframe: str) -> None:
    if not isinstance(timeframe, str) or not timeframe.strip():
        raise ValueError("timeframe must be a non-empty string")
