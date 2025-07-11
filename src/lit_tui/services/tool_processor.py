"""
Tool call processor for LIT TUI - copied from working lit-lib implementation.

This module handles processing tool calls by parsing JSON from LLM text responses
and executing them through MCP, following the exact same pattern as lit-platform.
"""

import asyncio
import json
import logging
import tiktoken
import re
from typing import Dict, List, Any, Optional, Callable
from enum import Enum

from .conversation_logger import log_conversation, create_tool_execution_record
from .model_compatibility import record_tool_result

logger = logging.getLogger(__name__)


def count_tokens_tiktoken(messages):
    """Use tiktoken for accurate token counting"""
    encoding = tiktoken.get_encoding("cl100k_base")  # GPT-4 encoding
    total_tokens = 0
    
    logger.info(f"🧮 Counting tokens for {len(messages)} messages:")
    for i, msg in enumerate(messages):
        content = msg.get('content', '')
        content_tokens = len(encoding.encode(content))
        role_tokens = 4  # Role overhead per message
        msg_total = content_tokens + role_tokens
        total_tokens += msg_total
        
        logger.info(f"   Message {i} ({msg.get('role', 'unknown')}): {content_tokens} content + {role_tokens} role = {msg_total} tokens")
    
    logger.info(f"🧮 Total tokens: {total_tokens}")
    
    # Add small buffer for generation (10-20% overhead is typical)
    final_context = int(total_tokens * 1.2)  # 20% buffer for response generation
    
    logger.info(f"🧮 Final context window: {final_context} (base: {total_tokens} + 20% buffer)")
    return final_context


class StreamState(Enum):
    """States for the tool processing state machine."""
    NORMAL_TOKENS = "normal"           # Regular text streaming
    TOOL_CALL_DETECTED = "detecting"  # Found opening brace, collecting JSON


