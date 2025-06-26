"""
Message list widget for displaying chat messages.

This widget handles the display of chat messages with rich formatting,
syntax highlighting, and scrolling capabilities.
"""

import logging
from datetime import datetime
from typing import List, Optional, Union

from rich.console import Console
from rich.markdown import Markdown
from rich.syntax import Syntax
from rich.text import Text
from textual.containers import Vertical, VerticalScroll
from textual.widget import Widget
from textual.widgets import Static


logger = logging.getLogger(__name__)


class MessageWidget(Static):
    """Individual message widget."""
    
    def __init__(self, role: str, content: str, timestamp: Optional[datetime] = None, **kwargs):
        """Initialize message widget."""
        self.role = role
        self.content = content
        self.timestamp = timestamp or datetime.now()
        
        # Create styled content
        styled_content = self._create_styled_content()
        super().__init__(styled_content, **kwargs)
        
        # Apply CSS classes based on role
        self.add_class(f"message-{role}")
    
    def _create_styled_content(self) -> str:
        """Create styled content for the message."""
        # Format timestamp
        time_str = self.timestamp.strftime("%H:%M:%S")
        
        # Simple role display without emojis
        role_display = {
            "user": "You",
            "assistant": "Assistant", 
            "system": "System"
        }.get(self.role, self.role.title())
        
        # Simple header - just timestamp and role
        header = f"{time_str} {role_display}"
        
        # Minimal content processing
        return f"{header}\n{self.content}\n"
    
    
class MessageList(Widget):
    """Widget for displaying a list of chat messages with scrolling."""
    
    # Enable scrolling and focusing
    can_focus = True
    
    CSS = """
    MessageList {
        background: $background;
        color: $text;
        overflow-y: scroll;
        height: 1fr;
    }
    
    .message-user {
        margin: 1 0;
        padding: 0;
    }
    
    .message-assistant {
        margin: 1 0;
        padding: 0;
    }
    
    .message-system {
        margin: 1 0;
        padding: 0;
    }
    """
    
    def __init__(self, config=None, **kwargs):
        """Initialize message list."""
        super().__init__(**kwargs)
        self.messages: List[MessageWidget] = []
        self.container: Optional[Union[Vertical, VerticalScroll]] = None
        self.config = config
    
    def compose(self):
        """Compose the message list."""
        # Use VerticalScroll for proper scrolling
        self.container = VerticalScroll()
        yield self.container
    
    async def add_message(self, role: str, content: str, timestamp: Optional[datetime] = None) -> None:
        """Add a new message to the list."""
        try:
            # Create message widget
            message = MessageWidget(role, content, timestamp)
            self.messages.append(message)
            
            # Add to container
            if self.container:
                await self.container.mount(message)
                
                # Auto-scroll to bottom if enabled in config
                if self.config and self.config.ui.auto_scroll:
                    self.container.scroll_end(animate=True)
                
        except Exception as e:
            logger.error(f"Error adding message: {e}")
    
    async def clear(self) -> None:
        """Clear all messages."""
        try:
            if self.container:
                # Remove all children
                for message in self.messages:
                    await message.remove()
                
            self.messages.clear()
            
        except Exception as e:
            logger.error(f"Error clearing messages: {e}")
    
    def get_messages(self) -> List[MessageWidget]:
        """Get all messages."""
        return self.messages.copy()
    
    async def update_last_message(self, content: str) -> None:
        """Update the content of the last message (useful for streaming)."""
        if self.messages:
            last_message = self.messages[-1]
            last_message.content = content
            last_message.update(last_message._create_styled_content())
    
    async def add_chunk_to_last_message(self, chunk: str) -> None:
        """Add a chunk to the last message (for streaming)."""
        if self.messages:
            last_message = self.messages[-1]
            last_message.content += chunk
            last_message.update(last_message._create_styled_content())
            # Auto-scroll to keep the latest content visible (if enabled)
            if self.config and self.config.ui.auto_scroll:
                self.container.scroll_end(animate=False)
