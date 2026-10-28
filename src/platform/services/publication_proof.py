"""Local publication-to-snapshot proof service.

Drives a genuine Contract v1.0 publication against the real P2 HTTP ingest
endpoint, then retrieves the record through the real snapshot/read path.

Security rules:
- Service credential is read from the environment (PROJECT2_API_KEY) and is
  never logged, printed, committed, or persisted.
- Market values used here are EXPLICITLY LABELED connectivity-verification
  fixtures. The tool must only be run against a local/loopback server instance
  with an isolated persistence directory. It never fabricates candles and
  never invents strategy results for production data stores.
"""

from datetime import datetime, timezone
import json
import math
import os
import time
import urllib.request
from typing import Any, Dict, Optional

INGEST_PATH = "/api/v1/integration/project1/ingest"
SNAPSHOT_PATH = "/api/v1/snapshot"


ACCEPTED_LIVE_PROVENANCE_TYPES = ("live_signal", "direct_strategy_signal")


def build_p1_contract_v1_payload(
    *,
    symbol: str = "XAUUSD",
    timeframe: str = "1H",
    decision: str = "buy",
    entry_price: float = 2700.0,
    stop_loss: float = 2680.0,
    take_profit: Optional[float] = 2720.0,
    strategy_name: str = "local_connectivity_proof",
    provenance_type: str = "live_signal",
    reference_now: Optional[float] = None,
) -> Dict[str, Any]:
    """Build a P1 Contract v1.0 payload in the canonical nested layout.

    Mirrors the shapes that Project 1 publishers serialize via
    to_contract_v1_payload(): nested signal/instrument/trade_setup/provenance
    sections with a timezone-aware ISO-8601 primary event timestamp and an
    authoritative publication timestamp (produced_at).
    """
    clean_symbol = str(symbol).strip().upper()
    clean_tf = str(timeframe).strip()
    clean_decision = str(decision).strip().lower()
    if clean_decision not in ("buy", "sell", "no-trade", "no-signal", "hold"):
        raise ValueError(f"Unsupported proof decision '{decision}'.")
    clean_provenance = str(provenance_type).strip()
    if clean_provenance not in ACCEPTED_LIVE_PROVENANCE_TYPES:
        raise ValueError(
            f"Unsupported proof provenance_type '{provenance_type}'. "
            f"Accepted live-signal provenance types: {ACCEPTED_LIVE_PROVENANCE_TYPES}."
        )

    now_ts = reference_now if reference_now is not None else time.time()
    now_dt = datetime.fromtimestamp(now_ts, tz=timezone.utc)
    # Event time is the market/candle observation moment; publication time is
    # separate and authoritative. Both must be explicit and UTC-aware.
    candle_ts = now_dt
    publication_ts = now_dt

    identity = f"proof_{now_dt.strftime('%Y%m%d%H%M%S')}_{math.floor(now_ts * 1000) % 10000}"
    payload: Dict[str, Any] = {
        "contract_version": "1.0",
        "event_id": identity,
        "event_type": "TRADING_SIGNAL",
        "timestamp": candle_ts.isoformat(),
        "instrument": {"symbol": clean_symbol, "interval": clean_tf},
        "signal": {
            "publication_id": identity,
            "signal_id": identity,
            "decision_id": identity,
            "decision": clean_decision,
            "strategy": strategy_name,
        },
        "trade_setup": {
            "entry_price": entry_price if clean_decision in ("buy", "sell") else None,
            "stop_loss": stop_loss if clean_decision in ("buy", "sell") else None,
            "tp1": take_profit if clean_decision in ("buy", "sell") else None,
        },
        "provenance": {
            "source": "local_publication_proof",
            "provenance_type": clean_provenance,
            "is_live": True,
            "produced_at": publication_ts.isoformat(),
        },
    }
    # publication/signal/event identity share the same synthetic proof lineage id
    return payload


def _request_json(req: urllib.request.Request, timeout_seconds: float = 10.0) -> Dict[str, Any]:
    with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
        body = resp.read().decode("utf-8")
        if resp.status < 200 or resp.status >= 300:
            raise RuntimeError(f"HTTP {resp.status} response")
        data = json.loads(body)
        if not isinstance(data, dict):
            raise RuntimeError("Response JSON is not an object.")
        return data


