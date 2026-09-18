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
from src.platform.adapters.project1_adapter import DisconnectedProject1Adapter
from src.platform.services.user_authorization import UserAuthorizationService
from src.platform.services.health_operations import SystemHealthService
from src.platform.services.security import SecurityBoundaryService, SecretSanitizer
from src.platform.services.project1_presenter import Project1SignalPresenter

logger = logging.getLogger("platform.server")


class PlatformRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler for API, health, authentication, user management, and SPA static assets."""

    config: PlatformConfig
    server_user_auth_service: UserAuthorizationService
    health_service: SystemHealthService
    security_service: SecurityBoundaryService
    presenter: Project1SignalPresenter
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

            if path == "/api/v1/snapshot":
                token = self._extract_bearer_token()
                user = None
                if token:
                    _, user = self.server_user_auth_service.validate_session_token(token)
                snapshot = self.presenter.build_host_snapshot(user=user)
                self._send_json_response(200, snapshot, origin=origin)
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

            if path in ("/api/v1/users/create", "/api/v1/users/status", "/api/v1/users/renew"):
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

    repo = FileBackedUserRepository(storage_dir=cfg.persistence_dir)
    user_auth_service = UserAuthorizationService(repository=repo, config=cfg)
    health_service = SystemHealthService(config=cfg)
    security_service = SecurityBoundaryService()
    port_adapter = DisconnectedProject1Adapter()
    presenter = Project1SignalPresenter(port=port_adapter, security_service=security_service)

    resolved_static_dir = static_dir or os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "web", "dist"))

    class CustomHandler(PlatformRequestHandler):
        server_user_auth_service = user_auth_service

    CustomHandler.config = cfg
    CustomHandler.health_service = health_service
    CustomHandler.security_service = security_service
    CustomHandler.presenter = presenter
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
