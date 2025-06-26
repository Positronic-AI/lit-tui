"""
Model compatibility checking for LIT TUI.

This module provides dynamic compatibility detection rather than hard-coded lists.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Set
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class ModelCompatibilityCache:
    """Dynamic model compatibility cache that learns from actual usage."""
    
    def __init__(self, cache_file: Optional[Path] = None):
        """Initialize compatibility cache."""
        self.cache_file = cache_file or Path.home() / ".lit-tui" / "model_compatibility.json"
        self.cache: Dict[str, Dict] = self._load_cache()
        
    def _load_cache(self) -> Dict[str, Dict]:
        """Load compatibility cache from file."""
        try:
            if self.cache_file.exists():
                with open(self.cache_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load compatibility cache: {e}")
        
        return {}
    
    def _save_cache(self) -> None:
        """Save compatibility cache to file."""
        try:
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.cache_file, 'w') as f:
                json.dump(self.cache, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save compatibility cache: {e}")
    
    def get_compatibility(self, model_name: str) -> Optional[bool]:
        """
        Get cached compatibility for a model.
        
        Returns None if unknown, True/False if known.
        """
        if model_name not in self.cache:
            return None
            
        entry = self.cache[model_name]
        
        # Check if entry is stale (older than 30 days)
        last_updated = datetime.fromisoformat(entry.get('last_updated', '2000-01-01'))
        if datetime.now() - last_updated > timedelta(days=30):
            logger.debug(f"Compatibility cache for {model_name} is stale, ignoring")
            return None
        
        return entry.get('supports_tools')
    
    def set_compatibility(self, model_name: str, supports_tools: bool, reason: str = "") -> None:
        """Record compatibility result for a model."""
        self.cache[model_name] = {
            'supports_tools': supports_tools,
            'last_updated': datetime.now().isoformat(),
            'reason': reason,
            'test_count': self.cache.get(model_name, {}).get('test_count', 0) + 1
        }
        self._save_cache()
        logger.info(f"Recorded {model_name} tool support: {supports_tools} ({reason})")


class DynamicModelCompatibility:
    """Dynamic model compatibility detection."""
    
    def __init__(self, config_override: Optional[Dict] = None):
        """
        Initialize compatibility checker.
        
        Args:
            config_override: Optional user configuration for model compatibility
        """
        self.cache = ModelCompatibilityCache()
        self.config_override = config_override or {}
        
        # Minimal heuristics - only the most obvious patterns
        self.known_patterns = {
            'likely_incompatible': [
                'code',  # Code-focused models often lack tool support
                'embed',  # Embedding models
                'vision',  # Vision-only models
            ],
            'likely_compatible': [
                'chat',  # Chat-focused models
                'instruct',  # Instruction-following models
            ]
        }
    
    def supports_tools(self, model_name: str) -> bool:
        """
        Determine if a model supports tools using dynamic detection.
        
        This is optimistic - assumes support unless proven otherwise.
        """
        # 1. Check user configuration override first
        if model_name in self.config_override:
            result = self.config_override[model_name]
            logger.info(f"Model {model_name} compatibility from config: {result}")
            return result
        
        # 2. Check cache
        cached = self.cache.get_compatibility(model_name)
        if cached is not None:
            logger.debug(f"Model {model_name} compatibility from cache: {cached}")
            return cached
        
        # 3. Use heuristics as last resort
        compatibility = self._heuristic_check(model_name)
        logger.info(f"Model {model_name} compatibility from heuristics: {compatibility}")
        return compatibility
    
    def _heuristic_check(self, model_name: str) -> bool:
        """Use simple heuristics to guess compatibility."""
        lower_name = model_name.lower()
        
        # Check for likely incompatible patterns
        for pattern in self.known_patterns['likely_incompatible']:
            if pattern in lower_name:
                return False
        
        # Default to optimistic (True) - let the user discover limitations
        return True
    
    def record_tool_attempt_result(self, model_name: str, success: bool, error_msg: str = "") -> None:
        """
        Record the result of a tool execution attempt.
        
        This helps the system learn which models actually work.
        """
        reason = "successful_tool_execution" if success else f"failed: {error_msg}"
        self.cache.set_compatibility(model_name, success, reason)
    
    def get_model_info(self, model_name: str) -> Dict:
        """Get comprehensive info about a model's compatibility."""
        cached_entry = self.cache.cache.get(model_name, {})
        
        return {
            'model_name': model_name,
            'supports_tools': self.supports_tools(model_name),
            'source': self._get_compatibility_source(model_name),
            'last_tested': cached_entry.get('last_updated'),
            'test_count': cached_entry.get('test_count', 0),
            'last_reason': cached_entry.get('reason', 'Not tested')
        }
    
    def _get_compatibility_source(self, model_name: str) -> str:
        """Determine where compatibility info came from."""
        if model_name in self.config_override:
            return "user_config"
        elif self.cache.get_compatibility(model_name) is not None:
            return "learned_from_usage"
        else:
            return "heuristic_guess"
    
    def suggest_alternative_model(self, current_model: str, available_models: List[str]) -> Optional[str]:
        """
        Suggest an alternative model based on compatibility data.
        
        Prefers models with proven tool support over untested ones.
        """
        compatible_models = []
        
        for model in available_models:
            if self.supports_tools(model):
                info = self.get_model_info(model)
                compatible_models.append((model, info))
        
        if not compatible_models:
            return None
        
        # Sort by reliability: proven > heuristic guess
        def sort_key(item):
            model, info = item
            if info['source'] == 'learned_from_usage' and info['test_count'] > 0:
                return 0  # Most reliable
            elif info['source'] == 'user_config':
                return 1  # User preference
            else:
                return 2  # Heuristic guess
        
        compatible_models.sort(key=sort_key)
        return compatible_models[0][0]


# Global instance
_compatibility_checker: Optional[DynamicModelCompatibility] = None

def get_compatibility_checker(config_override: Optional[Dict] = None) -> DynamicModelCompatibility:
    """Get or create the global compatibility checker."""
    global _compatibility_checker
    if _compatibility_checker is None:
        _compatibility_checker = DynamicModelCompatibility(config_override)
    return _compatibility_checker

def supports_tools(model_name: str) -> bool:
    """Check if a model supports tools (convenience function)."""
    return get_compatibility_checker().supports_tools(model_name)

def record_tool_result(model_name: str, success: bool, error_msg: str = "") -> None:
    """Record tool execution result (convenience function)."""
    get_compatibility_checker().record_tool_attempt_result(model_name, success, error_msg)

def suggest_alternative_model(current_model: str, available_models: List[str]) -> Optional[str]:
    """Suggest alternative model (convenience function)."""
    return get_compatibility_checker().suggest_alternative_model(current_model, available_models)
