# Contributing to ET Phone Home

Thank you for your interest in contributing! This document provides guidelines for contributing to the project.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Making Changes](#making-changes)
- [Pull Request Process](#pull-request-process)
- [Coding Standards](#coding-standards)
- [Testing](#testing)
- [Documentation](#documentation)

## Code of Conduct

This project follows our [Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code.

## Getting Started

### Types of Contributions

- **Bug Reports**: Found a bug? Open an issue with details
- **Feature Requests**: Have an idea? Open an issue to discuss
- **Code**: Fix bugs or implement features via pull requests
- **Documentation**: Improve docs, fix typos, add examples
- **Testing**: Add test coverage or report test failures

### First-Time Contributors

Look for issues labeled `good first issue` - these are specifically chosen for newcomers.

## Development Setup

```bash
# Clone the repository
git clone https://github.com/jfreed-dev/etphonehome.git
cd etphonehome

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # Linux/macOS
# or: .venv\Scripts\activate  # Windows

# Install with development dependencies
pip install -e ".[server,dev]"

# Verify setup
pytest
```

## Making Changes

### Branch Naming

Use descriptive branch names:

- `feature/add-macos-support`
- `fix/tunnel-reconnection-bug`
- `docs/improve-setup-guide`

### Commit Messages

Write clear, concise commit messages:

```
Add automatic reconnection on connection loss

- Implement exponential backoff for reconnection attempts
- Add max_reconnect_delay configuration option
- Update documentation with new settings
```

**Guidelines:**
- Use present tense ("Add feature" not "Added feature")
- First line: summary (50 chars or less)
- Body: explain what and why (wrap at 72 chars)
- Reference issues: "Fixes #123" or "Related to #456"

## Pull Request Process

### Before Submitting

1. **Update from main**: `git fetch origin && git rebase origin/main`
2. **Run tests**: `pytest`
3. **Run linters**: `black . && ruff check --fix .`
4. **Update docs**: If your change affects usage

### Submitting

1. Push your branch: `git push origin your-branch`
2. Open a pull request on GitHub
3. Fill out the PR template completely
4. Wait for CI checks to pass
5. Request review if not automatically assigned

### Review Process

- Maintainers will review within a few days
- Address feedback by pushing additional commits
- Once approved, a maintainer will merge

## Coding Standards

### Python Style

We use `black` for formatting and `ruff` for linting:

```bash
# Format code
black .

# Check for issues
ruff check .

# Auto-fix issues
ruff check --fix .
```

### Code Principles

- **Readability**: Clear code over clever code
- **Simplicity**: Minimal dependencies, straightforward logic
- **Testing**: New features should include tests
- **Documentation**: Public APIs should have docstrings

### File Organization

```
etphonehome/
├── client/          # Phone home client code
├── server/          # MCP server code
├── shared/          # Shared protocol and utilities
├── tests/           # Test suite
├── docs/            # Documentation
├── scripts/         # Utility scripts
└── build/           # Build infrastructure
```

## Testing

### Running Tests

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_agent.py

# Run with coverage
pytest --cov=client --cov=server --cov=shared
```

### Writing Tests

- Place tests in `tests/` directory
- Name test files `test_*.py`
- Use descriptive test function names
- Include both positive and negative test cases

```python
def test_run_command_returns_stdout():
    """Test that run_command captures stdout correctly."""
    # Arrange
    agent = Agent(allowed_paths=[])

    # Act
    result = agent.handle_run_command({"cmd": "echo hello"})

    # Assert
    assert result["stdout"].strip() == "hello"
    assert result["returncode"] == 0
```

## Documentation

### Updating Docs

- **README.md**: Project overview and quick start
- **docs/**: Detailed guides and references
- **CLAUDE.md**: Development guidance (auto-generated context)

### Documentation Style

- Use clear, concise language
- Include code examples
- Add diagrams for complex concepts
- Keep quick reference sections updated

## Questions?

- **General questions**: Open a Discussion
- **Bug reports**: Open an Issue
- **Security issues**: See [SECURITY.md](SECURITY.md)

Thank you for contributing!
