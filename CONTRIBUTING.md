# Contributing to LIT TUI

Thank you for your interest in contributing to LIT TUI! This document provides guidelines for contributing to the project.

## 🚀 Getting Started

### Prerequisites

- Python 3.8+
- Git
- A terminal with Unicode support

### Development Setup

1. Fork the repository on GitHub
2. Clone your fork locally:
   ```bash
   git clone https://github.com/your-username/lit-tui.git
   cd lit-tui
   ```

3. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

4. Install development dependencies:
   ```bash
   pip install -e ".[dev]"
   ```

5. Install pre-commit hooks:
   ```bash
   pre-commit install
   ```

## 🛠️ Development Guidelines

### Code Style

We use several tools to maintain code quality:

- **Black** for code formatting
- **isort** for import sorting  
- **mypy** for type checking
- **pytest** for testing

Run these before committing:
```bash
black src/
isort src/
mypy src/
pytest
```

### Project Structure

```
src/lit_tui/
├── app.py              # Main application
├── config.py           # Configuration management
├── screens/            # UI screens
├── widgets/            # Reusable UI components
├── services/           # Business logic (Ollama, MCP, etc.)
└── utils/              # Utility functions
```

### Adding New Features

1. **Create an issue** first to discuss the feature
2. **Create a branch** from main: `git checkout -b feature/your-feature`
3. **Implement your feature** following the existing patterns
4. **Add tests** for your changes
5. **Update documentation** if needed
6. **Submit a pull request**

## 📝 Commit Guidelines

We follow conventional commits:

- `feat:` New features
- `fix:` Bug fixes
- `docs:` Documentation changes
- `style:` Code style changes (formatting, etc.)
- `refactor:` Code refactoring
- `test:` Adding or updating tests
- `chore:` Build process or auxiliary tool changes

Example:
```
feat(chat): add syntax highlighting for code blocks
fix(config): handle missing config file gracefully
docs(readme): update installation instructions
```

## 🧪 Testing

Run the test suite:
```bash
pytest
```

Run with coverage:
```bash
pytest --cov=lit_tui --cov-report=html
```

## 📚 Documentation

- Update docstrings for new functions/classes
- Update README.md for user-facing changes
- Add examples in the `examples/` directory if appropriate

## 🐛 Bug Reports

When reporting bugs, please include:

- **Operating system** and terminal type
- **Python version**
- **LIT TUI version**
- **Steps to reproduce** the issue
- **Expected vs actual behavior**
- **Logs** if available (run with `--debug`)

## 💡 Feature Requests

For feature requests:

- **Describe the use case** - what problem does it solve?
- **Provide examples** of how it would be used
- **Consider alternatives** - are there other ways to solve this?
- **Implementation ideas** - any thoughts on how it might work?

## 🏗️ Architecture Guidelines

### Async-First Design

- Use `async/await` for I/O operations
- Prefer async widgets and methods when possible
- Handle cancellation gracefully

### Error Handling

- Use proper exception handling
- Log errors with appropriate levels
- Provide user-friendly error messages
- Graceful degradation when services are unavailable

### Performance

- Lazy load large data sets
- Use streaming for real-time updates
- Minimize blocking operations
- Profile performance-critical sections

## 🤝 Community

- Be respectful and inclusive
- Help newcomers get started
- Share knowledge and best practices
- Follow the [Code of Conduct](CODE_OF_CONDUCT.md)

## 📄 License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

Thank you for contributing to LIT TUI! 🎉
