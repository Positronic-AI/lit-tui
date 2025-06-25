"""
LIT TUI - A lightweight terminal chat interface for Ollama with MCP integration.

This package provides a beautiful, fast, and extensible terminal user interface
for chatting with Ollama models, featuring Model Context Protocol (MCP) integration
for dynamic tool discovery and execution.

Key Features:
- Fast terminal-native interface built with Textual
- Direct Ollama integration for model communication
- MCP support for extensible tool integration
- Rich text rendering with syntax highlighting
- Keyboard-first navigation optimized for developers
- Cross-platform compatibility

Example usage:
    from lit_tui.app import LitTuiApp
    
    app = LitTuiApp()
    app.run()

Author: Ben Vierck <ben@lit.ai>
License: MIT
"""

__version__ = "0.1.0"
__author__ = "Ben Vierck"
__email__ = "ben@lit.ai"
__license__ = "MIT"

# Import main components for easy access
from .app import LitTuiApp, main

__all__ = ["LitTuiApp", "main", "__version__"]
