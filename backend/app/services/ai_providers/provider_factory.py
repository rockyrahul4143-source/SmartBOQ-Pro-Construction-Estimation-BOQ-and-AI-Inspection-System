"""
AI Provider Factory and Configuration
====================================

Factory for creating AI provider instances based on environment configuration.
Handles provider selection, API key management, and fallback strategies.
"""

import os
import logging
from typing import Optional, Dict, Any

from .base_provider import AIProvider, AIError

logger = logging.getLogger(__name__)

# Global provider instance (lazy-loaded)
_provider_instance: Optional[AIProvider] = None
_provider_config: Dict[str, Any] = {}

def get_ai_provider() -> Optional[AIProvider]:
    """
    Get the configured AI provider instance.
    
    Returns None if no provider is configured (AI_PROVIDER=disabled).
    Lazy-loads the provider on first call.
    
    Environment variables:
        AI_PROVIDER: gemini|openai|anthropic|disabled (default: disabled)
        AI_MODEL: Provider-specific model name
        AI_MAX_TOKENS: Maximum tokens for responses (default: 4000)
        AI_TEMPERATURE: Sampling temperature (default: 0.1)
        
        GEMINI_API_KEY: Google AI API key
        OPENAI_API_KEY: OpenAI API key  
        ANTHROPIC_API_KEY: Anthropic API key
    
    Returns:
        AIProvider instance or None if disabled
        
    Raises:
        AIError: If provider configuration is invalid
    """
    global _provider_instance, _provider_config
    
    # Get configuration
    provider_name = os.environ.get("AI_PROVIDER", "disabled").lower().strip()
    
    if provider_name in ("disabled", "none", "", "off"):
        return None
    
    # Check if we need to reload provider
    current_config = {
        "provider": provider_name,
        "model": os.environ.get("AI_MODEL", ""),
        "max_tokens": int(os.environ.get("AI_MAX_TOKENS", "4000")),
        "temperature": float(os.environ.get("AI_TEMPERATURE", "0.1")),
    }
    
    if _provider_instance is None or _provider_config != current_config:
        logger.info(f"[AI Provider] Loading provider: {provider_name}")
        _provider_instance = _create_provider(provider_name, current_config)
        _provider_config = current_config
    
    return _provider_instance

def configure_provider(
    provider_name: str,
    api_key: str,
    model: str = "",
    **kwargs
) -> AIProvider:
    """
    Create and configure an AI provider programmatically.
    
    Args:
        provider_name: "gemini", "openai", or "anthropic"
        api_key: API key for the provider
        model: Model name (provider-specific)
        **kwargs: Additional configuration
        
    Returns:
        Configured AIProvider instance
        
    Raises:
        AIError: If provider creation fails
    """
    config = {
        "model": model,
        "max_tokens": kwargs.get("max_tokens", 4000),
        "temperature": kwargs.get("temperature", 0.1),
        **kwargs
    }
    
    return _create_provider(provider_name, config, api_key)

def _create_provider(
    provider_name: str, 
    config: Dict[str, Any],
    api_key_override: str = None
) -> AIProvider:
    """
    Internal factory method to create provider instances.
    
    Args:
        provider_name: Provider identifier
        config: Provider configuration
        api_key_override: Optional API key override
        
    Returns:
        AIProvider instance
        
    Raises:
        AIError: If provider creation fails
    """
    provider_name = provider_name.lower().strip()
    
    # Get API key
    if api_key_override:
        api_key = api_key_override
    else:
        api_key_map = {
            "gemini": "GEMINI_API_KEY",
            "openai": "OPENAI_API_KEY", 
            "anthropic": "ANTHROPIC_API_KEY"
        }
        
        env_var = api_key_map.get(provider_name)
        if not env_var:
            raise AIError(f"Unknown AI provider: {provider_name}")
        
        api_key = os.environ.get(env_var, "")
        if not api_key:
            raise AIError(
                f"API key not found: {env_var}. "
                f"Set environment variable or use AI_PROVIDER=disabled"
            )
    
    # Create provider instance
    try:
        if provider_name == "gemini":
            from .gemini_provider import GeminiProvider
            return GeminiProvider(api_key=api_key, **config)
            
        elif provider_name == "openai":
            from .openai_provider import OpenAIProvider
            return OpenAIProvider(api_key=api_key, **config)
            
        elif provider_name == "anthropic":
            from .anthropic_provider import AnthropicProvider
            return AnthropicProvider(api_key=api_key, **config)
            
        else:
            raise AIError(f"Unsupported AI provider: {provider_name}")
            
    except ImportError as e:
        raise AIError(
            f"Provider {provider_name} implementation not available: {e}"
        )
    except Exception as e:
        raise AIError(f"Failed to create {provider_name} provider: {e}")

def reset_provider() -> None:
    """Reset the global provider instance (for testing)."""
    global _provider_instance, _provider_config
    _provider_instance = None
    _provider_config = {}

def is_ai_enabled() -> bool:
    """Check if AI provider is enabled and configured."""
    try:
        provider = get_ai_provider()
        return provider is not None
    except Exception:
        return False

def get_provider_info() -> Dict[str, Any]:
    """Get information about the current provider configuration."""
    provider_name = os.environ.get("AI_PROVIDER", "disabled")
    
    info = {
        "provider": provider_name,
        "enabled": provider_name not in ("disabled", "none", "", "off"),
        "model": os.environ.get("AI_MODEL", ""),
        "max_tokens": os.environ.get("AI_MAX_TOKENS", "4000"),
        "temperature": os.environ.get("AI_TEMPERATURE", "0.1"),
    }
    
    if info["enabled"]:
        # Check if API key is available (don't expose the key)
        key_map = {
            "gemini": "GEMINI_API_KEY",
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY"
        }
        
        env_var = key_map.get(provider_name.lower())
        if env_var:
            api_key = os.environ.get(env_var, "")
            info["api_key_configured"] = bool(api_key)
            info["api_key_env_var"] = env_var
        else:
            info["api_key_configured"] = False
            info["error"] = f"Unknown provider: {provider_name}"
    
    return info