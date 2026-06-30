"""Headless TOTP auto-login for Zerodha Kite.

WARNING: Zerodha mandates manual login once per day. Automating login is not
recommended and may violate broker terms. Use at your own risk.
"""

import logging
import re
from urllib.parse import parse_qs, urlparse

import httpx
import pyotp

logger = logging.getLogger(__name__)

KITE_LOGIN = "https://kite.zerodha.com/api/login"
KITE_TWOFA = "https://kite.zerodha.com/api/twofa"


class TotpLoginService:
    def __init__(
        self,
        api_key: str,
        api_secret: str,
        totp_secret: str,
        redirect_url: str,
        password: str | None = None,
    ):
        self.api_key = api_key
        self.api_secret = api_secret
        self.totp_secret = totp_secret
        self.redirect_url = redirect_url
        self.password = password

    async def login(self, user_id: str, password: str | None = None) -> str:
        pwd = password or self.password
        if not pwd:
            raise ValueError("Password required for TOTP auto-login")

        async with httpx.AsyncClient(follow_redirects=False, timeout=30) as client:
            r1 = await client.post(
                KITE_LOGIN,
                data={"user_id": user_id, "password": pwd},
            )
            r1.raise_for_status()
            data1 = r1.json()
            if data1.get("status") != "success":
                raise RuntimeError(f"Login failed: {data1}")

            totp = pyotp.TOTP(self.totp_secret).now()
            r2 = await client.post(
                KITE_TWOFA,
                data={
                    "user_id": user_id,
                    "request_id": data1["data"]["request_id"],
                    "twofa_value": totp,
                },
            )
            r2.raise_for_status()
            data2 = r2.json()
            if data2.get("status") != "success":
                raise RuntimeError(f"2FA failed: {data2}")

            login_url = (
                f"https://kite.zerodha.com/connect/login?api_key={self.api_key}"
                f"&v=3&redirect_url={self.redirect_url}"
            )
            r3 = await client.get(login_url)
            if r3.status_code in (301, 302, 303, 307, 308):
                location = r3.headers.get("location", "")
                request_token = self._extract_request_token(location)
                if request_token:
                    from app.broker.kite_client import KiteService

                    kite = KiteService(self.api_key, self.api_secret)
                    session = kite.generate_session(request_token)
                    return session["access_token"]

            raise RuntimeError("Could not obtain request_token from redirect")

    def _extract_request_token(self, url: str) -> str | None:
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        tokens = qs.get("request_token", [])
        if tokens:
            return tokens[0]
        match = re.search(r"request_token=([^&]+)", url)
        return match.group(1) if match else None
