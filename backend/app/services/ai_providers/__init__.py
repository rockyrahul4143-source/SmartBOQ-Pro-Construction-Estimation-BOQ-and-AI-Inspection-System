"""
AI Provider Abstraction Layer for SmartBOQ Pro
==============================================

Provider-agnostic AI interface supporting multiple AI vendors for 
structural document understanding and engineering data extraction.

Supported providers:
- Gemini (Google AI)
- OpenAI (GPT-4, GPT-4V)  
- Anthropic (Claude)

Configuration via environment variables:
- AI_PROVIDER=gemini|openai|anthropic|disabled
- GEMINI_API_KEY, OPENAI_API_KEY, ANTHROPIC_API_KEY
- AI_MODEL (provider-specific model name)
- AI_MAX_TOKENS, AI_TEMPERATURE
"""

from .base_provider import (
    AIProvider,
    DocumentType,
    ExtractionRequest,
    ExtractionResponse,
    StructuralMember,
    SourceReference,
    ValidationStatus,
    AIError,
)

from .provider_factory import get_ai_provider, configure_provider, get_provider_info

__all__ = [
    "AIProvider",
    "DocumentType", 
    "ExtractionRequest",
    "ExtractionResponse",
    "StructuralMember",
    "SourceReference",
    "ValidationStatus",
    "AIError",
    "get_ai_provider",
    "configure_provider",
    "get_provider_info",
]