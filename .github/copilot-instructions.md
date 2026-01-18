# AI Copilot Instructions for online-service-mcp-server

## Project Overview
Building an MCP (Model Context Protocol) server that connects to REST API-based online services, enabling Claude and other AI tools to interact with external services through standardized MCP endpoints.

## Architecture & Components

### MCP Server Structure
- **Entry Point**: Main server initialization (typically `src/server.py` or similar)
- **Resources**: MCP resource handlers for exposing service data/capabilities
- **Tools**: MCP tool definitions for service operations/actions
- **Prompts**: MCP prompts for guiding AI interactions with services

### Key Directories (when established)
- `src/` - Core MCP server implementation
- `src/handlers/` - Request handlers for different service endpoints
- `src/models/` - Data models and schemas for service responses
- `tests/` - Unit and integration tests for handlers and tools

## MCP Protocol Patterns

### Tool Definition Pattern
Tools should follow MCP format with clear input schemas:
- Use JSON schema for type safety
- Include description, summary, and instructions
- Handle errors gracefully with detailed error messages
- Document required vs optional parameters explicitly

### Resource Handling Pattern
Resources represent accessible service data:
- Use URI-like paths: `service://collection/id`
- Include metadata (mime type, text content)
- Support listing operations where applicable
- Implement caching for expensive operations

## Development Workflow

### Setup & Dependencies
- Python 3.10+ required
- Use virtual environments (`python -m venv`)
- Dependency management via pip or uv
- Install MCP SDK: `pip install mcp`

### Testing
- Unit tests for individual handlers
- Integration tests with mock API responses
- Test error scenarios and edge cases

### Running Locally
- Start server: `python -m src.server` or appropriate entry point
- Debug via MCP client tools or Claude integration
- Validate tool/resource registration in server logs

## Integration Patterns

### REST API Client Setup
- Use `requests` or `httpx` for HTTP calls
- Implement connection pooling for performance
- Handle authentication (API keys, OAuth, etc.) via environment variables
- Implement retry logic with exponential backoff for rate limits

### Error Handling
- Map HTTP errors to MCP error responses
- Log API responses for debugging (mask sensitive data)
- Return user-friendly error messages
- Include error codes from external services when relevant

## Conventions & Patterns

### Naming
- Tools: snake_case, verb-first (e.g., `get_user_profile`, `create_ticket`)
- Resources: descriptive URI paths (e.g., `service://users/123`)
- Handlers: match service endpoint names

### Documentation
- Every tool should have a clear `description` field
- Include examples in tool documentation
- Document required credentials/setup in README

### Configuration
- Use environment variables for API endpoints, keys, and credentials
- Never commit secrets; use `.env` template with placeholders
- Support both local development and production configurations

## Common Tasks

### Adding a New Service Integration
1. Create handler in `src/handlers/{service_name}.py`
2. Define tools in `src/tools/{service_name}_tools.py`
3. Implement resource handlers if applicable
4. Add unit tests in `tests/handlers/test_{service_name}.py`
5. Update README with service setup instructions

### Debugging MCP Issues
- Enable MCP debug logging: `MCP_DEBUG=1` environment variable
- Check server logs for tool registration confirmation
- Validate JSON schemas in tool definitions
- Use MCP inspector tools to verify server responses

## Key Files to Know
- `README.md` - Project overview and setup guide
- `.gitignore` - Python project defaults already configured
