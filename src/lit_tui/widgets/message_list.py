"""
Message list widget for displaying chat messages.

This widget handles the display of chat messages with rich formatting,
syntax highlighting, and scrolling capabilities.
"""

import logging
from datetime import datetime
from typing import List, Optional

from rich.console import Console
from rich.markdown import Markdown
from rich.syntax import Syntax
from rich.text import Text
from textual.containers import Vertical
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
        
        # Role styling
        role_display = {
            "user": "👤 You",
            "assistant": "🤖 Assistant", 
            "system": "⚙️ System"
        }.get(self.role, self.role.title())
        
        # Create header
        header = f"[dim]{time_str}[/dim] [bold]{role_display}[/bold]"
        
        # Process content for markdown/code blocks
        processed_content = self._process_content(self.content)
        
        return f"{header}\n{processed_content}\n"
    
    def _process_content(self, content: str) -> str:
        """Process content for rich formatting."""
        # For now, just return the content as-is
        # TODO: Add markdown processing, code highlighting, etc.
        return content


class MessageList(Widget):
    """Widget for displaying a list of chat messages."""
    
    CSS = """
    MessageList {
        background: $background;
        color: $text;
        scrollbar-background: $surface;
        scrollbar-color: $primary;
    }
    
    .message-user {
        background: $accent 10%;
        margin: 1 0;
        padding: 1;
        border-left: thick $accent;
    }
    
    .message-assistant {
        background: $primary 10%;
        margin: 1 0;
        padding: 1;
        border-left: thick $primary;
    }
    
    .message-system {
        background: $warning 10%;
        margin: 1 0;
        padding: 1;
        border-left: thick $warning;
    }
    """
    
    def __init__(self, **kwargs):
        """Initialize message list."""
        super().__init__(**kwargs)
        self.messages: List[MessageWidget] = []
        self.container: Optional[Vertical] = None
    
    def compose(self):
        """Compose the message list."""
        self.container = Vertical()
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
                
                # Auto-scroll to bottom
                self.scroll_end(animate=True)
                
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
