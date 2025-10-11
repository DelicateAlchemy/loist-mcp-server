"""
Bearer Token Authentication for Music Library MCP Server
Simple token-based authentication for MVP
"""
import logging
from typing import Optional
from fastmcp.server.auth import AuthProvider, AccessToken

logger = logging.getLogger(__name__)


class SimpleBearerAuth(AuthProvider):
    """
    Simple bearer token authentication provider for MVP
    
    Validates requests against a single configured bearer token.
    For production, consider using JWT, OAuth, or more sophisticated auth.
    """
    
    def __init__(self, token: str, enabled: bool = True, base_url: Optional[str] = None):
        """
        Initialize bearer token authentication
        
        Args:
            token: The valid bearer token to accept
            enabled: Whether authentication is enabled (default: True)
            base_url: Optional base URL for the server
        """
        super().__init__(base_url=base_url)
        self.token = token
        self.enabled = enabled
        logger.info(f"Bearer authentication {'enabled' if enabled else 'disabled'}")
    
    async def verify_token(self, token: str) -> Optional[AccessToken]:
        """
        Verify a bearer token and return access info if valid
        
        Args:
            token: The token string to validate
            
        Returns:
            AccessToken object if valid, None if invalid
        """
        # If auth is disabled, allow all requests
        if not self.enabled:
            logger.debug("Authentication disabled, allowing request")
            return AccessToken(
                token=token,
                client_id="anonymous",
                scopes=[],
                claims={"authenticated": False, "mode": "disabled"}
            )
        
        # Validate token
        if token != self.token:
            logger.warning("Invalid bearer token provided")
            return None
        
        logger.debug("Bearer token validated successfully")
        return AccessToken(
            token=token,
            client_id="api_client",
            scopes=["read", "write"],
            claims={
                "authenticated": True,
                "method": "bearer_token",
                "user_type": "api_client"
            }
        )

