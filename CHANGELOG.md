# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.1] - 2026-03-29

### Security
- Tightened backend CORS defaults to explicit development origins and added `CORS_ALLOW_ORIGINS` for deployment-specific allowlists
- Stopped returning raw backend exception details from upload failures to avoid leaking internal error information
- Upgraded `react-syntax-highlighter` to `16.1.1` to pull in a non-vulnerable PrismJS dependency chain
- Fixed Dependabot's Python configuration to monitor the root `requirements.txt` file where backend dependencies are actually declared

### Fixed
- Aligned application version metadata for the v1.0.1 patch release

## [1.0.0] - 2026-03-29

### Added
- **Full-stack n8n-to-Python transpiler** with FastAPI backend and React/Vite frontend
- **Workflow parsing & validation** using Pydantic models for n8n workflow JSON
- **Automatic Python code generation** from n8n workflow definitions
- **Dual runtime mode detection**:
  - FastAPI mode for webhook and chat triggers
  - Standalone script mode for manual and schedule triggers
- **Node handler support** for 20+ n8n node types:
  - HTTP requests with auth/headers/params/body support
  - Conditional branching (if/else) with expression evaluation
  - Manual data transformation and field assignment
  - LangChain AI integration (ChatTrigger, Memory, OpenAI)
  - Database operations (PostgreSQL, MySQL, MongoDB)
  - Webhook and scheduled task triggers
  - Chat trigger with message extraction
- **Expression engine** for evaluating n8n expressions in Python
- **Dependency inference** - automatically detects required Python packages
- **Credential security** - sensitive values use `os.getenv()` with `.env.example` generation
- **React UI** with:
  - Workflow upload/preview
  - Live code preview with syntax highlighting
  - ZIP project download
  - Responsive design with Tailwind CSS
- **Docker support** for containerized backend and frontend
- **Comprehensive test suite** with pytest for pipeline and handler validation
- **RESTful API** endpoints for upload, download, and node type enumeration

### Known Limitations
- Some node types generate stub implementations with TODO comments (merge, itemLists)
- JavaScript code blocks in `code` nodes are preserved as comments with conversion TODO
- LangChain memory nodes require both `langchain` and `langchain-classic` packages

### Technical Specs
- **Backend**: Python 3.10+, FastAPI, Pydantic, pytest
- **Frontend**: React 18+, TypeScript, Vite, Tailwind CSS
- **Architecture**: Modular handler-based pipeline (parse → IR → emit → post-process)
- **License**: MIT

[1.0.1]: https://github.com/opsingh861/nCode/releases/tag/v1.0.1
[1.0.0]: https://github.com/opsingh861/nCode/releases/tag/v1.0.0
