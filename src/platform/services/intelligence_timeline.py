"""Services for Unified Intelligence Timeline & Reusable Explainability Boundary.

Unifies existing real events/data (Market, Project 1 Signals, Notifications, Health, Workspace)
into a chronological activity timeline and provides explainability payloads for permitted items.

Enforces strict user isolation, SecurityBoundaryService authorization, and SecretSanitizer
payload filtering. Does NOT calculate new strategy decisions, indicator logic, or predictions.
"""

import time
from typing import Any, Dict, List, Optional, Set, Tuple

from src.platform.domain.notification import Notification, NotificationEvent
from src.platform.domain.security import Permission
from src.platform.domain.timeline import (
    ExplainabilityPayload,
    TimelineCategory,
    TimelineItem,
    TimelineSeverity,
)
from src.platform.domain.user_authorization import UserAuthorization
from src.platform.services.security import SecretSanitizer, SecurityBoundaryService


class IntelligenceTimelineService:
    """Service to construct and query a unified, chronological platform intelligence timeline."""

    def __init__(self, security_boundary: Optional[SecurityBoundaryService] = None) -> None:
        self.security_boundary = security_boundary or SecurityBoundaryService()

    def build_timeline(
        self,
        user: Optional[UserAuthorization],
        snapshot: Dict[str, Any],
        notifications: Optional[List[Dict[str, Any]]] = None,
        workspace_events: Optional[List[Dict[str, Any]]] = None,
        category: Optional[TimelineCategory] = None,
        search_query: Optional[str] = None,
    ) -> List[TimelineItem]:
        """Construct a real chronological timeline from existing platform snapshots and events."""
        items: List[TimelineItem] = []
        user_id = user.user_id if user else "guest"

        # 1. Project 1 Signal Events (Requires READ_SIGNALS, active live signals only)
        can_read_signals, _ = self.security_boundary.authorize(
            user=user, resource="signals", action="read", required_permission=Permission.READ_SIGNALS
        )
        if can_read_signals and isinstance(snapshot, dict):
            sig = snapshot.get("signal")
            p1 = snapshot.get("project1")
            if isinstance(sig, dict) and isinstance(p1, dict) and p1.get("connected"):
                sig_id = sig.get("signalId")
                sig_status = sig.get("status")
                action = (sig.get("action") or "").upper()
                if sig_id and sig_status == "active" and action not in ("NO SIGNAL", "UNKNOWN", "STALE SIGNAL"):
                    ts_str = sig.get("timestamp")
                    ts_val = time.time()
                    if ts_str:
                        try:
                            # Parse RFC2822 / ISO string or float if available
                            ts_val = time.mktime(time.strptime(ts_str, "%a, %d %b %Y %H:%M:%S GMT"))
                        except (ValueError, TypeError):
                            pass

                    strat_name = sig.get("strategyName") or "Project 1 Engine"
                    symbol = snapshot.get("market", {}).get("symbol", "XAUUSD")
                    tf = sig.get("timeframe") or "1h"

                    # Filter protected payload details
                    raw_meta = sig.get("metadata") or {}
                    clean_meta = self.security_boundary.filter_protected_payload(user, raw_meta)

                    items.append(
                        TimelineItem(
                            item_id=f"timeline-sig-{sig_id}",
                            timestamp=ts_val,
                            category=TimelineCategory.SIGNAL,
                            severity=TimelineSeverity.SUCCESS if action in ("BUY", "SELL") else TimelineSeverity.INFO,
                            title=f"{action} Signal for {symbol}",
                            summary=f"Emitted via Project 1 port ({p1.get('adapterName', 'Port')}) for {symbol} ({tf}). Strategy: {strat_name}.",
                            source="Project1IntegrationPort",
                            route="/signals",
                            target_user_id=None,
                            explainable=True,
                            payload={
                                "signal_id": sig_id,
                                "symbol": symbol,
                                "action": action,
                                "timeframe": tf,
                                "strategy_name": strat_name,
                                "confidence": sig.get("confidence"),
                                "status": sig_status,
                                "metadata": clean_meta,
                            },
                        )
                    )

        # 2. Market Events & Context
        if isinstance(snapshot, dict):
            mkt = snapshot.get("market")
            if isinstance(mkt, dict):
                symbol = mkt.get("symbol", "XAUUSD")
                mkt_status = mkt.get("status", "disconnected")
                mkt_msg = mkt.get("message", "Market data status update.")
                quote = mkt.get("quote") or {}
                bid = quote.get("bid") if isinstance(quote, dict) else None
                ask = quote.get("ask") if isinstance(quote, dict) else None

                last_fetched = mkt.get("lastFetchedAt")
                mkt_ts = time.time()
                if last_fetched:
                    try:
                        mkt_ts = time.mktime(time.strptime(last_fetched, "%a, %d %b %Y %H:%M:%S GMT"))
                    except (ValueError, TypeError):
                        pass

                items.append(
                    TimelineItem(
                        item_id=f"timeline-mkt-{symbol.lower()}",
                        timestamp=mkt_ts,
                        category=TimelineCategory.MARKET,
                        severity=TimelineSeverity.INFO if mkt_status == "connected" else TimelineSeverity.WARNING,
                        title=f"Market Feed Update: {symbol}",
                        summary=f"Market status is {mkt_status}. {mkt_msg}",
                        source="MarketDataService / ProviderRegistry",
                        route="/markets",
                        target_user_id=None,
                        explainable=True,
                        payload={
                            "symbol": symbol,
                            "timeframe": mkt.get("timeframe", "1h"),
                            "status": mkt_status,
                            "bid": bid,
                            "ask": ask,
                            "provider": mkt.get("provider"),
                        },
                    )
                )

        # 3. Notification Events (Enforcing User Isolation & Sanitization)
        if notifications and isinstance(notifications, list):
            for n in notifications:
                if not isinstance(n, dict):
                    continue
                n_uid = n.get("user_id") or n.get("target_user_id")
                # User isolation: include only if user_id matches or is target_user_id
                if n_uid and n_uid != user_id and not (user and user.is_admin):
                    continue

                cat_raw = n.get("category", "system")
                try:
                    cat_enum = TimelineCategory(cat_raw)
                except ValueError:
                    cat_enum = TimelineCategory.NOTIFICATION

                sev_raw = n.get("severity", "info")
                try:
                    sev_enum = TimelineSeverity(sev_raw)
                except ValueError:
                    sev_enum = TimelineSeverity.INFO

                n_id = n.get("notification_id") or n.get("event_id") or f"notif-{time.time()}"
                title = SecretSanitizer.sanitize_string(n.get("title", "Notification Event"))
                msg = SecretSanitizer.sanitize_string(n.get("message", "System notification received."))
                n_ts = n.get("timestamp", time.time())

                clean_meta = self.security_boundary.filter_protected_payload(user, n.get("metadata") or n.get("payload") or {})

                items.append(
                    TimelineItem(
                        item_id=f"timeline-notif-{n_id}",
                        timestamp=float(n_ts),
                        category=cat_enum,
                        severity=sev_enum,
                        title=title,
                        summary=msg,
                        source="NotificationService",
                        route="/notifications",
                        target_user_id=user_id,
                        explainable=False,
                        payload=clean_meta,
                    )
                )

        # 4. Health & Connection Events
        if isinstance(snapshot, dict):
            mon = snapshot.get("monitoring")
            prov = snapshot.get("providers")
            if isinstance(mon, dict):
                h_ts = time.time()
                items.append(
                    TimelineItem(
                        item_id="timeline-health-mon",
                        timestamp=h_ts,
                        category=TimelineCategory.HEALTH,
                        severity=TimelineSeverity.SUCCESS if mon.get("health") == "healthy" else TimelineSeverity.WARNING,
                        title="Connection & Data Health Inspection",
                        summary=mon.get("message", "Data freshness and observer pipeline evaluation."),
                        source="ProviderMonitoringService",
                        route="/health",
                        target_user_id=None,
                        explainable=True,
                        payload={
                            "freshness": mon.get("freshness"),
                            "health": mon.get("health"),
                            "providers_message": prov.get("message") if isinstance(prov, dict) else None,
                        },
                    )
                )

        # 5. Workspace / Watchlist Events
        if workspace_events and isinstance(workspace_events, list):
            for ws in workspace_events:
                if not isinstance(ws, dict):
                    continue
                ws_uid = ws.get("user_id")
                if ws_uid and ws_uid != user_id and not (user and user.is_admin):
                    continue

                ws_id = ws.get("event_id", f"ws-{time.time()}")
                items.append(
                    TimelineItem(
                        item_id=f"timeline-ws-{ws_id}",
                        timestamp=float(ws.get("timestamp", time.time())),
                        category=TimelineCategory.WORKSPACE,
                        severity=TimelineSeverity.INFO,
                        title=SecretSanitizer.sanitize_string(ws.get("title", "Workspace Activity")),
                        summary=SecretSanitizer.sanitize_string(ws.get("summary", "Watchlist updated.")),
                        source="WorkspaceService",
                        route="/watchlist",
                        target_user_id=user_id,
                        explainable=False,
                        payload=ws.get("payload", {}),
                    )
                )

        # Sort chronologically descending (newest first)
        items.sort(key=lambda x: x.timestamp, reverse=True)

        # Apply category filter if specified
        if category is not None:
            items = [item for item in items if item.category == category]

        # Apply search query filter if specified
        if search_query and search_query.strip():
            q = search_query.strip().lower()
            items = [
                item
                for item in items
                if q in item.title.lower() or q in item.summary.lower() or q in item.source.lower()
            ]

        return items


