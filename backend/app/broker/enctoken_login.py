"""Headless login for Zerodha web session (enctoken).

Extracts the enctoken cookie after username/password + TOTP 2FA.
This bypasses official Kite Connect OAuth and uses Zerodha's internal web APIs.

WARNING: Unofficial — may break if Zerodha changes login flow. Use at your own risk.
"""

import logging

import httpx
import pyotp

logger = logging.getLogger(__name__)

KITE_LOGIN = "https://kite.zerodha.com/api/login"
KITE_TWOFA = "https://kite.zerodha.com/api/twofa"


def normalize_totp_secret(secret: str) -> str:
    """Strip spaces and uppercase — matches Google Authenticator base32 format."""
    return secret.replace(" ", "").strip().upper()


class EnctokenLoginService:
    async def login(
        self,
        user_id: str,
        password: str,
        totp_secret: str | None = None,
        twofa_value: str | None = None,
    ) -> tuple[str, str]:
        """Return (user_id, enctoken) after successful web login."""
        if not totp_secret and not twofa_value:
            raise ValueError("TOTP secret or one-time 2FA code required for automated enctoken login")

        otp = twofa_value or pyotp.TOTP(normalize_totp_secret(totp_secret)).now()

        async with httpx.AsyncClient(follow_redirects=False, timeout=30) as client:
            r1 = await client.post(KITE_LOGIN, data={"user_id": user_id, "password": password})
            r1.raise_for_status()
            data1 = r1.json()
            if data1.get("status") != "success":
                raise RuntimeError(f"Login failed: {data1.get('message', data1)}")

            request_id = data1["data"]["request_id"]
            uid = data1["data"].get("user_id", user_id)

            r2 = await client.post(
                KITE_TWOFA,
                data={
                    "user_id": uid,
                    "request_id": request_id,
                    "twofa_value": otp,
                    "twofa_type": "totp",
                },
            )
            r2.raise_for_status()
            data2 = r2.json()
            if data2.get("status") != "success":
                raise RuntimeError(f"2FA failed: {data2.get('message', data2)}")

            enctoken = r2.cookies.get("enctoken")
            if not enctoken:
                raise RuntimeError("No enctoken in login response — check credentials or 2FA")

            logger.info("Enctoken login success for user %s", uid)
            return uid, enctoken
