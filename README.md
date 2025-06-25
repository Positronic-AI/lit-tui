# LIT TUI

A lightweight, fast, and beautiful terminal chat interface for Ollama with MCP (Model Context Protocol) integration.

![LIT TUI Demo](docs/demo.gif)

## ✨ Features

- **🚀 Fast**: Starts in milliseconds, not seconds
- **💡 Smart**: Optional integration with system-prompt-composer for enhanced prompts
- **🔧 Extensible**: MCP integration for dynamic tool discovery and execution
- **🎨 Beautiful**: Rich terminal interface with syntax highlighting and themes
- **⌨️ Keyboard-first**: Efficient navigation designed for developers
- **📦 Lightweight**: No Electron overhead - pure Python performance
- **🔄 Cross-platform**: Works on Linux, macOS, and Windows terminals

## 🚀 Quick Start

### Installation

```bash
# Install from PyPI (when published)
pip install lit-tui

# Or install from source
git clone https://github.com/lit-ai/lit-tui.git
cd lit-tui
pip install -e .
```

### Prerequisites

- Python 3.8+
- [Ollama](https://ollama.ai) running locally
- A terminal with Unicode support

### Usage

```bash
# Start lit-tui
lit-tui

# Or with specific model
lit-tui --model llama2

# With debug logging
lit-tui --debug
```

## 🛠️ Configuration

lit-tui stores its configuration in `~/.lit-tui/config.json`. On first run, it will create a default configuration.

### Example Configuration

```json
{
  "ollama": {
    "host": "http://localhost:11434",
    "default_model": "llama2"
  },
  "ui": {
    "theme": "dark",
    "font_size": "medium",
    "show_token_count": true
  },
  "storage": {
    "max_sessions": 100,
    "auto_save": true
  },
  "mcp": {
    "enabled": true,
    "servers": []
  }
}
```

## 🔧 MCP Integration

lit-tui supports the Model Context Protocol for dynamic tool integration:

```json
{
  "mcp": {
    "enabled": true,
    "servers": [
      {
        "name": "filesystem",
        "command": "mcp-server-filesystem",
        "args": ["--root", "/home/user/projects"]
      },
      {
        "name": "git",
        "command": "mcp-server-git"
      }
    ]
  }
}
```

## ⌨️ Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `Ctrl+N` | New chat session |
| `Ctrl+L` | Clear current chat |
| `Ctrl+S` | Save session |
| `Ctrl+O` | Open session |
| `Ctrl+Q` | Quit |
| `Tab` | Switch between panels |
| `Enter` | Send message |
| `Shift+Enter` | New line in message |
| `Ctrl+/` | Show help |

## 🎨 Themes

lit-tui supports custom themes. See [examples/custom_themes/](examples/custom_themes/) for examples.

## 🏗️ Architecture

lit-tui is designed as a reference implementation showcasing:

- **Clean async architecture** using Python's asyncio
- **Direct protocol integration** with Ollama and MCP
- **Terminal-native UI** with Textual framework
- **Modular design** with clear separation of concerns
- **Performance optimization** for responsive chat experience

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Development Setup

```bash
git clone https://github.com/lit-ai/lit-tui.git
cd lit-tui
pip install -e ".[dev]"
pre-commit install
```

### Running Tests

```bash
pytest
```

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

## 🙏 Acknowledgments

- Built with [Textual](https://textual.textualize.io/) - an amazing Python TUI framework
- Inspired by [lazygit](https://github.com/jesseduffield/lazygit), [k9s](https://k9scli.io/), and other excellent TUI applications
- MCP integration follows the [Model Context Protocol](https://modelcontextprotocol.io/) specification

---

**Made with ❤️ by [LIT](https://lit.ai) - Advancing the field of AI through open-source innovation**
