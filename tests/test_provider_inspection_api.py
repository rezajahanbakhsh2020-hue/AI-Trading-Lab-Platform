"""Tests for provider inspection API endpoints."""

import json
import tempfile
import unittest
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from src.platform.config import PlatformConfig
from src.platform.server import create_server


class TestProviderInspectionAPI(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config = PlatformConfig(
            app_env="testing",
            persistence_dir=self.temp_dir.name,
            session_secret="test-secret-key",
            initial_admin_password="TestAdminPassword123!",
        )
        self.server = create_server(
            host="127.0.0.1",
            port=0,
            config=self.config,
        )
        self.port = self.server.server_address[1]
        self.base_url = f"http://127.0.0.1:{self.port}"
        import threading
        self.server_thread = threading.Thread(target=self.server.serve_forever)
        self.server_thread.daemon = True
        self.server_thread.start()

        # Login via HTTP to obtain valid token
        login_data = json.dumps({"user_id": "demo_user", "password": "DevCustomerPass2026!"}).encode("utf-8")
        login_req = Request(f"{self.base_url}/api/v1/auth/login", data=login_data, headers={"Content-Type": "application/json"})
        with urlopen(login_req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            self.valid_token = data.get("token")

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.temp_dir.cleanup()

    def test_inspect_unauthenticated_returns_401(self) -> None:
        req = Request(f"{self.base_url}/api/v1/providers/inspect")
        with self.assertRaises(HTTPError) as ctx:
            urlopen(req)
        self.assertEqual(ctx.exception.code, 401)
        data = json.loads(ctx.exception.read().decode("utf-8"))
        self.assertTrue(data["error"])
        self.assertEqual(data["what"], "Unauthorized Access")

    def test_inspect_all_providers_authenticated(self) -> None:
        req = Request(f"{self.base_url}/api/v1/providers/inspect")
        req.add_header("Authorization", f"Bearer {self.valid_token}")
        with urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(data["success"])
            self.assertIn("inspections", data)
            inspections = data["inspections"]
            self.assertGreaterEqual(len(inspections), 2)
            categories = [ins["category"] for ins in inspections]
            self.assertIn("market_data", categories)
            self.assertIn("quote", categories)

    def test_inspect_provider_by_category_and_id(self) -> None:
        req = Request(f"{self.base_url}/api/v1/providers/inspect?category=market_data&provider_id=biquote")
        req.add_header("Authorization", f"Bearer {self.valid_token}")
        with urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(data["success"])
            inspections = data["inspections"]
            self.assertEqual(len(inspections), 1)
            self.assertEqual(inspections[0]["category"], "market_data")
            self.assertEqual(inspections[0]["provider_id"], "biquote")
            self.assertTrue(inspections[0]["capability"]["supports_fetch_candles"])

    def test_inspect_unknown_provider_returns_400(self) -> None:
        req = Request(f"{self.base_url}/api/v1/providers/inspect?category=market_data&provider_id=unknown_id")
        req.add_header("Authorization", f"Bearer {self.valid_token}")
        with self.assertRaises(HTTPError) as ctx:
            urlopen(req)
        self.assertEqual(ctx.exception.code, 400)
        data = json.loads(ctx.exception.read().decode("utf-8"))
        self.assertTrue(data["error"])
        self.assertEqual(data["what"], "Provider Inspection Failed")


if __name__ == "__main__":
    unittest.main()
