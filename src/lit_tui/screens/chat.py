"""
Main chat screen for LIT TUI.

This module contains the primary chat interface including message display,
input handling, and session management.
"""

import asyncio
import logging
from typing import Optional

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Input, Static

from ..config import Config
from ..services import OllamaClient, StorageService, MCPClient
from ..services.storage import ChatMessage
from ..services.prompt_composer import PromptComposer
from ..services.tool_processor import ToolCallProcessor
from ..widgets import MessageList, Sidebar


logger = logging.getLogger(__name__)


class ChatScreen(Screen):
    """Main chat screen."""
    
    CSS = """
    ChatScreen {
        layout: vertical;
    }
    
    .main-content {
        layout: horizontal;
        height: 1fr;
    }
    
    .sidebar {
        width: 25%;
    }
    
    .main-area {
        width: 75%;
        layout: vertical;
    }
    
    .chat-area {
        height: 1fr;
    }
    
    .input-area {
        height: auto;
        padding: 1;
    }
    
    .chat-input {
        width: 1fr;
    }
    
    .status-bar {
        height: 1;
        text-align: left;
        dock: bottom;
    }
    """
    
    def __init__(self, config: Config, **kwargs):
        """Initialize chat screen."""
        super().__init__(**kwargs)
        self.config = config
        self.ollama_client = OllamaClient(config)
        self.storage_service = StorageService(config)
        self.mcp_client = MCPClient(config)
        self.prompt_composer = PromptComposer(config)
        self.tool_processor = ToolCallProcessor(self.mcp_client, self.ollama_client)
        self.current_session = None
        self.current_model: Optional[str] = None
        self.is_generating = False
        
    def compose(self) -> ComposeResult:
        """Compose the chat screen layout."""
        # Main content area with sidebar and chat
        with Horizontal(classes="main-content"):
            # Sidebar for session management
            with Vertical(classes="sidebar"):
                yield Sidebar(self.config)
                
            # Main chat area
            with Vertical(classes="main-area"):
                # Chat messages area
                with Vertical(classes="chat-area"):
                    yield MessageList(config=self.config, id="messages")
                    
                # Input area
                with Vertical(classes="input-area"):
                    yield Input(
                        placeholder="Type your message here... (Enter to send)",
                        id="chat_input",
                        classes="chat-input"
                    )
                    
        # Status bar at the very bottom of the window
        yield Static("", id="status", classes="status-bar")
    
    async def on_mount(self) -> None:
        """Called when screen is mounted."""
        # Initialize services
        await self._initialize_services()
        
        # Focus the input field
        self.query_one("#chat_input", Input).focus()
        
        # Start with a new session
        await self.new_chat()
        
    async def _initialize_services(self) -> None:
        """Initialize Ollama and MCP services."""
        self.update_status("Checking Ollama connection...")
        
        try:
            # Initialize Ollama
            is_available = await self.ollama_client.is_available()
            if not is_available:
                self.update_status("")
                self.notify_via_sidebar("Ollama not available - check if server is running", "warning")
                return
            
            # Load available models and restore last model
            models = await self.ollama_client.get_models()
            if not models:
                self.update_status("")
                self.notify_via_sidebar("No models found - please pull a model in Ollama", "warning")
                return
            
            # Try to restore last used model
            last_model = await self.storage_service.load_last_model()
            if last_model and any(model.name == last_model for model in models):
                self.current_model = last_model
                logger.info(f"🔄 Restored last model: {last_model}")
            else:
                # Use first available model as default
                self.current_model = models[0].name
                logger.info(f"📋 Using default model: {self.current_model}")
                
            # Update sidebar model display
            try:
                sidebar = self.query_one(Sidebar)
                sidebar.update_model_display(self.current_model)
            except Exception as e:
                logger.warning(f"Could not update model display: {e}")
            
            self.update_status("Initializing MCP tools...")
            
            # Initialize MCP client
            mcp_success = await self.mcp_client.initialize()
            if mcp_success:
                tools = self.mcp_client.get_available_tools()
                tool_count = len(tools)
                self.update_status("")
                self.notify_via_sidebar(f"Connected with {tool_count} MCP tools", "success")
            else:
                self.update_status("")
                self.notify_via_sidebar(f"Connected to Ollama - using {self.current_model}", "success")
            
        except Exception as e:
            logger.error(f"Failed to initialize services: {e}")
            self.update_status("")
            self.notify_via_sidebar(f"Service initialization failed: {e}", "error")
    
    @on(Input.Submitted, "#chat_input")
    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle message input submission."""
        if not self.is_generating and event.value.strip():
            self.send_message(event.value.strip())
            event.input.value = ""
    
    @work(exclusive=True)
    async def send_message(self, message: str) -> None:
        """Send a message and get response."""
        if self.is_generating:
            return
            
        try:
            self.is_generating = True
            self.update_status("Sending message...")
            
            # Add user message to chat
            message_list = self.query_one("#messages", MessageList)
            await message_list.add_message("user", message)
            
            # Add to session and save (this implements the elegant pattern)
            if self.current_session:
                # Check if this will be the first save
                is_first_save = not self.current_session.is_saved
                
                user_msg = ChatMessage(role="user", content=message, model=self.current_model)
                self.current_session.add_message(user_msg)
                
                # Save session to disk (first user message triggers first save)
                await self.storage_service.save_session(self.current_session)
                
                # If this was the first save, refresh sidebar to show the new session
                if is_first_save:
                    sidebar = self.query_one(Sidebar)
                    await sidebar.load_sessions()
                    # Enable delete button since session is now saved
                    sidebar.update_delete_button_state(session_is_saved=True)
            
            # Start generating response
            self.update_status("🤖 Generating response...")
            self.generate_response(message)
            
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            self.notify_via_sidebar(f"Error: {e}", "error")
        finally:
            self.is_generating = False
            self.update_status("")
    
    @work(exclusive=True)
    async def generate_response(self, message: str) -> None:
        """Generate response from Ollama with streaming and tool support."""
        try:
            # Reset tool processor for this conversation
            if self.tool_processor:
                self.tool_processor.reset_for_new_conversation()
                
            if not self.current_model:
                await self._handle_no_model()
                return
            
            # Prepare messages for Ollama
            messages = []
            if self.current_session:
                # Convert session messages to Ollama format
                for msg in self.current_session.messages:
                    messages.append({
                        "role": msg.role,
                        "content": msg.content
                    })
            
            # Get available tools
            available_tools = self.mcp_client.get_available_tools() if self.mcp_client else []
            
            # Compose intelligent system prompt - we need this for tool usage
            # Check if we already have a system message
            has_system_message = any(msg.get("role") == "system" for msg in messages)
            
            if not has_system_message:
                logger.info(f"🧠 Composing system prompt with {len(available_tools)} tools")
                for tool in available_tools[:3]:  # Log first 3 tools
                    logger.info(f"   Tool: {tool.name} - {tool.description}")
                
                prompt_response = self.prompt_composer.compose_system_prompt(
                    user_message=message,
                    mcp_tools=available_tools,  # Pass actual MCPTool objects
                    messages=messages,
                    context={"model": self.current_model}
                )
                
                logger.info(f"📝 System prompt length: {len(prompt_response['system_prompt'])} chars")
                logger.info(f"📝 System prompt preview: {prompt_response['system_prompt'][:300]}...")
                
                # Store system prompt info for logging (remove separate file logging)
                system_prompt_info = prompt_response.copy()
                
                system_msg = {
                    "role": "system",
                    "content": prompt_response["system_prompt"]
                }
                messages.insert(0, system_msg)
                
                # Log prompt composition results
                if prompt_response.get("fallback"):
                    logger.info("📝 Using fallback system prompt")
                else:
                    logger.info(f"✅ Enhanced system prompt generated")
                    if prompt_response.get("applied_modules"):
                        logger.info(f"Applied modules: {prompt_response['applied_modules']}")
            else:
                logger.info("💬 System message already exists, skipping system prompt generation")
                system_prompt_info = None
            
            # Start streaming response
            message_list = self.query_one("#messages", MessageList)
            
            # Add initial assistant message
            await message_list.add_message("assistant", "")
            
            # Create unified streaming callback that updates MessageList directly
            async def unified_stream_callback(chunk: str) -> None:
                """Unified streaming callback for both tool and non-tool conversations."""
                if chunk:
                    await message_list.add_chunk_to_last_message(chunk)
                    
            # Process with tools if available (lit-platform approach)
            if available_tools:
                # Check model compatibility before processing with tools
                from ..services.model_compatibility import supports_tools, suggest_alternative_model
                
                if not supports_tools(self.current_model):
                    # Model doesn't support tools - show helpful error
                    logger.warning(f"❌ Model {self.current_model} does not support tool calling")
                    
                    # Get available models for suggestion
                    available_model_names = [model["name"] for model in await self.ollama_client.list_models()]
                    suggested_model = suggest_alternative_model(self.current_model, available_model_names)
                    
                    error_message = f"❌ **Model Compatibility Issue**\n\n"
                    error_message += f"The model `{self.current_model}` does not support tool calling. "
                    error_message += f"I have {len(available_tools)} tools available (file operations, etc.) but this model cannot use them.\n\n"
                    
                    if suggested_model:
                        error_message += f"💡 **Suggestion**: Switch to `{suggested_model}` or another compatible model.\n\n"
                        error_message += f"**Compatible models include**: qwen3:latest, llama3.1:latest, mistral:latest\n"
                        error_message += f"**Incompatible models**: codellama (all versions), codegemma, starcoder\n\n"
                    
                    error_message += f"You can change the model using the sidebar or try your request with a different model."
                    
                    # Update the message directly
                    await message_list.update_last_message(error_message)
                    return
                
                logger.info(f"🔧 Processing with {len(available_tools)} tools available (system prompt approach)")
                response_content = await self.tool_processor.process_with_tools(
                    model=self.current_model,
                    messages=messages,
                    tools=[],  # Don't pass tools to Ollama - they're in the system prompt
                    stream_callback=unified_stream_callback,
                    system_prompt_info=system_prompt_info
                )
            else:
                # No tools, use standard completion with the same streaming approach
                logger.info("💬 Processing without tools")
                response_content = ""
                async for chunk in self.ollama_client.chat_completion(
                    model=self.current_model,
                    messages=messages,
                    stream=True
                ):
                    response_content += chunk
                    if chunk:
                        await unified_stream_callback(chunk)
            
            # Save complete response to session
            if self.current_session and response_content:
                assistant_msg = ChatMessage(
                    role="assistant", 
                    content=response_content,
                    model=self.current_model
                )
                self.current_session.add_message(assistant_msg)
                await self.storage_service.save_session(self.current_session)
            
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            message_list = self.query_one("#messages", MessageList)
            await message_list.add_message("assistant", f"Error: {e}")
    
    async def _handle_no_model(self) -> None:
        """Handle case where no model is available."""
        message_list = self.query_one("#messages", MessageList)
        error_msg = ("No Ollama model available. Please:\n"
                    "1. Make sure Ollama is running\n"
                    "2. Pull a model (e.g., `ollama pull llama2`)\n"
                    "3. Restart lit-tui")
        await message_list.add_message("assistant", error_msg)
    
    def update_status(self, message: str) -> None:
        """Update status bar."""
        status = self.query_one("#status", Static)
        status.update(message)
        
    def notify_via_sidebar(self, message: str, severity: str = "info") -> None:
        """Send notification through sidebar instead of built-in notify."""
        try:
            sidebar = self.query_one(Sidebar)
            sidebar.show_notification(message, severity)
        except Exception as e:
            logger.error(f"Error sending notification via sidebar: {e}")
            # Fallback to built-in notification
            self.notify(message, severity=severity)
    
    async def new_chat(self) -> None:
        """Start a new chat session."""
        try:
            # Create new session (not saved to disk yet)
            self.current_session = await self.storage_service.create_session(
                model=self.current_model
            )
            
            # Clear messages - start with clean empty chat
            message_list = self.query_one("#messages", MessageList)
            await message_list.clear()
            
            # No welcome message - clean start like lit-server and lit-desktop
            
            # Refresh the sidebar session list (will only show saved sessions)
            sidebar = self.query_one(Sidebar)
            await sidebar.load_sessions()
            
            # Update delete button state - disable since this session is not saved yet
            sidebar.update_delete_button_state(session_is_saved=False)
            
            self.notify_via_sidebar("Started new chat session", "success")
            
        except Exception as e:
            logger.error(f"Error creating new session: {e}")
            self.notify_via_sidebar(f"Error creating session: {e}", "error")
    
    async def load_session(self, session_id: str) -> None:
        """Load a specific session by ID."""
        try:
            session = await self.storage_service.load_session(session_id)
            if not session:
                self.notify_via_sidebar(f"Session not found: {session_id}", "error")
                return
            
            self.current_session = session
            
            # Clear and reload messages
            message_list = self.query_one("#messages", MessageList)
            await message_list.clear()
            
            # Add all messages from the session
            for msg in session.messages:
                await message_list.add_message(msg.role, msg.content, msg.timestamp)
            
            # Update model if different
            if session.model and session.model != self.current_model:
                await self.change_model(session.model)
            
            # Enable delete button since loaded sessions are always saved
            sidebar = self.query_one(Sidebar)
            sidebar.update_delete_button_state(session_is_saved=True)
            
        except Exception as e:
            logger.error(f"Error loading session {session_id}: {e}")
            self.notify_via_sidebar(f"Error loading session: {e}", "error")
    
    async def open_session(self) -> None:
        """Open existing session."""
        # TODO: Implement session selection dialog
        self.notify_via_sidebar("Session selection coming soon!", "info")
    
    async def change_model(self, model_name: str) -> None:
        """Change the current model."""
        try:
            # Verify model is available
            models = await self.ollama_client.get_models()
            if not any(m.name == model_name for m in models):
                self.notify_via_sidebar(f"Model {model_name} not found", "error")
                return
            
            self.current_model = model_name
            
            # Save as last used model
            await self.storage_service.save_last_model(model_name)
            
            self.notify_via_sidebar(f"Switched to model: {model_name}", "success")
            
            # Update sidebar model display
            try:
                sidebar = self.query_one(Sidebar)
                sidebar.update_model_display(self.current_model)
            except Exception as e:
                logger.warning(f"Could not update sidebar model display: {e}")
            
            # Update session model
            if self.current_session:
                self.current_session.model = model_name
                await self.storage_service.save_session(self.current_session)
                
        except Exception as e:
            logger.error(f"Error changing model: {e}")
            self.notify_via_sidebar(f"Error changing model: {e}", "error")
    
    async def get_mcp_status(self) -> str:
        """Get MCP status for display."""
        try:
            health = await self.mcp_client.health_check()
            if not health["enabled"]:
                return "MCP: Disabled"
            
            running_servers = sum(1 for server in health["servers"].values() if server["running"])
            total_servers = len(health["servers"])
            total_tools = health["total_tools"]
            
            if running_servers == 0:
                return "MCP: No servers"
            elif total_tools == 0:
                return f"MCP: {running_servers} servers, no tools"
            else:
                return f"MCP: {total_tools} tools from {running_servers} servers"
                
        except Exception as e:
            logger.error(f"Error getting MCP status: {e}")
            return "MCP: Error"
    
    async def call_mcp_tool(self, tool_name: str, arguments: dict) -> Optional[str]:
        """Call an MCP tool and return the result."""
        try:
            self.update_status(f"🔧 Calling tool: {tool_name}")
            
            result = await self.mcp_client.call_tool(tool_name, arguments)
            
            if result:
                if "error" in result:
                    error_msg = f"Tool error: {result['error']}"
                    logger.error(error_msg)
                    return error_msg
                else:
                    # Extract content from result
                    if "content" in result:
                        if isinstance(result["content"], list):
                            # Handle multiple content items
                            content_parts = []
                            for item in result["content"]:
                                if isinstance(item, dict) and "text" in item:
                                    content_parts.append(item["text"])
                            return "\n".join(content_parts)
                        else:
                            return str(result["content"])
                    else:
                        return str(result)
            else:
                return f"Tool {tool_name} returned no result"
                
        except Exception as e:
            error_msg = f"Error calling tool {tool_name}: {e}"
            logger.error(error_msg)
            return error_msg
        finally:
            self.update_status("Ready")
