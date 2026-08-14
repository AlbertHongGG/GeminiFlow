class GeminiFlowError(Exception):
    """Base exception for all GeminiFlow errors."""
    pass

class AuthenticationError(GeminiFlowError):
    """Raised when authentication fails or cookies are invalid/expired."""
    pass

class NetworkError(GeminiFlowError):
    """Raised when a network request fails (e.g. connection error)."""
    pass

class PayloadError(GeminiFlowError):
    """Raised when the API payload is invalid or rejected."""
    pass

class ProtocolError(GeminiFlowError):
    """Raised when parsing the Gemini API protocol fails."""
    pass

class TokenExpiredError(GeminiFlowError):
    """Raised when SNlM0e or SID tokens are no longer valid during a request."""
    pass

class RequireManualLoginError(AuthenticationError):
    """Raised when the user needs to manually login (e.g. captcha, terms of service)."""
    pass
