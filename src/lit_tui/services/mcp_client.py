"""
MCP (Model Context Protocol) client service for LIT TUI.

This module provides standalone MCP integration without dependencies on lit-lib,
implementing direct MCP server connections and tool discovery.
"""

import asyncio
import json
import logging
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any, AsyncIterator
import signal
import os

from ..config import Config, MCPServerConfig


logger = logging.getLogger(__name__)


class MCPServerProcess:
    """Manages a single MCP server process."""
    
    def __init__(self, config: MCPServerConfig):
        self.config = config
        self.process: Optional[subprocess.Popen] = None
        self.is_running = False
        
    async def start(self) -> bool:
        """Start the MCP server process."""
        try:
            # Prepare environment
            env = os.environ.copy()
            env.update(self.config.env)
            
            # Start the process
            self.process = subprocess.Popen(
                [self.config.command] + self.config.args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                text=True
            )
            
            # Give it a moment to start
            await asyncio.sleep(0.5)
            
            # Check if it's still running
            if self.process.poll() is None:
                self.is_running = True
                logger.info(f"Started MCP server: {self.config.name}")
                return True
            else:
                logger.error(f"MCP server {self.config.name} failed to start")
                return False
                
        except Exception as e:
            logger.error(f"Failed to start MCP server {self.config.name}: {e}")
            return False
    
    async def stop(self) -> None:
        """Stop the MCP server process."""
        if self.process and self.is_running:
            try:
                self.process.terminate()
                
                # Wait for graceful shutdown
                try:
                    await asyncio.wait_for(
                        asyncio.create_task(self._wait_for_process()),
                        timeout=5.0
                    )
                except asyncio.TimeoutError:
                    # Force kill if it doesn't shut down gracefully
                    self.process.kill()
                    await self._wait_for_process()
                
                self.is_running = False
                logger.info(f"Stopped MCP server: {self.config.name}")
                
            except Exception as e:
                logger.error(f"Error stopping MCP server {self.config.name}: {e}")
    
    async def _wait_for_process(self) -> None:
        """Wait for process to terminate."""
        if self.process:
            while self.process.poll() is None:
                await asyncio.sleep(0.1)
    
    async def send_request(self, request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Send a JSON-RPC request to the MCP server."""
        if not self.is_running or not self.process:
            return None
        
        try:
            # Send request
            request_json = json.dumps(request) + '\n'
            self.process.stdin.write(request_json)
            self.process.stdin.flush()
            
            # Read response (with timeout)
            response_line = await asyncio.wait_for(
                self._read_line(),
                timeout=self.config.timeout
            )
            
            if response_line:
                return json.loads(response_line.strip())
            
        except asyncio.TimeoutError:
            logger.warning(f"MCP server {self.config.name} request timeout")
        except Exception as e:
            logger.error(f"MCP request error for {self.config.name}: {e}")
        
        return None
    
    async def _read_line(self) -> Optional[str]:
        """Read a line from the process stdout."""
        if not self.process:
            return None
        
        # This is a simplified implementation
        # In a real implementation, you'd want proper async I/O
        try:
            line = self.process.stdout.readline()
            return line if line else None
        except Exception:
            return None


class MCPTool:
    """Represents an MCP tool."""
    
    def __init__(self, name: str, description: str = "", parameters: Optional[Dict] = None):
        self.name = name
        self.description = description
        self.parameters = parameters or {}
        self.server_name: Optional[str] = None


class MCPClient:
    """Client for managing MCP servers and tools."""
    
    def __init__(self, config: Config):
        """Initialize MCP client."""
        self.config = config
        self.servers: Dict[str, MCPServerProcess] = {}
        self.tools: Dict[str, MCPTool] = {}
        self.request_id = 0
        
    async def initialize(self) -> bool:
        """Initialize MCP client and start configured servers."""
        if not self.config.mcp.enabled:
            logger.info("MCP integration is disabled")
            return True
        
        success_count = 0
        
        for server_config in self.config.mcp.servers:
            server = MCPServerProcess(server_config)
            self.servers[server_config.name] = server
            
            if await server.start():
                success_count += 1
                # Discover tools from this server
                await self._discover_tools(server_config.name)
        
        logger.info(f"Started {success_count}/{len(self.config.mcp.servers)} MCP servers")
        return success_count > 0
    
    async def shutdown(self) -> None:
        """Shutdown all MCP servers."""
        for server in self.servers.values():
            await server.stop()
        
        self.servers.clear()
        self.tools.clear()
        logger.info("Shut down all MCP servers")
    
    async def _discover_tools(self, server_name: str) -> None:
        """Discover available tools from an MCP server."""
        server = self.servers.get(server_name)
        if not server:
            return
        
        try:
            # Send tools/list request
            request = {
                "jsonrpc": "2.0",
                "id": self._next_request_id(),
                "method": "tools/list",
                "params": {}
            }
            
            response = await server.send_request(request)
            
            if response and "result" in response:
                tools_data = response["result"].get("tools", [])
                
                for tool_data in tools_data:
                    tool = MCPTool(
                        name=tool_data.get("name", ""),
                        description=tool_data.get("description", ""),
                        parameters=tool_data.get("inputSchema", {})
                    )
                    tool.server_name = server_name
                    
                    # Store with server prefix to avoid conflicts
                    tool_key = f"{server_name}.{tool.name}"
                    self.tools[tool_key] = tool
                
                logger.info(f"Discovered {len(tools_data)} tools from {server_name}")
        
        except Exception as e:
            logger.error(f"Failed to discover tools from {server_name}: {e}")
    
    def _next_request_id(self) -> int:
        """Get next request ID."""
        self.request_id += 1
        return self.request_id
    
    async def call_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        server_name: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Call an MCP tool."""
        # Find the tool
        tool_key = f"{server_name}.{tool_name}" if server_name else tool_name
        
        # Try exact match first
        tool = self.tools.get(tool_key)
        if not tool:
            # Try to find by tool name across servers
            for key, t in self.tools.items():
                if t.name == tool_name:
                    tool = t
                    break
        
        if not tool or not tool.server_name:
            logger.warning(f"Tool not found: {tool_name}")
            return None
        
        server = self.servers.get(tool.server_name)
        if not server or not server.is_running:
            logger.warning(f"Server not running for tool: {tool_name}")
            return None
        
        try:
            # Send tools/call request
            request = {
                "jsonrpc": "2.0",
                "id": self._next_request_id(),
                "method": "tools/call",
                "params": {
                    "name": tool.name,
                    "arguments": arguments
                }
            }
            
            response = await server.send_request(request)
            
            if response and "result" in response:
                return response["result"]
            elif response and "error" in response:
                logger.error(f"Tool call error: {response['error']}")
                return {"error": response["error"]}
        
        except Exception as e:
            logger.error(f"Failed to call tool {tool_name}: {e}")
            return {"error": str(e)}
        
        return None
    
    def get_available_tools(self) -> List[MCPTool]:
        """Get list of all available tools."""
        return list(self.tools.values())
    
    def get_tools_by_server(self, server_name: str) -> List[MCPTool]:
        """Get tools from a specific server."""
        return [tool for tool in self.tools.values() if tool.server_name == server_name]
    
    async def health_check(self) -> Dict[str, Any]:
        """Get health status of all MCP servers."""
        health_info = {
            "enabled": self.config.mcp.enabled,
            "servers": {},
            "total_tools": len(self.tools)
        }
        
        for server_name, server in self.servers.items():
            health_info["servers"][server_name] = {
                "running": server.is_running,
                "tools": len(self.get_tools_by_server(server_name))
            }
        
        return health_info
    
    def format_tool_for_llm(self, tool: MCPTool) -> Dict[str, Any]:
        """Format a tool definition for LLM function calling."""
        return {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters
            }
        }
    
    def get_tools_for_llm(self) -> List[Dict[str, Any]]:
        """Get all tools formatted for LLM function calling."""
        return [self.format_tool_for_llm(tool) for tool in self.tools.values()]


async def create_example_mcp_config() -> List[MCPServerConfig]:
    """Create example MCP server configurations."""
    examples = []
    
    # Check if common MCP servers might be available
    common_servers = [
        {
            "name": "filesystem",
            "command": "mcp-server-filesystem",
            "args": ["--root", str(Path.home())],
            "description": "File system operations"
        },
        {
            "name": "git",
            "command": "mcp-server-git",
            "args": [],
            "description": "Git repository operations"
        },
        {
            "name": "sqlite",
            "command": "mcp-server-sqlite",
            "args": [],
            "description": "SQLite database operations"
        }
    ]
    
    for server_info in common_servers:
        # Check if the command exists
        try:
            result = subprocess.run(
                ["which", server_info["command"]], 
                capture_output=True, 
                text=True
            )
            if result.returncode == 0:
                examples.append(MCPServerConfig(**server_info))
        except Exception:
            pass  # Command not found
    
    return examples
