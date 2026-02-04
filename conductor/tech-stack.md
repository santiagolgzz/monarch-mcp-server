# Technology Stack

## Core Development
- **Language**: Python (>=3.10)
- **MCP Frameworks**: `mcp[cli]`, `fastmcp`
- **Primary API**: `monarchmoney` (Unofficial Monarch Money API wrapper)
- **Data Validation**: `pydantic` (Used for tool schema definition and response validation)
- **Communication**: `gql` (GraphQL client for Monarch Money API)

## Infrastructure & Runtime
- **Server Environment**: `uvicorn` with `starlette` for optional HTTP/Remote hosting.
- **Dependency Management**: `pip` (via `requirements.txt` and `pyproject.toml`) and `uv`.
- **Authentication**: `keyring` and `python-dotenv` for secure credential handling.
- **Session Persistence**: Secure local storage using `pickle` (located in `~/.mm/`).

## Quality Assurance & Tooling
- **Linting & Formatting**: `ruff`
- **Type Checking**: `ty`
- **Testing Framework**: `pytest` with `pytest-asyncio`