class ToolCallProcessor:
    """
    Tool processing system following lit-platform approach exactly.
    
    Copied from lit-lib/src/lit/tools/chat_tools.py
    """
    
    def __init__(self, mcp_client, ollama_client):
        """Initialize the tool call processor."""
        self.mcp_client = mcp_client
        self.ollama_client = ollama_client
        
        # Configuration
        self.max_tool_calls = 20
        
        # Reset state
        self.tool_call_count = 0
        self.state = StreamState.NORMAL_TOKENS
        self.tool_call_buffer = ""
        self.brace_count = 0
        
        # Track tool executions for this conversation
        self.tool_executions = []
        self.current_model = None  # Will be set during processing
        
    def reset_for_new_conversation(self):
        """Reset state for a new conversation."""
        self.tool_call_count = 0
        self.tool_executions = []
        self._reset_state()
        
    def _reset_state(self):
        """Reset the state machine."""
        self.state = StreamState.NORMAL_TOKENS
        self.tool_call_buffer = ""
        self.brace_count = 0
        # Note: we don't reset tool_executions here as they should persist for the full conversation
        
    async def process_with_tools(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],  # Ignored - tools are in system prompt
        stream_callback: Optional[Callable[[str], None]] = None,
        max_iterations: int = 20,
        system_prompt_info: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Process a chat completion with tools support (exact lit-platform approach).
        """
        logger.info(f"=== STARTING RECURSIVE TOOL PROCESSING (max tools: {max_iterations}) ===")
        
        # Store model for compatibility tracking
        self.current_model = model
        
        current_messages = messages.copy()
        total_response = ""
        model_had_successful_tool_execution = False
        
        try:
            while self.tool_call_count < max_iterations:
                logger.info(f"TOOL CYCLE #{self.tool_call_count + 1}: Starting stream processing")
                
                # Reset state for this cycle
                self._reset_state()
                tool_executed_this_cycle = False
                
                # Calculate dynamic context window size
                token_count = count_tokens_tiktoken(current_messages)
                logger.info(f"🔢 Token count for {len(current_messages)} messages: {token_count}")
                logger.info(f"📋 Message breakdown:")
                for i, msg in enumerate(current_messages):
                    content_preview = msg.get('content', '')[:100] + '...' if len(msg.get('content', '')) > 100 else msg.get('content', '')
                    logger.info(f"   [{i}] {msg.get('role', 'unknown')}: {len(msg.get('content', ''))} chars - {content_preview}")
                
                # Log the request
                request_data = {
                    "model": model,
                    "messages": current_messages,
                    "options": {"temperature": 0.0, "num_ctx": token_count},
                    "tools": len(self.mcp_client.get_available_tools()) if self.mcp_client else 0
                }
                
                logger.info(f"🚀 Calling Ollama with num_ctx={token_count}")
                
                # Stream from the model (no tools parameter)
                full_response = ""
                async for chunk in self.ollama_client.chat_completion(
                    model=model,
                    messages=current_messages,
                    stream=True,
                    options={"temperature": 0.0, "num_ctx": token_count}
                ):
                    if chunk:  # Only process non-empty chunks
                        full_response += chunk
                        
                        # Process token through state machine
                        result = await self._process_token(chunk, stream_callback)
                        
                        if result["action"] == "continue":
                            # Normal token, continue streaming
                            continue
                        elif result["action"] == "tool_detected":
                            # Tool call detected and executed
                            tool_result = result["tool_result"]
                            tool_call_json = result["tool_call_json"]
                            
                            # Add tool call and result to conversation
                            current_messages.append({
                                "role": "assistant", 
                                "content": tool_call_json
                            })
                            
                            # Create monitoring prompt like lit-platform
                            monitoring_prompt = f"Tool result: {tool_result}\n\nREMINDER: Your original task was: \"{messages[-1]['content']}\"\n\nYou've executed {self.tool_call_count} tool call{'s' if self.tool_call_count != 1 else ''}. Continue if you're making progress toward your original goal."
                            
                            current_messages.append({
                                "role": "user", 
                                "content": monitoring_prompt
                            })
                            
                            # Add to total response
                            total_response += tool_call_json
                            result_msg = f"\n\nTool result: {tool_result}\n\n"
                            total_response += result_msg
                            
                            # Send result to stream
                            if stream_callback:
                                # Handle both sync and async callbacks
                                if asyncio.iscoroutinefunction(stream_callback):
                                    await stream_callback(result_msg)
                                else:
                                    stream_callback(result_msg)
                            
                            tool_executed_this_cycle = True
                            self.tool_call_count += 1
                            break  # Start new cycle
                
                # Log the response with all tool execution data
                log_conversation(
                    request_data, 
                    full_response, 
                    "tool-processor",
                    system_prompt_info=system_prompt_info,
                    tool_executions=self.tool_executions.copy()
                )
                
                # If no tool was executed this cycle, we're done
                if not tool_executed_this_cycle:
                    total_response += full_response
                    break
                    
            if self.tool_call_count >= max_iterations:
                logger.warning(f"Reached max tool calls ({max_iterations})")
                
        except Exception as e:
            logger.error(f"Error in tool processing: {e}")
            if stream_callback:
                error_msg = f"\n❌ Tool processing error: {e}\n"
                # Handle both sync and async callbacks
                if asyncio.iscoroutinefunction(stream_callback):
                    await stream_callback(error_msg)
                else:
                    stream_callback(error_msg)
            total_response += f"\n\nError: {e}"
            
        return total_response
    
    async def _process_token(self, token: str, stream_callback: Optional[Callable[[str], None]]) -> Dict[str, Any]:
        """
        Process a single token through the state machine.
        
        Copied from lit-lib approach.
        """
        logger.debug(f"PROCESS TOKEN: '{token}' (state={self.state})")
        
        if self.state == StreamState.NORMAL_TOKENS:
            return await self._handle_normal_token(token, stream_callback)
        elif self.state == StreamState.TOOL_CALL_DETECTED:
            return await self._handle_tool_collection_token(token, stream_callback)
        else:
            # Unknown state, treat as normal
            logger.warning(f"Unknown state {self.state}, treating as normal")
            self.state = StreamState.NORMAL_TOKENS
            return await self._handle_normal_token(token, stream_callback)
    
    async def _handle_normal_token(self, token, stream_callback):
        """Handle tokens in normal streaming mode."""
        # Check if this might be the start of a tool call
        if "{" in token:
            logger.info("TOOL DETECTION: Found opening brace, starting tool call collection")
            self.state = StreamState.TOOL_CALL_DETECTED
            self.tool_call_buffer = token
            # Count actual braces in the token to set initial count
            self.brace_count = token.count("{") - token.count("}")
            
            # Send the brace to the stream for now
            if stream_callback:
                # Handle both sync and async callbacks
                if asyncio.iscoroutinefunction(stream_callback):
                    await stream_callback(token)
                else:
                    stream_callback(token)
            
            return {"action": "continue"}
        else:
            # Normal token, send to stream
            if stream_callback:
                # Handle both sync and async callbacks
                if asyncio.iscoroutinefunction(stream_callback):
                    await stream_callback(token)
                else:
                    stream_callback(token)
            
            return {"action": "continue"}
    
    async def _handle_tool_collection_token(self, token, stream_callback):
        """Handle tokens while collecting a potential tool call."""
        self.tool_call_buffer += token
        
        # Count braces to determine when JSON is complete
        for char in token:
            if char == "{":
                self.brace_count += 1
            elif char == "}":
                self.brace_count -= 1
        
        logger.debug(f"TOOL COLLECTION: '{token}' -> buffer='{self.tool_call_buffer}' brace_count={self.brace_count}")
        
        # If braces are balanced, we might have a complete JSON object
        if self.brace_count == 0:
            logger.info(f"TOOL VALIDATION: Balanced braces detected, validating JSON: '{self.tool_call_buffer}'")
            
            # Strip out <think>...</think> blocks before validation
            cleaned_buffer = re.sub(r'<think>.*?</think>', '', self.tool_call_buffer, flags=re.DOTALL).strip()
            
            # Try to parse and validate as tool call (using lit-platform's method)
            tool_call = self._extract_tool_call(cleaned_buffer)
            
            if tool_call:
                # Valid tool call detected
                logger.info(f"TOOL EXECUTION #{self.tool_call_count + 1}: {tool_call['tool']}")
                
                # Execute the tool
                try:
                    # Since we're in an async context, we can await directly
                    tool_result = await self._execute_tool_call_async_safe(tool_call)
                    
                    # Reset state and return result
                    self.state = StreamState.NORMAL_TOKENS
                    
                    return {
                        "action": "tool_detected",
                        "tool_result": tool_result,
                        "tool_call_json": cleaned_buffer
                    }
                    
                except Exception as e:
                    logger.error(f"Tool execution failed: {e}")
                    # Continue as normal text on error
                    self.state = StreamState.NORMAL_TOKENS
                    if stream_callback:
                        # Handle both sync and async callbacks
                        if asyncio.iscoroutinefunction(stream_callback):
                            await stream_callback(self.tool_call_buffer)
                        else:
                            stream_callback(self.tool_call_buffer)
                    return {"action": "continue"}
            else:
                # Not a valid tool call, treat as normal text
                logger.info("TOOL VALIDATION: Not a valid tool call, continuing as normal text")
                self.state = StreamState.NORMAL_TOKENS
                if stream_callback:
                    # Handle both sync and async callbacks
                    if asyncio.iscoroutinefunction(stream_callback):
                        await stream_callback(self.tool_call_buffer)
                    else:
                        stream_callback(self.tool_call_buffer)
                return {"action": "continue"}
        else:
            # Still collecting, send token to stream
            if stream_callback:
                # Handle both sync and async callbacks
                if asyncio.iscoroutinefunction(stream_callback):
                    await stream_callback(token)
                else:
                    stream_callback(token)
            return {"action": "continue"}
    
    def _extract_tool_call(self, text: str) -> Optional[Dict[str, Any]]:
        """Extract tool call from text, copied from lit-platform approach."""
        try:
            # Strip out <think>...</think> blocks before processing
            text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
            
            # Simple check for a JSON tool call format
            if not (text.strip().startswith("{") and text.strip().endswith("}")):
                return None
            
            # Try to parse the JSON
            data = json.loads(text)
            
            # Check if it has the required fields
            if "tool" in data and "arguments" in data:
                # Extract server and tool names
                if "." in data["tool"]:
                    server_name, tool_name = data["tool"].split(".", 1)
                else:
                    # If no server specified, try to find the first available server
                    available_tools = self.mcp_client.get_available_tools()
                    if available_tools:
                        server_name = available_tools[0].server_name
                        tool_name = data["tool"]
                    else:
                        logger.warning("No MCP servers configured and no server specified in tool call")
                        return None
                
                # Transform arguments if needed - map file_path to path
                arguments = data["arguments"].copy()
                if "file_path" in arguments and "path" not in arguments:
                    arguments["path"] = arguments.pop("file_path")
                
                return {
                    "server": server_name,
                    "tool": tool_name,
                    "arguments": arguments
                }
        except Exception as e:
            logger.error(f"Error extracting tool call: {e}")
        
        return None
    
    async def _execute_tool_call_async_safe(self, tool_call: Dict[str, Any]) -> str:
        """Execute tool call asynchronously - safe for use in async context."""
        return await self._execute_tool_call_async(tool_call)
    
    async def _execute_tool_call_async(self, tool_call: Dict[str, Any]) -> str:
        """Execute tool call through MCP."""
        server_name = tool_call["server"]
        tool_name = tool_call["tool"]
        arguments = tool_call["arguments"]
        
        logger.info(f"🚀 Executing {tool_name} on server {server_name} with args: {arguments}")
        
        try:
            # Execute the tool through MCP
            result = await self.mcp_client.execute_tool(server_name, tool_name, arguments)
            logger.info(f"✅ Tool execution successful")
            
            # Record successful tool execution for model compatibility learning
            if self.current_model:
                record_tool_result(self.current_model, True, "successful_tool_execution")
            
            # Record tool execution for consolidated logging
            tool_record = create_tool_execution_record(
                f"{server_name}.{tool_name}", 
                arguments, 
                result
            )
            self.tool_executions.append(tool_record)
            
            # Format the result
            if isinstance(result, dict):
                return json.dumps(result, indent=2)
            else:
                return str(result)
                
        except Exception as e:
            error_msg = f"Error executing tool {server_name}.{tool_name}: {e}"
            logger.error(error_msg)
            
            # Record failed tool execution for model compatibility learning
            if self.current_model:
                record_tool_result(self.current_model, False, str(e))
            
            # Record failed tool execution for consolidated logging
            tool_record = create_tool_execution_record(
                f"{server_name}.{tool_name}", 
                arguments, 
                None, 
                error_msg
            )
            self.tool_executions.append(tool_record)
            
            return error_msg
