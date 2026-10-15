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

class RateLimitError(GeminiFlowError):
    """Raised when Google responds with HTTP 429 Too Many Requests or rate limits."""
    pass

class RequireManualLoginError(AuthenticationError):
    """Raised when the user needs to manually login (e.g. captcha, terms of service)."""
    pass

class AttestationError(GeminiFlowError):
    """Raised when Botguard attestation or token signing fails."""
    pass

class ChallengeFetchError(AttestationError):
    """Raised when fetching Botguard challenge from Waa server fails."""
    pass

class VmExecutionError(AttestationError):
    """Raised when executing the Botguard VM in the JS engine fails."""
    pass

class PromptInputError(GeminiFlowError):
    """Raised when resolving a prompt input fails."""
    pass

class PromptFileNotFoundError(PromptInputError):
    """Raised when the specified prompt file does not exist or cannot be accessed."""
    pass

class PromptEmptyError(PromptInputError):
    """Raised when the prompt content is empty or only whitespace."""
    pass

class PromptEncodingError(PromptInputError):
    """Raised when the prompt file cannot be decoded as text."""
    pass

class PromptConflictError(PromptInputError):
    """Raised when conflicting prompt sources are provided (e.g. both inline prompt and file)."""
    pass