class ExplainabilityService:
    """Service to expose authorized, sanitized explainability context for platform items."""

    def __init__(self, security_boundary: Optional[SecurityBoundaryService] = None) -> None:
        self.security_boundary = security_boundary or SecurityBoundaryService()

    def generate_explainability(
        self,
        user: Optional[UserAuthorization],
        item: TimelineItem,
        snapshot: Dict[str, Any],
    ) -> ExplainabilityPayload:
        """Generate explainability context for permitted items, strictly redacting protected details.

        Explains existing outputs only. Does NOT compute new predictions or strategy rules.
        """
        if not item.explainable:
            raise ValueError(f"Timeline item '{item.item_id}' is not explainable")

        # Authorize access based on item category
        if item.category == TimelineCategory.SIGNAL:
            authorized, reason = self.security_boundary.authorize(
                user=user, resource="signals", action="read", required_permission=Permission.READ_SIGNALS
            )
            if not authorized:
                raise PermissionError(f"Explainability denied: {reason}")

        # Sanitize and filter metadata
        clean_payload = self.security_boundary.filter_protected_payload(user, item.payload)

        # Permitted market context from existing snapshot
        mkt_ctx = {}
        if isinstance(snapshot, dict) and "market" in snapshot:
            mkt = snapshot["market"]
            if isinstance(mkt, dict):
                mkt_ctx = {
                    "symbol": mkt.get("symbol"),
                    "timeframe": mkt.get("timeframe"),
                    "status": mkt.get("status"),
                    "provider": mkt.get("provider", {}).get("name") if isinstance(mkt.get("provider"), dict) else None,
                    "last_fetched_at": mkt.get("lastFetchedAt"),
                }

        # Permitted risk context from existing snapshot
        risk_ctx = {}
        if isinstance(snapshot, dict) and "risk" in snapshot:
            r = snapshot["risk"]
            if isinstance(r, dict):
                risk_ctx = {
                    "entry_level": r.get("entry"),
                    "stop_loss": r.get("stopLoss"),
                    "take_profits": r.get("takeProfits"),
                    "status": r.get("status"),
                    "rule": "1% equity risk evaluation",
                }

        # Notes describing explainability constraints
        notes = [
            f"Context assembled from legitimate platform boundary '{item.source}'.",
            "This explanation articulates existing system outputs and market conditions.",
            "Proprietary Project 1 strategy code, indicator math, and lab models are protected and unexposed.",
        ]

        if not (user and user.is_admin):
            notes.append("Standard user authorization active: lab parameters and internal model weights remain redacted.")

        return ExplainabilityPayload(
            item_id=item.item_id,
            item_type=item.category.value,
            received_at=item.timestamp,
            source=item.source,
            freshness_status="FRESH" if (time.time() - item.timestamp < 300) else "STALE",
            permitted_metadata=clean_payload,
            permitted_market_context=mkt_ctx,
            permitted_risk_context=risk_ctx,
            explainability_notes=notes,
        )