def run_publication_proof(
    base_url: str,
    service_key: Optional[str],
    *,
    symbol: str = "XAUUSD",
    timeframe: str = "1H",
    decision: str = "buy",
    provenance_type: str = "live_signal",
    timeout_seconds: float = 10.0,
    transport_post=None,
    transport_get=None,
) -> Dict[str, Any]:
    """Execute publication -> authenticated ingest -> snapshot retrieval proof.

    Returns a result dict: {success, evidence_level, missing records details,
    publication_id, snapshot_payload} with the service key never included.
    """
    if not service_key or not str(service_key).strip():
        return {
            "success": False,
            "evidence_level": "LEVEL_2_LOCAL_HTTP",
            "reason": "Missing ephemeral service credential (PROJECT2_API_KEY / PROJECT1_SERVICE_KEY env).",
        }

    clean_base = str(base_url).strip().rstrip("/")
    key_clean = str(service_key).strip()

    payload = build_p1_contract_v1_payload(
        symbol=symbol,
        timeframe=timeframe,
        decision=decision,
        provenance_type=provenance_type,
    )
    event_id = payload["event_id"]

    def post(req: urllib.request.Request) -> Dict[str, Any]:
        return _request_json(req, timeout_seconds)

    def get(req: urllib.request.Request) -> Dict[str, Any]:
        return _request_json(req, timeout_seconds)

    post_fn = transport_post or post
    get_fn = transport_get or get

    ack = None
    try:
        ingest_req = urllib.request.Request(
            f"{clean_base}{INGEST_PATH}",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {key_clean}",
                "X-API-Key": key_clean,
            },
            method="POST",
        )
        ack = post_fn(ingest_req)
    except Exception as exc:
        return {
            "success": False,
            "evidence_level": "LEVEL_2_LOCAL_HTTP",
            "reason": f"HTTP ingest failed: {type(exc).__name__}: {exc}",
            "event_id": event_id,
        }

    if not ack.get("success") or ack.get("status") not in ("INGESTED", "DUPLICATE_ACCEPTED"):
        return {
            "success": False,
            "evidence_level": "LEVEL_2_LOCAL_HTTP",
            "reason": f"Ingest not accepted: status={ack.get('status')} errors={ack.get('errors') or ack.get('message')}",
            "event_id": event_id,
        }
    if str(ack.get("event_id") or "") != event_id or str(ack.get("publication_id") or "") != event_id:
        return {
            "success": False,
            "evidence_level": "LEVEL_2_LOCAL_HTTP",
            "reason": "Acknowledgement identity mismatch with published event_id.",
            "event_id": event_id,
        }

    try:
        snapshot = get_fn(urllib.request.Request(
            f"{clean_base}{SNAPSHOT_PATH}?symbol={symbol}&timeframe={timeframe}",
            headers={"Content-Type": "application/json"},
            method="GET",
        ))
    except Exception as exc:
        return {
            "success": False,
            "evidence_level": "LEVEL_2_LOCAL_HTTP",
            "reason": f"Snapshot retrieval failed: {type(exc).__name__}: {exc}",
            "event_id": event_id,
        }

    sig_block = snapshot.get("signal") if isinstance(snapshot.get("signal"), dict) else {}
    retrieved_id = sig_block.get("signalId") or sig_block.get("signal_id")
    retrieved_pub_id = sig_block.get("publicationId") or sig_block.get("publication_id")
    retrieved_action = sig_block.get("action")
    is_visible = (
        sig_block.get("status") in ("active", "no-trade")
        and retrieved_id == payload["signal"]["signal_id"]
        and retrieved_pub_id == event_id
    )

    return {
        "success": is_visible,
        "evidence_level": "LEVEL_2_LOCAL_HTTP",
        "reason": (
            "Published Contract v1.0 record accepted by authenticated ingest and retrieved through the real snapshot path."
            if is_visible
            else "Record was ingested, but the real snapshot path did not return it visibly."
        ),
        "event_id": event_id,
        "publication_id": event_id,
        "signal_id": payload["signal"]["signal_id"],
        "action": retrieved_action,
        "timeframe": sig_block.get("timeframe"),
        "symbol": sig_block.get("symbol") or symbol,
        "risk": {
            "entry": (snapshot.get("risk") or {}).get("entry"),
            "stopLoss": (snapshot.get("risk") or {}).get("stopLoss"),
            "takeProfits": (snapshot.get("risk") or {}).get("takeProfits"),
        },
        "security_viewer_id": (snapshot.get("security") or {}).get("userId"),
        "snapshot_signal": sig_block,
    }


def main(argv=None) -> int:
    import argparse
    import secrets

    parser = argparse.ArgumentParser(
        description="Publish a Contract v1.0 payload to the local P2 ingest endpoint and verify real snapshot retrieval.",
    )
    parser.add_argument("--base-url", default=os.getenv("PROJECT2_PUBLISH_URL", "").rsplit("/api/", 1)[0])
    parser.add_argument("--symbol", default="XAUUSD")
    parser.add_argument("--timeframe", default="1H")
    parser.add_argument("--decision", default="buy")
    parser.add_argument("--provenance-type", default="live_signal")
    args = parser.parse_args(argv)

    service_key = os.getenv("PROJECT2_API_KEY") or os.getenv("PROJECT1_SERVICE_KEY") or ""

    if not args.base_url:
        print("[FAIL] Missing base URL: pass --base-url or set PROJECT2_PUBLISH_URL.", flush=True)
        return 2

    result = run_publication_proof(
        base_url=args.base_url,
        service_key=service_key,
        symbol=args.symbol,
        timeframe=args.timeframe,
        decision=args.decision,
        provenance_type=args.provenance_type,
    )
    out = {k: v for k, v in result.items() if k != "snapshot_signal"}
    print(json.dumps(out, indent=2, default=str))
    if result.get("success"):
        print(
            "[OK] Level 2 (local HTTP) proof observed: "
            f"event_id={result['event_id']} action={result.get('action')} "
            f"timeframe={result.get('timeframe')} risk={result.get('risk')}",
            flush=True,
        )
        return 0
    print(f"[FAIL] {result.get('reason')}", flush=True)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
