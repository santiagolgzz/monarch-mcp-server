# Track Specification: Refactor Server Architecture & Fix Critical Bugs

## Overview
This track aims to resolve significant architectural inconsistencies and bugs introduced by the addition of the HTTP server. The primary goal is to eliminate code duplication between `server.py` and `http_server.py`, optimize performance by adopting native async patterns, and fix critical logic errors in transaction management and log handling.

## Scope
- **Refactoring**: Extract shared tool logic into `src/monarch_mcp_server/tools.py`.
- **Performance**: Convert synchronous tool wrappers to native `async def` and optimize log file reading.
- **Bug Fixes**:
    - Fix `update_transaction` to correctly handle `None` parameters.
    - Validate `account_id` inputs.
    - Standardize `get_account_history` return format.
    - Centralize monkey-patching of `BASE_URL`.

## Key Changes
1.  **`src/monarch_mcp_server/__init__.py`**: Central location for `MonarchMoneyEndpoints.BASE_URL` patch.
2.  **`src/monarch_mcp_server/client.py`**: New module for unified client instantiation and authentication.
3.  **`src/monarch_mcp_server/tools.py`**: New module containing all 40+ tool definitions, refactored to be async-native and registered via a shared function.
4.  **`src/monarch_mcp_server/server.py` & `http_server.py`**: Simplified to only handle transport-specific setup and import tools from the shared module.

## Success Criteria
- All tools are defined in a single location (`tools.py`).
- No use of `run_async` for tool implementations; all tools are `async def`.
- `update_transaction` correctly updates only provided fields.
- Large log files are read efficiently without loading the entire file into memory.
- Existing tests pass, and new tests cover the refactored modules.
