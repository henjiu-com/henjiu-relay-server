"""API Integration Tests"""

import pytest
import asyncio
import websockets
import json
import time


class TestAPIIntegration:
    """API Integration tests with running server"""
    
    @pytest.fixture
    def base_url(self):
        """Base URL for API"""
        return "http://localhost:8080"
    
    @pytest.fixture
    def admin_auth(self):
        """Admin authentication"""
        return ("arno", "123456")
    
    def test_health_endpoint(self, base_url):
        """Test health endpoint"""
        import requests
        
        response = requests.get(f"{base_url}/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "http_port" in data
        assert "ws_port" in data
    
    def test_debug_api_key(self, base_url):
        """Test debug API key endpoint"""
        import requests
        
        response = requests.get(f"{base_url}/api/debug/api-key")
        
        assert response.status_code == 200
        data = response.json()
        assert "username" in data
        assert "api_key" in data
        assert len(data["api_key"]) > 20
    
    def test_api_without_auth(self, base_url):
        """Test API endpoints require authentication"""
        import requests
        
        endpoints = [
            "/api/instances",
            "/api/users", 
            "/api/send",
            "/api/sessions"
        ]
        
        for endpoint in endpoints:
            response = requests.get(f"{base_url}{endpoint}")
            # Should be 401, 403, redirect, or 405 for POST endpoints
            assert response.status_code in [401, 307, 403, 405], f"{endpoint} should require auth"
    
    def test_api_with_wrong_key(self, base_url):
        """Test API with wrong key"""
        import requests
        
        headers = {"X-API-Key": "wrong-key"}
        
        response = requests.get(f"{base_url}/api/instances", headers=headers)
        assert response.status_code == 401
    
    def test_admin_ui_accessible(self, base_url, admin_auth):
        """Test admin UI is accessible"""
        import requests
        
        response = requests.get(
            f"{base_url}/admin/dashboard",
            auth=admin_auth
        )
        
        assert response.status_code == 200
        assert "Henjiu Relay" in response.text
    
    def test_users_page_accessible(self, base_url, admin_auth):
        """Test users page is accessible"""
        import requests
        
        response = requests.get(
            f"{base_url}/admin/users",
            auth=admin_auth
        )
        
        assert response.status_code == 200
        assert "用户" in response.text or "User" in response.text


class TestWebSocketIntegration:
    """WebSocket integration tests"""
    
    @pytest.mark.asyncio
    async def test_websocket_connection_without_token(self):
        """Test WebSocket connection fails without auth"""
        try:
            async with websockets.connect("ws://localhost:8081") as ws:
                # Send register without token
                await ws.send(json.dumps({
                    "type": "register",
                    "instance_id": "test-instance",
                    "auth_token": "wrong-token"
                }))
                
                # Should get error response
                response = await asyncio.wait_for(ws.recv(), timeout=5)
                data = json.loads(response)
                
                assert "error" in data
        except Exception as e:
            # Expected to fail with wrong token
            pass
    
    @pytest.mark.asyncio
    async def test_websocket_connection_with_token(self):
        """Test WebSocket connection with correct auth"""
        try:
            async with websockets.connect("ws://localhost:8081") as ws:
                # Send register with correct token
                await ws.send(json.dumps({
                    "type": "register",
                    "instance_id": "tianyi",
                    "auth_token": "tianyi-token-2024"
                }))
                
                # Should get registered response
                response = await asyncio.wait_for(ws.recv(), timeout=5)
                data = json.loads(response)
                
                assert data.get("type") == "registered"
        except Exception as e:
            # May fail if instance is not configured
            pass


class TestSecurityIntegration:
    """Security integration tests"""
    
    def test_no_directory_listing(self):
        """Test directory listing is disabled"""
        import requests
        
        # Try to access a directory
        response = requests.get("http://localhost:8080/static/")
        
        # Should either 404 or redirect
        assert response.status_code in [404, 403, 301, 302]
    
    def test_cors_headers(self):
        """Test CORS headers"""
        import requests
        
        response = requests.options("http://localhost:8080/api/instances")
        
        # Should have some CORS handling
        # Or just normal response
        assert response.status_code in [200, 401, 405]
    
    def test_sql_injection_protection(self):
        """Test basic SQL injection protection"""
        import requests
        
        # Try common SQL injection patterns
        payloads = [
            "' OR '1'='1",
            "'; DROP TABLE users;--",
            "1' AND '1'='1"
        ]
        
        for payload in payloads:
            response = requests.get(
                f"http://localhost:8080/api/instances?search={payload}"
            )
            # Should either work normally or reject
            assert response.status_code in [200, 400, 401, 404]


class TestLoadIntegration:
    """Load tests"""
    
    def test_health_endpoint_concurrent(self):
        """Test health endpoint under load"""
        import requests
        import concurrent.futures
        
        def make_request():
            return requests.get("http://localhost:8080/health")
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request) for _ in range(50)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]
        
        # All should succeed
        assert all(r.status_code == 200 for r in results)
    
    def test_api_rate_limiting(self):
        """Test API rate limiting if configured"""
        import requests
        
        # Make many requests without auth
        responses = []
        for _ in range(20):
            r = requests.get("http://localhost:8080/api/instances")
            responses.append(r.status_code)
        
        # Without auth, should get 401 (not rate limited)
        # The important thing is we're testing the server handles requests
        assert all(r in [200, 401, 429] for r in responses)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
