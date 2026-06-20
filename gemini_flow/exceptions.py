from __future__ import annotations

class GeminiFlowError(Exception):
    """Base exception for GeminiFlow"""
    pass

class AuthenticationError(GeminiFlowError):
    """Raised when authentication fails (e.g. missing cookies, expired tokens)"""
    pass

class NetworkError(GeminiFlowError):
    """Raised when a network request to Google fails"""
    pass

class PayloadError(GeminiFlowError):
    """Raised when request payload or response cannot be parsed properly"""
    pass

class TokenFetchError(AuthenticationError):
    """Raised when SNlM0e token cannot be extracted"""
    pass
