"""
System prompt composer integration for LIT TUI.

This module provides intelligent system prompt generation using the 
system-prompt-composer package, with fallback to basic prompts when
the package is not available.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

# Try to import system-prompt-composer
try:
    import system_prompt_composer
    SYSTEM_PROMPT_COMPOSER_AVAILABLE = True
    logger.info("✅ system-prompt-composer loaded - enhanced prompts enabled")
except ImportError as e:
    SYSTEM_PROMPT_COMPOSER_AVAILABLE = False
    logger.warning("📦 system-prompt-composer not available - using basic prompts")
    logger.warning(f"   To enable enhanced prompts: pip install system-prompt-composer")
    logger.warning(f"   Import error: {e}")
    system_prompt_composer = None


class PromptComposer:
    """Service for composing intelligent system prompts."""
    
    def __init__(self, config=None):
        """Initialize the prompt composer."""
        self.config = config
        
    def compose_system_prompt(
        self,
        user_message: str,
        mcp_tools: List[Any],  # List of MCPTool objects
        messages: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Compose an intelligent system prompt.
        
        Args:
            user_message: The user's latest message
            mcp_tools: List of available MCP tools
            messages: Chat message history
            context: Additional context information
            
        Returns:
            Dict with system_prompt and metadata
        """
        if not SYSTEM_PROMPT_COMPOSER_AVAILABLE:
            return self._generate_fallback_prompt(mcp_tools, context)
        
        try:
            # Prepare MCP configuration for prompt composer
            mcp_config = self._prepare_mcp_config(mcp_tools)
            
            # Build request for system-prompt-composer
            request = {
                "user_prompt": user_message,
                "mcp_config": mcp_config,
                "session_state": {
                    "tool_call_count": len([m for m in messages if self._has_tool_call(m)]),
                }
            }
            
            # Add context if provided
            if context:
                request["context"] = context
            
            # Call system-prompt-composer
            logger.info("🧠 Composing system prompt with system-prompt-composer")
            
            try:
                # Serialize and validate request
                request_json = json.dumps(request)
                json.loads(request_json)  # Validate
                
                # Use built-in prompts for now
                logger.info("📦 Using built-in prompts")
                response_json = system_prompt_composer.compose_system_prompt(request_json)
                
                response = json.loads(response_json)
                
                logger.info(f"✅ System prompt composed: {len(response.get('system_prompt', ''))} chars")
                if response.get('applied_modules'):
                    logger.info(f"Applied modules: {response['applied_modules']}")
                if response.get('recognized_tools'):
                    logger.info(f"Recognized tools: {len(response['recognized_tools'])}")
                
                return response
                
            except json.JSONEncodeError as e:
                logger.error(f"Error serializing request to JSON: {e}")
                raise
            except RuntimeError as e:
                if "Invalid JSON request" in str(e):
                    logger.error(f"System-prompt-composer rejected JSON request: {e}")
                    logger.error(f"Problematic request keys: {list(request.keys())}")
                raise
                
        except Exception as e:
            logger.error(f"Error composing system prompt: {e}")
            logger.exception(e)
            return self._generate_fallback_prompt(mcp_tools, context)
    
    def _prepare_mcp_config(self, mcp_tools: List[Any]) -> Dict[str, Any]:
        """Prepare MCP configuration from tools list."""
        # Create proper MCP config format that system-prompt-composer expects
        servers = {}
        
        for tool in mcp_tools:
            server_name = getattr(tool, 'server_name', 'default') or 'default'
            
            if server_name not in servers:
                servers[server_name] = {
                    "name": server_name,
                    "command": "mcp-server",  # Generic command
                    "args": [],
                    "env": {}
                }
        
        return {"mcpServers": servers}
    
    def _has_tool_call(self, message: Dict[str, Any]) -> bool:
        """Check if a message contains a tool call."""
        content = str(message.get('content', ''))
        return '"tool":' in content or 'function_call' in content
    
    def _generate_fallback_prompt(
        self, 
        mcp_tools: List[Any],  # List of MCPTool objects
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Generate a comprehensive fallback prompt when system-prompt-composer is unavailable."""
        
        system_prompt = "You are a helpful AI assistant."
        
        if mcp_tools:
            # Use exact format from working lit-lib implementation
            tools_json = self._format_tools_for_prompt_detailed(mcp_tools)
            
            system_prompt = f"""You have access to the following tools:

{tools_json}

To use a tool, respond with JSON in the following format:
{{
  "tool": "server_name.tool_name",
  "arguments": {{
    "path": "value1"
  }}
}}

**KEY INSTRUCTION**: When users ask to "create an MCP tool", use desktop-commander.write_file to save a Python file to /data/team/mcp_tools/toolname.py. The content must be properly formatted Python code with actual newlines (not literal \\n characters):

Example tool call:
```json
{{
  "tool": "desktop-commander.write_file",
  "arguments": {{
    "path": "/data/team/mcp_tools/toolname.py",
    "content": "def invoke(arguments):\\n    \\"\\"\\"Tool description here.\\n    \\n    Parameters:\\n    - param_name: Description (type)\\n    \\"\\"\\"\\n    try:\\n        value = arguments.get('param_name', 'default')\\n        return f\\"Result: {{value}}\\"\\n    except Exception as e:\\n        return f\\"Error: {{str(e)}}\\"\\""
  }}
}}
```

CRITICAL: The \\n in the content string represents actual newlines, not literal backslash-n characters. Use proper Python string escaping.

Only use the tools when explicitly requested by the user or when they would significantly help with the user's request.
When a user asks you to read or write files or access system resources, you should use the appropriate tool rather than saying you can't."""
        
        return {
            "system_prompt": system_prompt,
            "source": "fallback",
            "fallback": True,
            "version": "1.0.0-fallback"
        }
    
    def _format_tools_for_prompt_detailed(self, mcp_tools: List[Any]) -> str:
        """Format tools for inclusion in the system prompt using lit-lib approach."""
        tool_list = []
        
        for tool in mcp_tools:
            name = getattr(tool, 'name', 'unknown')
            description = getattr(tool, 'description', 'No description available')
            parameters = getattr(tool, 'parameters', {})
            
            # Format similar to working lit-lib JSON structure
            tool_entry = {
                "name": name,
                "description": description,
                "parameters": parameters
            }
            tool_list.append(tool_entry)
        
        # Format as JSON-like structure for the prompt (similar to lit-lib)
        import json
        return json.dumps(tool_list, indent=2)
    
    def _format_tools_for_prompt(self, mcp_tools: List[Any]) -> str:
        """Format tools for inclusion in the system prompt."""
        tool_descriptions = []
        
        for tool in mcp_tools:
            name = getattr(tool, 'name', 'unknown')
            description = getattr(tool, 'description', 'No description available')
            tool_descriptions.append(f"- {name}: {description}")
        
        return "\n".join(tool_descriptions)
