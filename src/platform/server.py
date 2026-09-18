"""Production Application Server Entry Point for AI-Trading-Lab-Platform.

Provides production-grade HTTP serving using standard library ThreadingHTTPServer,
handling API endpoints, operational health/readiness probes, authentication gates,
user management lifecycle, CORS origin validation, production security headers, and SPA static asset routing.
"""

from http.server import HTTPServer, ThreadingHTTPServer, BaseHTTPRequestHandler
import json
import logging
import mimetypes
import os
import sys
from typing import Any, Dict, Optional, Tuple
import urllib.parse

from src.platform.config import PlatformConfig
from src.platform.adapters.user_repository import FileBackedUserRepository
from src.platform.adapters.workspace_repository import FileBackedWorkspaceRepository
from src.platform.adapters.project1_adapter import DisconnectedProject1Adapter
from src.platform.services.user_authorization import UserAuthorizationService
from src.platform.services.workspace import WorkspaceService
from src.platform.services.health_operations import SystemHealthService
from src.platform.services.security import SecurityBoundaryService, SecretSanitizer
from src.platform.services.project1_presenter import Project1SignalPresenter
from src.platform.services.project1_gateway import Project1IntegrationGatewayService
from src.platform.services.notification import NotificationService
from src.platform.services.notification_delivery import NotificationDeliveryService
from src.platform.providers.notification_delivery import RecordingNotificationDeliveryAdapter

logger = logging.getLogger("platform.server")


class PlatformRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler for API, health, authentication, user management, and SPA static assets."""

    config: PlatformConfig
    server_user_auth_service: UserAuthorizationService
    workspace_service: WorkspaceService
    health_service: SystemHealthService
    security_service: SecurityBoundaryService
    presenter: Project1SignalPresenter
    gateway_service: Project1IntegrationGatewayService
    notification_service: NotificationService
    notification_delivery_service: NotificationDeliveryService
    static_dir: str

    def log_message(self, format: str, *args: Any) -> None:
        """Sanitize and format server log output."""
        logger.info("%s - - [%s] %s", self.address_string(), self.log_date_time_string(), format % args)

    def _set_security_headers(self, origin: Optional[str] = None) -> None:
        """Apply production security headers and CORS policy."""
        headers = self.config.get_security_headers()
        for k, v in headers.items():
            self.send_header(k, v)

        if origin and self.config.is_origin_allowed(origin):
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Allow-Credentials", "true")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, PUT, DELETE")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Requested-With")

    def _send_json_response(
        self,
        status_code: int,
        data: Dict[str, Any],
        origin: Optional[str] = None,
        sanitize: bool = True,
    ) -> None:
        """Send JSON response with security headers and CORS support."""
        response_data = SecretSanitizer.sanitize_data(data) if sanitize else data
        body = json.dumps(response_data, indent=2).encode("utf-8")

        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._set_security_headers(origin=origin)
        self.end_headers()
        self.wfile.write(body)

    def _send_error_response(
        self,
        status_code: int,
        what: str,
        why: str,
        recommended_action: str,
        origin: Optional[str] = None,
    ) -> None:
        """Send standardized operational error response."""
        corr_id = self.health_service.generate_correlation_id()
        payload = {
            "error": True,
            "status_code": status_code,
            "correlation_id": corr_id,
            "what": what,
            "why": why,
            "recommended_action": recommended_action,
        }
        self._send_json_response(status_code, payload, origin=origin)

    def _extract_bearer_token(self) -> Optional[str]:
        """Extract Bearer token from Authorization header."""
        auth_hdr = self.headers.get("Authorization", "")
        if auth_hdr.startswith("Bearer "):
            return auth_hdr[7:].strip()
        return None

    def _authenticate_request_user(self) -> Tuple[bool, Optional[Any]]:
        """Validate bearer token from request headers and return (is_authenticated, user)."""
        token = self._extract_bearer_token()
        if not token:
            return False, None
        return self.server_user_auth_service.validate_session_token(token)

    def do_OPTIONS(self) -> None:
        """Handle CORS preflight OPTIONS requests."""
        origin = self.headers.get("Origin")
        self.send_response(204)
        self._set_security_headers(origin=origin)
        self.end_headers()

    def do_GET(self) -> None:
        """Handle HTTP GET requests."""
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        origin = self.headers.get("Origin")

        try:
            if path in ("/health", "/health/liveness", "/health/live"):
                is_live, msg = self.health_service.check_liveness()
                self._send_json_response(200, {"status": "alive", "liveness": is_live, "message": msg}, origin=origin)
                return

            if path in ("/health/readiness", "/health/ready"):
                is_ready, details = self.health_service.check_readiness()
                status_code = 200 if is_ready else 503
                self._send_json_response(status_code, {"status": "ready" if is_ready else "not_ready", "readiness": details}, origin=origin)
                return

            if path in ("/api/v1/diagnostics", "/diagnostics"):
                diag = self.health_service.get_operational_diagnostics()
                self._send_json_response(
                    200,
                    {
                        "timestamp": diag.timestamp,
                        "liveness": diag.liveness,
                        "readiness": diag.readiness,
                        "app_env": diag.app_env,
                        "active_sessions_count": diag.active_sessions_count,
                        "system_status": diag.system_status,
                        "summary": diag.diagnostics_summary,
                    },
                    origin=origin,
                )
                return

            if path == "/api/v1/users/audit":
                valid, actor = self._authenticate_request_user()
                if not valid or not actor:
                    self._send_error_response(401, "Unauthenticated", "Missing or invalid session token.", "Login to access audit logs.", origin=origin)
                    return
                if not actor.is_admin:
                    self._send_error_response(403, "Access Denied", "Admin privileges required.", "Contact platform administrator.", origin=origin)
                    return

                query_params = urllib.parse.parse_qs(parsed_url.query)
                target_uid = query_params.get("user_id", [None])[0]
                outcome = query_params.get("outcome", [None])[0]

                events = self.security_service.audit_logger.get_events(user_id=target_uid, outcome=outcome)
                self._send_json_response(
                    200,
                    {
                        "success": True,
                        "events": [e.to_dict() for e in events],
                    },
                    origin=origin,
                )
                return

            if path == "/api/v1/profile":
                valid, user = self._authenticate_request_user()
                if not valid or not user:
                    self._send_error_response(401, "Unauthenticated", "Missing or invalid session token.", "Login to view profile.", origin=origin)
                    return

                self._send_json_response(
                    200,
                    {
                        "success": True,
                        "profile": user.to_dict(),
                    },
                    origin=origin,
                )
                return

            if path == "/api/v1/workspace":
                valid, user = self._authenticate_request_user()
                if not valid or not user:
                    self._send_error_response(401, "Unauthenticated", "Missing or invalid session token.", "Login to view workspace.", origin=origin)
                    return

                ws = self.workspace_service.get_or_create_workspace(user, user.user_id)
                self._send_json_response(
                    200,
                    {
                        "success": True,
                        "workspace": ws.to_dict(),
                    },
                    origin=origin,
                )
                return

            if path == "/api/v1/auth/validate":
                valid, user = self._authenticate_request_user()
                if not valid or not user:
                    self._send_json_response(401, {"valid": False, "reason": "Invalid or expired session token"}, origin=origin)
                    return
                self._send_json_response(
                    200,
                    {
                        "valid": True,
                        "user": {
                            "user_id": user.user_id,
                            "role": user.role.value,
                            "permissions": [p.value for p in user.permissions],
                            "is_permanent_admin": user.is_permanent_admin,
                            "is_account_valid": user.is_account_valid(),
                            "activation_timestamp": user.activation_timestamp,
                            "expiration_timestamp": user.expiration_timestamp,
                        },
                    },
                    origin=origin,
                )
                return

            if path == "/api/v1/users":
                valid, actor = self._authenticate_request_user()
                if not valid or not actor:
                    self._send_error_response(401, "Unauthenticated", "Missing or invalid session token.", "Login to access account management.", origin=origin)
                    return
                if not actor.is_admin:
                    self._send_error_response(403, "Access Denied", "Admin privileges required.", "Contact platform administrator.", origin=origin)
                    return

                users = self.server_user_auth_service.list_user_accounts(actor)
                self._send_json_response(
                    200,
                    {
                        "success": True,
                        "users": [u.to_dict() for u in users],
                    },
                    origin=origin,
                )
                return

            if path in ("/api/v1/integration/project1/capabilities", "/api/v1/integration/project1/contract"):
                token = self._extract_bearer_token()
                user = None
                if token:
                    _, user = self.server_user_auth_service.validate_session_token(token)
                res = self.gateway_service.get_capabilities(user=user)
                self._send_json_response(200, res, origin=origin)
                return

            if path == "/api/v1/integration/project1/records":
                valid, user = self._authenticate_request_user()
                if not valid or not user:
                    self._send_error_response(401, "Unauthenticated", "Missing or invalid session token.", "Login to access integration records.", origin=origin)
                    return

                query_params = urllib.parse.parse_qs(parsed_url.query)
                symbol = query_params.get("symbol", [None])[0]
                lifecycle_state = query_params.get("lifecycle_state", [None])[0]
                limit_str = query_params.get("limit", ["100"])[0]
                try:
                    limit = int(limit_str)
                except ValueError:
                    limit = 100

                res = self.gateway_service.list_records(
                    user=user,
                    symbol=symbol,
                    lifecycle_state=lifecycle_state,
                    limit=limit,
                )
                self._send_json_response(200, res, origin=origin)
                return

            if path == "/api/v1/snapshot":
                token = self._extract_bearer_token()
                user = None
                if token:
                    _, user = self.server_user_auth_service.validate_session_token(token)
                snapshot = self.presenter.build_host_snapshot(user=user)
                self._send_json_response(200, snapshot, origin=origin)
                return

            if path == "/api/v1/notifications":
                valid, user = self._authenticate_request_user()
                if not valid or not user:
                    self._send_error_response(401, "Unauthenticated", "Missing or invalid session token.", "Login to view notifications.", origin=origin)
                    return

                query_params = urllib.parse.parse_qs(parsed_url.query)
                category = query_params.get("category", [None])[0]
                unread_only = query_params.get("unread_only", ["false"])[0].lower() == "true"
                include_archived = query_params.get("include_archived", ["false"])[0].lower() == "true"

                notifs = self.notification_service.get_notifications(
                    requester=user,
                    target_user_id=user.user_id,
                    category=category,
                    unread_only=unread_only,
                    include_archived=include_archived,
                )
                self._send_json_response(
                    200,
                    {
                        "success": True,
                        "notifications": [n.to_dict() for n in notifs],
                        "count": len(notifs),
                    },
                    origin=origin,
                )
                return

            if path == "/api/v1/notifications/unread-count":
                valid, user = self._authenticate_request_user()
                if not valid or not user:
                    self._send_error_response(401, "Unauthenticated", "Missing or invalid session token.", "Login to view unread count.", origin=origin)
                    return

                count = self.notification_service.get_unread_count(
                    requester=user,
                    target_user_id=user.user_id,
                )
                self._send_json_response(
                    200,
                    {
                        "success": True,
                        "unread_count": count,
                    },
                    origin=origin,
                )
                return

            if path == "/api/v1/notifications/preferences":
                valid, user = self._authenticate_request_user()
                if not valid or not user:
                    self._send_error_response(401, "Unauthenticated", "Missing or invalid session token.", "Login to view notification preferences.", origin=origin)
                    return

                ws = self.workspace_service.get_or_create_workspace(user, user.user_id)
                self._send_json_response(
                    200,
                    {
                        "success": True,
                        "preferences": ws.notification_preferences.to_dict(),
                    },
                    origin=origin,
                )
                return

            if path == "/api/v1/notifications/delivery-status":
                valid, user = self._authenticate_request_user()
                if not valid or not user:
                    self._send_error_response(401, "Unauthenticated", "Missing or invalid session token.", "Login to check delivery status.", origin=origin)
                    return

                has_tg = bool(user.telegram_chat_id and user.telegram_chat_id.strip())
                self._send_json_response(
                    200,
                    {
                        "success": True,
                        "channels": {
                            "in_app": {"status": "IN_APP_AVAILABLE", "configured": True},
                            "telegram": {
                                "status": "EXTERNAL_CONFIGURED" if has_tg else "EXTERNAL_NOT_CONFIGURED",
                                "configured": has_tg,
                                "chat_id": user.telegram_chat_id if has_tg else None,
                            },
                        },
                    },
                    origin=origin,
                )
                return

            if path == "/api/v1/notifications/admin/delivery-log":
                valid, actor = self._authenticate_request_user()
                if not valid or not actor:
                    self._send_error_response(401, "Unauthenticated", "Missing or invalid session token.", "Login as Admin.", origin=origin)
                    return
                if not actor.is_admin:
                    self._send_error_response(403, "Access Denied", "Admin privileges required.", "Contact platform administrator.", origin=origin)
                    return

                desc = self.notification_delivery_service.describe()
                self._send_json_response(
                    200,
                    {
                        "success": True,
                        "delivery_service": desc,
                    },
                    origin=origin,
                )
                return

            # Static asset or SPA routing
            self._serve_static_asset(path, origin=origin)

        except Exception as exc:
            logger.exception("Error handling GET request to %s: %s", path, str(exc))
            self._send_error_response(
                500,
                what="Internal Server Error",
                why="An unexpected operational error occurred while processing the request.",
                recommended_action="Please try again or contact system support with the correlation ID.",
                origin=origin,
            )

    def do_POST(self) -> None:
        """Handle HTTP POST requests."""
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        origin = self.headers.get("Origin")

        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body_bytes = self.rfile.read(content_length) if content_length > 0 else b""

            if path == "/api/v1/auth/login":
                try:
                    req_data = json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
                except Exception:
                    self._send_error_response(
                        400,
                        what="Invalid JSON Request",
                        why="The request payload was not valid JSON.",
                        recommended_action="Ensure request body is a valid JSON object with 'user_id' and 'password'.",
                        origin=origin,
                    )
                    return

                user_id = str(req_data.get("user_id", "")).strip()
                password = str(req_data.get("password", "")).strip()

                if not user_id or not password:
                    self._send_error_response(
                        400,
                        what="Missing Credentials",
                        why="Both 'user_id' and 'password' fields are required.",
                        recommended_action="Provide user_id and password in the login request.",
                        origin=origin,
                    )
                    return

                ok, user, msg = self.server_user_auth_service.authenticate_with_password(user_id, password)
                if not ok or not user:
                    self._send_json_response(401, {"success": False, "message": msg or "Invalid credentials"}, origin=origin)
                    return

                token = self.server_user_auth_service.create_session_token(user.user_id)
                self._send_json_response(
                    200,
                    {
                        "success": True,
                        "message": "Authentication successful",
                        "token": token,
                        "user": user.to_dict(),
                    },
                    origin=origin,
                    sanitize=False,  # Return session token to caller upon successful login
                )
                return

            if path == "/api/v1/auth/logout":
                token = self._extract_bearer_token()
                if token:
                    self.server_user_auth_service.revoke_session_token(token)
                self._send_json_response(200, {"success": True, "message": "Logged out successfully"}, origin=origin)
                return

            if path in (
                "/api/v1/users/create",
                "/api/v1/users/status",
                "/api/v1/users/renew",
                "/api/v1/users/role",
                "/api/v1/users/revoke-sessions",
            ):
                valid, actor = self._authenticate_request_user()
                if not valid or not actor:
                    self._send_error_response(401, "Unauthenticated", "Missing or invalid session token.", "Login as Admin.", origin=origin)
                    return
                if not actor.is_admin:
                    self._send_error_response(403, "Access Denied", "Admin privileges required.", "Contact administrator.", origin=origin)
                    return

                try:
                    req_data = json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
                except Exception:
                    self._send_error_response(400, "Invalid JSON Request", "Request body was not valid JSON.", "Provide valid JSON body.", origin=origin)
                    return

                if path == "/api/v1/users/create":
                    target_id = str(req_data.get("user_id", "")).strip()
                    password = str(req_data.get("password", "")).strip()
                    act_ts = float(req_data.get("activation_timestamp", time.time()))
                    exp_ts = float(req_data.get("expiration_timestamp", time.time() + (30 * 86400)))
                    role = req_data.get("role", "customer")
                    symbols = tuple(req_data.get("allowed_symbols", ["XAUUSD", "EURUSD"]))

                    if not target_id or not password:
                        self._send_error_response(400, "Missing Parameters", "Both 'user_id' and 'password' are required.", "Provide required user fields.", origin=origin)
                        return

                    try:
                        created = self.server_user_auth_service.create_customer_account(
                            actor_user=actor,
                            target_user_id=target_id,
                            plaintext_password=password,
                            activation_timestamp=act_ts,
                            expiration_timestamp=exp_ts,
                            allowed_symbols=symbols,
                            role=role,
                        )
                        self._send_json_response(200, {"success": True, "user": created.to_dict()}, origin=origin)
                        return
                    except Exception as err:
                        self._send_error_response(400, "Account Creation Failed", str(err), "Verify input parameters.", origin=origin)
                        return

                if path == "/api/v1/users/status":
                    target_id = str(req_data.get("user_id", "")).strip()
                    is_active = bool(req_data.get("is_active", True))
                    try:
                        updated = self.server_user_auth_service.set_account_active_status(actor, target_id, is_active)
                        self._send_json_response(200, {"success": True, "user": updated.to_dict()}, origin=origin)
                        return
                    except Exception as err:
                        self._send_error_response(400, "Status Update Failed", str(err), "Check target user ID.", origin=origin)
                        return

                if path == "/api/v1/users/renew":
                    target_id = str(req_data.get("user_id", "")).strip()
                    new_exp = float(req_data.get("expiration_timestamp", time.time() + (30 * 86400)))
                    try:
                        renewed = self.server_user_auth_service.renew_customer_account(actor, target_id, new_exp)
                        self._send_json_response(200, {"success": True, "user": renewed.to_dict()}, origin=origin)
                        return
                    except Exception as err:
                        self._send_error_response(400, "Account Renewal Failed", str(err), "Check target user ID and expiration timestamp.", origin=origin)
                        return

                if path == "/api/v1/users/role":
                    target_id = str(req_data.get("user_id", "")).strip()
                    new_role = req_data.get("role", "customer")
                    try:
                        updated = self.server_user_auth_service.update_user_role(actor, target_id, new_role)
                        self._send_json_response(200, {"success": True, "user": updated.to_dict()}, origin=origin)
                        return
                    except Exception as err:
                        self._send_error_response(400, "Role Update Failed", str(err), "Check role assignment permissions.", origin=origin)
                        return

                if path == "/api/v1/users/revoke-sessions":
                    target_id = str(req_data.get("user_id", "")).strip()
                    try:
                        count = self.server_user_auth_service.revoke_user_sessions(actor, target_id)
                        self._send_json_response(200, {"success": True, "revoked_count": count}, origin=origin)
                        return
                    except Exception as err:
                        self._send_error_response(400, "Session Revocation Failed", str(err), "Check target user ID.", origin=origin)
                        return

            if path == "/api/v1/integration/project1/ingest":
                valid, user = self._authenticate_request_user()
                if not valid or not user:
                    self._send_error_response(401, "Unauthenticated", "Missing or invalid session token.", "Login to ingest Project 1 signals.", origin=origin)
                    return

                try:
                    req_data = json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
                except Exception:
                    self._send_error_response(400, "Invalid JSON Request", "Request body was not valid JSON.", "Provide valid JSON payload.", origin=origin)
                    return

                res = self.gateway_service.ingest_signal_payload(user=user, payload=req_data)
                if res.get("success"):
                    self._send_json_response(200, res, origin=origin)
                else:
                    err_code = res.get("error_code", "INGESTION_FAILED")
                    status_code = 400
                    if err_code == "UNAUTHORIZED":
                        status_code = 403
                    elif err_code == "FORBIDDEN_USER_MISMATCH":
                        status_code = 403
                    elif err_code == "UNSUPPORTED_CONTRACT_VERSION":
                        status_code = 422
                    self._send_json_response(status_code, res, origin=origin)
                return

            if path == "/api/v1/integration/project1/lifecycle":
                valid, user = self._authenticate_request_user()
                if not valid or not user:
                    self._send_error_response(401, "Unauthenticated", "Missing or invalid session token.", "Login to update lifecycle.", origin=origin)
                    return

                try:
                    req_data = json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
                except Exception:
                    self._send_error_response(400, "Invalid JSON Request", "Request body was not valid JSON.", "Provide valid JSON payload.", origin=origin)
                    return

                res = self.gateway_service.update_lifecycle(user=user, payload=req_data)
                status_code = 200 if res.get("success") else 400
                if res.get("error_code") == "UNAUTHORIZED":
                    status_code = 403
                elif res.get("error_code") == "RECORD_NOT_FOUND":
                    status_code = 404
                self._send_json_response(status_code, res, origin=origin)
                return

            if path in ("/api/v1/profile/update", "/api/v1/workspace/update"):
                valid, user = self._authenticate_request_user()
                if not valid or not user:
                    self._send_error_response(401, "Unauthenticated", "Missing or invalid session token.", "Login to update settings.", origin=origin)
                    return

                try:
                    req_data = json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
                except Exception:
                    self._send_error_response(400, "Invalid JSON Request", "Request body was not valid JSON.", "Provide valid JSON body.", origin=origin)
                    return

                if path == "/api/v1/profile/update":
                    target_id = str(req_data.get("user_id", user.user_id)).strip()
                    syms = req_data.get("allowed_symbols")
                    syms_tuple = tuple(syms) if isinstance(syms, list) else None
                    chat_id = req_data.get("telegram_chat_id")
                    delivery = req_data.get("delivery_enabled")
                    detail = req_data.get("detail")

                    try:
                        updated = self.server_user_auth_service.update_user_profile(
                            actor_user=user,
                            target_user_id=target_id,
                            allowed_symbols=syms_tuple,
                            telegram_chat_id=chat_id,
                            delivery_enabled=delivery,
                            detail=detail,
                        )
                        self._send_json_response(200, {"success": True, "user": updated.to_dict()}, origin=origin)
                        return
                    except Exception as err:
                        self._send_error_response(400, "Profile Update Failed", str(err), "Check profile inputs.", origin=origin)
                        return

                if path == "/api/v1/workspace/update":
                    target_id = str(req_data.get("user_id", user.user_id)).strip()
                    chart_p = req_data.get("chart_preferences")
                    layout_p = req_data.get("layout_preferences")
                    notif_p = req_data.get("notification_preferences")
                    act_sym = req_data.get("active_symbol")
                    act_wl = req_data.get("active_watchlist_id")

                    try:
                        ws = self.workspace_service.get_or_create_workspace(user, target_id)
                        if act_sym:
                            ws = self.workspace_service.set_active_symbol(user, target_id, act_sym)
                        if act_wl:
                            ws = self.workspace_service.set_active_watchlist(user, target_id, act_wl)
                        if chart_p or layout_p or notif_p:
                            ws = self.workspace_service.update_preferences(
                                user,
                                target_id,
                                chart_preferences=chart_p,
                                layout_preferences=layout_p,
                                notification_preferences=notif_p,
                            )
                        self._send_json_response(200, {"success": True, "workspace": ws.to_dict()}, origin=origin)
                        return
                    except Exception as err:
                        self._send_error_response(400, "Workspace Update Failed", str(err), "Check workspace inputs.", origin=origin)
                        return

            if path == "/api/v1/notifications/mark-read":
                valid, user = self._authenticate_request_user()
                if not valid or not user:
                    self._send_error_response(401, "Unauthenticated", "Missing or invalid session token.", "Login to update notifications.", origin=origin)
                    return

                try:
                    req_data = json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
                except Exception:
                    self._send_error_response(400, "Invalid JSON Request", "Request body was not valid JSON.", "Provide valid JSON payload.", origin=origin)
                    return

                mark_all = bool(req_data.get("mark_all", False))
                notif_id = str(req_data.get("notification_id", "")).strip()

                try:
                    if mark_all:
                        count = self.notification_service.mark_all_as_read(user, user.user_id)
                        self._send_json_response(200, {"success": True, "marked_count": count}, origin=origin)
                    elif notif_id:
                        updated = self.notification_service.mark_as_read(user, user.user_id, notif_id)
                        self._send_json_response(200, {"success": True, "notification": updated.to_dict()}, origin=origin)
                    else:
                        self._send_error_response(400, "Missing Parameters", "Either 'notification_id' or 'mark_all: true' must be provided.", "Provide notification_id or mark_all flag.", origin=origin)
                    return
                except KeyError as err:
                    self._send_error_response(404, "Notification Not Found", str(err), "Check notification ID.", origin=origin)
                    return
                except Exception as err:
                    self._send_error_response(400, "Update Failed", str(err), "Check request parameters.", origin=origin)
                    return

            if path == "/api/v1/notifications/archive":
                valid, user = self._authenticate_request_user()
                if not valid or not user:
                    self._send_error_response(401, "Unauthenticated", "Missing or invalid session token.", "Login to archive notifications.", origin=origin)
                    return

                try:
                    req_data = json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
                except Exception:
                    self._send_error_response(400, "Invalid JSON Request", "Request body was not valid JSON.", "Provide valid JSON payload.", origin=origin)
                    return

                notif_id = str(req_data.get("notification_id", "")).strip()
                if not notif_id:
                    self._send_error_response(400, "Missing Parameters", "'notification_id' parameter is required.", "Provide notification_id.", origin=origin)
                    return

                try:
                    updated = self.notification_service.archive_notification(user, user.user_id, notif_id)
                    self._send_json_response(200, {"success": True, "notification": updated.to_dict()}, origin=origin)
                    return
                except KeyError as err:
                    self._send_error_response(404, "Notification Not Found", str(err), "Check notification ID.", origin=origin)
                    return

            if path in ("/api/v1/notifications/delete", "/api/v1/notifications/preferences/update"):
                valid, user = self._authenticate_request_user()
                if not valid or not user:
                    self._send_error_response(401, "Unauthenticated", "Missing or invalid session token.", "Login to manage notifications.", origin=origin)
                    return

                try:
                    req_data = json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
                except Exception:
                    self._send_error_response(400, "Invalid JSON Request", "Request body was not valid JSON.", "Provide valid JSON payload.", origin=origin)
                    return

                if path == "/api/v1/notifications/delete":
                    notif_id = str(req_data.get("notification_id", "")).strip()
                    if not notif_id:
                        self._send_error_response(400, "Missing Parameters", "'notification_id' is required.", "Provide notification_id.", origin=origin)
                        return
                    deleted = self.notification_service.delete_notification(user, user.user_id, notif_id)
                    self._send_json_response(200, {"success": deleted}, origin=origin)
                    return

                if path == "/api/v1/notifications/preferences/update":
                    try:
                        ws = self.workspace_service.update_preferences(
                            user,
                            user.user_id,
                            notification_preferences=req_data,
                        )
                        self._send_json_response(200, {"success": True, "preferences": ws.notification_preferences.to_dict()}, origin=origin)
                        return
                    except Exception as err:
                        self._send_error_response(400, "Preference Update Failed", str(err), "Check notification preferences input.", origin=origin)
                        return

            self._send_error_response(
                404,
                what="Endpoint Not Found",
                why=f"POST route '{path}' is not registered on this server.",
                recommended_action="Check the API path and request method.",
                origin=origin,
            )

        except Exception as exc:
            logger.exception("Error handling POST request to %s: %s", path, str(exc))
            self._send_error_response(
                500,
                what="Internal Server Error",
                why="An unexpected error occurred during POST processing.",
                recommended_action="Contact administrator with the provided correlation ID.",
                origin=origin,
            )

    def _serve_static_asset(self, path: str, origin: Optional[str] = None) -> None:
        """Serve static files from web/dist with SPA index.html fallback."""
        if not os.path.exists(self.static_dir):
            self._send_json_response(
                200,
                {
                    "name": "AI-Trading-Lab-Platform Runtime API",
                    "status": "running",
                    "note": "Frontend bundle not compiled in web/dist yet. Run 'npm run build' inside web/ to serve SPA assets.",
                },
                origin=origin,
            )
            return

        rel_path = path.lstrip("/")
        target_path = os.path.normpath(os.path.join(self.static_dir, rel_path))

        # Prevent directory traversal
        if not target_path.startswith(os.path.abspath(self.static_dir)):
            self._send_error_response(403, "Forbidden", "Access denied.", "Request valid path.", origin=origin)
            return

        # If static file exists, serve it
        if os.path.isfile(target_path):
            file_to_serve = target_path
        else:
            # SPA Fallback to index.html for client-side routing
            file_to_serve = os.path.join(self.static_dir, "index.html")

        if not os.path.exists(file_to_serve):
            self._send_error_response(404, "Not Found", "Requested resource not found.", "Check URL.", origin=origin)
            return

        mime_type, _ = mimetypes.guess_type(file_to_serve)
        if mime_type is None:
            mime_type = "application/octet-stream"

        try:
            with open(file_to_serve, "rb") as f:
                content = f.read()

            self.send_response(200)
            self.send_header("Content-Type", mime_type)
            self.send_header("Content-Length", str(len(content)))
            self._set_security_headers(origin=origin)
            self.end_headers()
            self.wfile.write(content)
        except Exception as exc:
            logger.error("Error reading file %s: %s", file_to_serve, str(exc))
            self._send_error_response(500, "Storage Read Error", "Failed reading static asset.", "Retry.", origin=origin)


def create_server(
    host: str = "0.0.0.0",
    port: int = 8000,
    config: Optional[PlatformConfig] = None,
    static_dir: Optional[str] = None,
) -> ThreadingHTTPServer:
    """Initialize and construct the platform ThreadingHTTPServer instance."""
    cfg = config or PlatformConfig.load_from_env()

    # Fail closed in production mode if security secrets are invalid
    if cfg.is_production:
        if not cfg.session_secret or cfg.session_secret == "dev_session_secret_key_change_in_production_2026" or len(cfg.session_secret) < 32:
            raise RuntimeError("CRITICAL PRODUCTION SECURITY FAILURE: SESSION_SECRET is unset or too weak.")

    user_repo = FileBackedUserRepository(storage_dir=cfg.persistence_dir)
    ws_repo = FileBackedWorkspaceRepository(storage_dir=cfg.persistence_dir)
    user_auth_service = UserAuthorizationService(repository=user_repo, config=cfg)
    security_service = SecurityBoundaryService()
    workspace_service = WorkspaceService(repository=ws_repo, security_service=security_service)
    notification_service = NotificationService(security_service=security_service, workspace_service=workspace_service)
    delivery_adapter = RecordingNotificationDeliveryAdapter(available=True, notification_service=notification_service)
    notification_delivery_service = NotificationDeliveryService(
        delivery_port=delivery_adapter,
        user_auth_service=user_auth_service,
        security_service=security_service,
    )

    health_service = SystemHealthService(config=cfg)
    port_adapter = DisconnectedProject1Adapter()
    presenter = Project1SignalPresenter(port=port_adapter, security_service=security_service)
    gateway_service = Project1IntegrationGatewayService(
        security_boundary=security_service,
        notification_service=notification_service,
    )

    resolved_static_dir = static_dir or os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "web", "dist"))

    class CustomHandler(PlatformRequestHandler):
        pass

    CustomHandler.server_user_auth_service = user_auth_service
    CustomHandler.workspace_service = workspace_service
    CustomHandler.notification_service = notification_service
    CustomHandler.notification_delivery_service = notification_delivery_service
    CustomHandler.config = cfg
    CustomHandler.health_service = health_service
    CustomHandler.security_service = security_service
    CustomHandler.presenter = presenter
    CustomHandler.gateway_service = gateway_service
    CustomHandler.static_dir = resolved_static_dir

    server = ThreadingHTTPServer((host, port), CustomHandler)
    return server


def main() -> None:
    """Main execution entry point for platform application server."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    port_str = os.getenv("PORT", "8000")
    try:
        port = int(port_str)
    except ValueError:
        port = 8000

    host = os.getenv("HOST", "0.0.0.0")

    try:
        cfg = PlatformConfig.load_from_env()
        server = create_server(host=host, port=port, config=cfg)
        logger.info("AI-Trading-Lab-Platform server running on http://%s:%d (env: %s)", host, port, cfg.app_env)
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Server shutting down cleanly.")
        sys.exit(0)
    except Exception as exc:
        logger.critical("Fatal server startup failure: %s", str(exc), exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
