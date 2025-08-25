# Debug Proxy Server

A configurable Python REST API proxy server designed for debugging and testing. This proxy allows you to intercept, debug, and inject failures into HTTP requests between clients and backend services.

## Features

- **Single target with multiple endpoints** - Configure one backend service with multiple endpoint behaviors
- **Wildcard path matching** - Automatically forward unconfigured paths using `/*` patterns
- **URL path transformation** - Add prefixes to backend URLs (e.g., `/v2.0/foo` → `/service/v2.0/foo`)
- **Failure injection** - Simulate various failure scenarios:
  - Count-based failures (fail on the Nth request)
  - Periodic failures (fail every N requests)
  - Probability-based failures (random failure rate)
  - Delayed responses with timeouts
  - **Toggle functionality** - Enable/disable failure rules without deletion
- **Request debugging** - Detailed logging of requests and responses
- **Dynamic configuration reloading** - Changes to config file are applied automatically
- **Environment variable support** - Use environment variables in configuration

## Breaking Changes

**Version 2.0+**: Configuration structure has changed from multiple targets to single target.

**Before (v1.x):**
```yaml
targets:
  service1: { url: "http://localhost:3001", endpoints: [...] }
  service2: { url: "http://localhost:3002", endpoints: [...] }
```

**After (v2.0+):**
```yaml
target:
  url: "http://localhost:3001"
  endpoints: [...]
```

This change fixes the logical issue where there was no way to route requests to specific targets. All requests now go to the single configured target URL with endpoint-based path matching.

## Installation

1. Clone or download the project files
2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Quick Start

1. Copy the example configuration:
```bash
cp config.example.yaml config.yaml
```

2. Edit `config.yaml` to configure your target service

3. Run the proxy:
```bash
python main.py
```

The proxy will start on `http://localhost:8000` by default.

## Configuration

### Basic Structure

```yaml
server:
  host: "0.0.0.0"
  port: 8000
  debug: true

logging:
  level: "INFO"
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

target:
  url: "http://backend-service:3000"
  path_prefix: "/api/v1"  # Optional: prepend to all requests
  headers:
    X-Proxy-Source: "debug-proxy"
  endpoints:
    - path: "/api/users"
      methods: ["GET", "POST"]
      debug: true
      failure_rules: []
    - path: "/*"  # Wildcard - forwards all other paths
      methods: ["*"]
      debug: false
```

### Failure Rules

#### Count-based Failure
Fail on a specific request number:
```yaml
failure_rules:
  - condition:
      enabled: true
      method: "POST"
      count: 3  # Fail on the 3rd POST request
    response:
      status_code: 503
      body: {"error": "Service temporarily unavailable"}
```

#### Periodic Failure
Fail every N requests:
```yaml
failure_rules:
  - condition:
      enabled: true
      method: "GET"
      every: 10  # Fail every 10th GET request
    response:
      status_code: 429
      body: {"error": "Rate limited"}
```

#### Probability-based Failure
Random failure rate:
```yaml
failure_rules:
  - condition:
      enabled: true
      method: "GET"
      probability: 0.1  # 10% chance of failure
    response:
      status_code: 500
      body: {"error": "Internal server error"}
```

#### Delayed Response
Add delay before responding:
```yaml
failure_rules:
  - condition:
      enabled: true
      method: "POST"
      delay: 5000  # 5 second delay
    response:
      status_code: 408
      body: {"error": "Request timeout"}
```

#### Enabling/Disabling Rules
Toggle failure rules without deleting them:
```yaml
failure_rules:
  - condition:
      enabled: true   # Active rule
      method: "POST"
      every: 3
    response:
      status_code: 503
      body: {"error": "Service unavailable"}

  - condition:
      enabled: false  # Disabled rule
      method: "GET"
      probability: 0.1
    response:
      status_code: 500
      body: {"error": "Random failure"}
```

### Path Prefix

Transform request URLs by adding a prefix to the backend URL:
```yaml
target:
  url: "http://backend-service:3000"
  path_prefix: "/service"  # Transform /v2.0/foo -> /service/v2.0/foo
  endpoints: [...]
```

This feature is useful for:
- Adding versioning prefixes (e.g., `/api/v1` before all paths)
- Routing to specific service endpoints
- Legacy API path compatibility

### Environment Variables

Use environment variables in headers:
```yaml
target:
  url: "https://api.stripe.com"
  headers:
    Authorization: "Bearer ${STRIPE_API_KEY}"
```

## Usage Examples

### Debugging API Calls
Set `debug: true` on endpoints to see detailed request/response logging:
```
2024-01-01 10:00:00 - proxy-server - INFO - [proxy] POST /api/users -> http://localhost:3001
2024-01-01 10:00:01 - proxy-server - INFO - [proxy] Response: 201
```

### Testing Failure Scenarios
Configure failure rules to test how your application handles errors:
- Simulate service outages with 503 errors
- Test timeout handling with delays
- Verify retry logic with periodic failures

### Load Testing
Use probability-based failures to simulate real-world error rates during load testing.

## Dynamic Configuration

The proxy automatically reloads configuration when `config.yaml` is modified. No restart required!

```bash
# Edit config file
vim config.yaml

# Changes are applied immediately
# Check logs for: "Configuration reloaded successfully"
```

## API

The proxy forwards all HTTP methods (`GET`, `POST`, `PUT`, `DELETE`, etc.) and preserves:
- Request headers
- Request body
- Query parameters
- Response headers
- Response body
- HTTP status codes

## Files

- `main.py` - Main proxy server implementation
- `config.py` - Configuration loading and data models
- `config.example.yaml` - Example configuration file
- `requirements.txt` - Python dependencies
- `README.md` - This documentation

## Dependencies

- **FastAPI** - Web framework
- **httpx** - HTTP client for proxying requests
- **uvicorn** - ASGI server
- **PyYAML** - YAML configuration parsing
- **watchdog** - File system monitoring for config reloading
- **pydantic** - Data validation and settings management

## Development

This code was written by Claude (Anthropic's AI assistant) to provide a flexible debugging and testing proxy for REST APIs.

## License

This project is provided as-is for debugging and testing purposes.
