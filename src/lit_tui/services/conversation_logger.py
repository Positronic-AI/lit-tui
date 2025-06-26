"""
Conversation logging for debugging LIT TUI interactions.

This module provides consolidated logging that captures everything 
in a single transcript file for each LLM interaction.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


def log_conversation(
    request_data: Dict[str, Any], 
    response_data: str, 
    source: str = "lit-tui",
    system_prompt_info: Optional[Dict[str, Any]] = None,
    tool_executions: Optional[List[Dict[str, Any]]] = None
) -> None:
    """
    Log complete conversation transcript including all LLM interactions and tool executions.
    
    This is the single source of truth for debugging LLM interactions.
    All tool execution details and system prompt information should be included here.
    """
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        
        # Create logs directory in ~/.lit-tui/logs/
        log_dir = Path.home() / ".lit-tui" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        
        log_file = log_dir / f"transcript-{timestamp}-{source}.log"
        
        with open(log_file, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write(f"LIT TUI CONVERSATION TRANSCRIPT - {source.upper()}\n")
            f.write(f"Timestamp: {datetime.now().isoformat()}\n")
            f.write("=" * 80 + "\n\n")
            
            # System Prompt Information
            if system_prompt_info:
                f.write("SYSTEM PROMPT DETAILS:\n")
                f.write("-" * 40 + "\n")
                f.write(f"Source: {system_prompt_info.get('source', 'unknown')}\n")
                f.write(f"Version: {system_prompt_info.get('version', 'unknown')}\n")
                if 'applied_modules' in system_prompt_info:
                    f.write(f"Applied Modules: {system_prompt_info['applied_modules']}\n")
                if 'recognized_tools' in system_prompt_info:
                    f.write(f"Recognized Tools: {len(system_prompt_info['recognized_tools'])}\n")
                f.write("\n")
            
            # Tool Executions (if any occurred during this conversation)
            if tool_executions:
                f.write("TOOL EXECUTIONS:\n")
                f.write("-" * 40 + "\n")
                for i, tool_exec in enumerate(tool_executions):
                    f.write(f"[{i+1}] Tool: {tool_exec.get('tool_name', 'unknown')}\n")
                    f.write(f"    Arguments: {json.dumps(tool_exec.get('arguments', {}), indent=6)}\n")
                    if tool_exec.get('error'):
                        f.write(f"    ERROR: {tool_exec['error']}\n")
                    else:
                        result = tool_exec.get('result', '')
                        if isinstance(result, dict):
                            f.write(f"    Result: {json.dumps(result, indent=6)}\n")
                        else:
                            result_str = str(result)
                            if len(result_str) > 200:
                                result_str = result_str[:200] + "... [TRUNCATED]"
                            f.write(f"    Result: {result_str}\n")
                    f.write("\n")
                f.write("\n")
            
            # LLM Request
            f.write("REQUEST TO LLM:\n")
            f.write("-" * 40 + "\n")
            f.write(f"Model: {request_data.get('model', 'unknown')}\n")
            
            if 'tools' in request_data:
                tools_info = request_data['tools']
                if isinstance(tools_info, list):
                    # Tools is a list of tool objects
                    f.write(f"Tools Available: {len(tools_info)} tools\n")
                    tool_names = [tool.get('name', 'unnamed') for tool in tools_info]
                    f.write(f"Tool Names: {', '.join(tool_names)}\n")
                else:
                    # Tools is a count (integer)
                    f.write(f"Tools Available: {tools_info} tools\n")
            else:
                f.write("Tools Available: None\n")
            
            f.write("\nMessages:\n")
            for i, msg in enumerate(request_data.get('messages', [])):
                f.write(f"  [{i}] Role: {msg.get('role', 'unknown')}\n")
                content = msg.get('content', '')
                
                # For system messages, ALWAYS log the full content - this is crucial for debugging tools
                if msg.get('role') == 'system':
                    f.write(f"      Content (FULL SYSTEM PROMPT):\n")
                    f.write("      " + "-" * 60 + "\n")
                    # Indent each line of the system prompt for readability
                    for line in content.split('\n'):
                        f.write(f"      {line}\n")
                    f.write("      " + "-" * 60 + "\n")
                else:
                    # For other messages, truncate if very long
                    if len(content) > 500:
                        content = content[:500] + "... [TRUNCATED]"
                    f.write(f"      Content: {content}\n")
                f.write("\n")
            
            # LLM Response
            f.write("RESPONSE FROM LLM:\n")
            f.write("-" * 40 + "\n")
            f.write(str(response_data))  # Ensure it's a string
            f.write("\n\n")
            
            f.write("=" * 80 + "\n")
            f.write("END OF TRANSCRIPT\n")
            f.write("=" * 80 + "\n")
            
        logger.info(f"Conversation transcript logged to: {log_file}")
        
    except Exception as e:
        logger.error(f"Failed to log conversation: {e}")


# Keep this function for backward compatibility, but make it a no-op
# since tool execution details are now included in the main transcript
def log_tool_execution(
    tool_name: str,
    arguments: Dict[str, Any],
    result: Any,
    error: str = None
) -> None:
    """
    DEPRECATED: Tool execution logging is now handled in log_conversation().
    This function is kept for backward compatibility but does nothing.
    """
    # Just log to the main application log that tool execution occurred
    if error:
        logger.error(f"Tool {tool_name} failed: {error}")
    else:
        logger.info(f"Tool {tool_name} executed successfully")


def create_tool_execution_record(
    tool_name: str,
    arguments: Dict[str, Any],
    result: Any = None,
    error: str = None
) -> Dict[str, Any]:
    """
    Helper function to create a tool execution record for inclusion in conversation logs.
    """
    return {
        "tool_name": tool_name,
        "arguments": arguments,
        "result": result,
        "error": error,
        "timestamp": datetime.now().isoformat()
    }
