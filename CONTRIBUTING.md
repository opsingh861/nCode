# Contributing to nCode

Thank you for your interest in contributing to nCode! We welcome contributions from the community and are excited to collaborate with you.

## Code of Conduct

This project adheres to the Contributor Covenant [Code of Conduct](https://www.contributor-covenant.org/version/2/0/code_of_conduct/). By participating, you are expected to uphold this code. Please report unacceptable behavior to [project maintainers].

## How to Contribute

### Reporting Bugs

Before creating a bug report, please check the issue list to avoid duplicates. When creating a bug report, provide:

- **Clear title** describing the issue
- **Exact reproduction steps**
- **Expected behavior**
- **Actual behavior**
- **Screenshots/code snippets** if applicable
- **Environment details** (OS, Python version, etc.)
- **Generated error messages and logs**

### Suggesting Enhancements

Enhancement suggestions are tracked as GitHub issues. When suggesting an enhancement:

- Use a **clear, descriptive title**
- Provide a **step-by-step description** of the enhancement
- Provide **specific examples** to demonstrate the steps
- Describe the **current behavior** and **expected behavior**
- Explain **why this enhancement would be useful**

### Code Contributions

1. **Fork the repository** on GitHub
2. **Clone your fork locally**:
   ```bash
   git clone https://github.com/YOUR_USERNAME/nCode.git
   cd nCode
   ```
3. **Create a feature branch**:
   ```bash
   git checkout -b feature/your-feature-name
   ```
4. **Set up development environment**:
   ```bash
   # Backend
   cd backend && python -m venv .venv
   # Windows
   .\.venv\Scripts\Activate.ps1
   # Unix/macOS
   source .venv/bin/activate

   pip install -r requirements.txt

   # Frontend
   cd ../frontend
   npm install
   ```
5. **Make your changes** following the coding guidelines below
6. **Write or update tests** for your changes
7. **Run tests** to ensure everything passes:
   ```bash
   # Backend tests
   cd backend
   python -m pytest tests/ -v

   # Frontend tests (if applicable)
   cd ../frontend
   npm run test
   ```
8. **Commit your changes** with clear, descriptive messages:
   ```bash
   git commit -m "feat: add new handler for X node type"
   ```
9. **Push to your fork**:
   ```bash
   git push origin feature/your-feature-name
   ```
10. **Create a Pull Request** with:
    - Clear title and description
    - Reference to related issues (e.g., "Fixes #123")
    - List of changes made
    - Any breaking changes or migration notes

## Coding Guidelines

### Python (Backend)

- Follow [PEP 8](https://pep8.org/) style guide
- Use type hints for function arguments and returns
- Write docstrings for all functions and classes
- Use meaningful variable names
- Keep functions small and focused (single responsibility principle)
- Add tests for all new functionality

**Handler Implementation Pattern**:
```python
from backend.handlers.registry import register
from backend.handlers.base import GenerationContext
from backend.core.ir import IRNode, IRNodeKind
from backend.models.workflow import N8nNode

@register("n8n-nodes-base.yourType")
class YourNodeHandler:
    def generate(self, node: N8nNode, ctx: GenerationContext) -> IRNode:
        var = _safe_var(node.name)
        ctx.register_node_var(node.name, var)
        # Implementation...
        return IRNode(...)

    def supported_operations(self) -> list[str]: 
        return ["operation_name"]
    
    def required_packages(self) -> list[str]: 
        return ["package-name"]
```

### TypeScript/React (Frontend)

- Use **interfaces** (not type aliases)
- Write descriptive variable and function names
- Use proper TypeScript typing (avoid `any`)
- Follow React best practices (hooks, functional components)
- Keep components small and reusable
- Add comments for complex logic

### Commit Message Format

Follow conventional commits specification:
```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types**: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

**Examples**:
- `feat(handlers): add support for postgres node operations`
- `fix(expression-engine): resolve undefined variable reference`
- `docs(readme): update installation instructions`
- `test(handlers): add unit tests for http node handler`

## Pull Request Process

1. **Ensure all tests pass** locally before submitting
2. **Update CHANGELOG.md** with your changes under `[Unreleased]` section
3. **Update relevant documentation** (README, docstrings, etc.)
4. **Respond to code review feedback** promptly
5. **Keep PR focused** - one feature per PR when possible
6. **No merge conflicts** - rebase if necessary

## Development Workflow

### Running the Project

```bash
# Full stack with docker
docker compose up --build

# Or manually:
# Terminal 1 - Backend
cd backend
.\.venv\Scripts\Activate.ps1  # Windows
source .venv/bin/activate     # Unix/macOS
python -m uvicorn backend.main:app --reload

# Terminal 2 - Frontend
cd frontend
npm run dev
```

### Testing

```bash
# Run all tests
cd backend
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_handlers.py -v

# Run with coverage
python -m pytest tests/ --cov=backend --cov-report=html
```

## Release Process

Releases follow [Semantic Versioning](https://semver.org/):

- **MAJOR** version for incompatible API changes
- **MINOR** version for new functionality (backward compatible)
- **PATCH** version for bug fixes

## Getting Help

- **Questions**: Open a discussion or issue with the `question` label
- **Documentation**: Check [README.md](README.md) and inline code comments
- **Issues**: Browse existing issues or create a new one

## License

By contributing to nCode, you agree that your contributions will be licensed under its MIT License.

Thank you for contributing! 🎉
