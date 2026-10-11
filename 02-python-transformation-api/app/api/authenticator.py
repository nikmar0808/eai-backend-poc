import hmac
import logging
from typing import Optional

from fastapi import HTTPException, Security, status
from fastapi.security.api_key import APIKeyHeader

from app.config import settings

# Configure structured logging for the API module
logger = logging.getLogger(__name__)

# Declare the specific header key name the system will look for in network packets
API_KEY_NAME = "X-EAI-TOKEN"
api_key_header_guard = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

# -------------------------------------------------------------------------
# SECURITY INTERCEPTOR FUNCTION
# -------------------------------------------------------------------------
def authenticate_request(api_key: Optional[str] = Security(api_key_header_guard)) -> str:
    """Validate the inbound token header against the configured token.

    The comparison is constant-time (hmac.compare_digest) so that response timing does not reveal how many leading
    characters of a guess were correct. Both sides are encoded because compare_digest requires bytes or ASCII-only str.
    """
    if api_key is not None and hmac.compare_digest(
        api_key.encode("utf-8"), settings.API_SECURITY_TOKEN.encode("utf-8")
    ):
        return api_key
    logger.warning("Unauthorized request rejected: missing or invalid token.")
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Access Denied: Invalid Security Credentials.",
    )

