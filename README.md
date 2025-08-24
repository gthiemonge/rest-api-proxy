# Debug Proxy Server

A configurable Python REST API proxy server designed for debugging and testing. This proxy allows you to intercept, debug, and inject failures into HTTP requests between clients and backend services.

## Features

- **Multi-target configuration** - Configure multiple backend services with different endpoints
- **Wildcard path matching** - Automatically forward unconfigured paths using `/*` patterns
- **Failure injection** - Simulate various failure scenarios:
  - Count-based failures (fail on the Nth request)
  - Periodic failures (fail every N requests)
  - Probability-based failures (random failure rate)
  - Delayed responses with timeouts
- **Request debugging** - Detailed logging of requests and responses
- **Dynamic configuration reloading** - Changes to config file are applied automatically
- **Environment variable support** - Use environment variables in configuration

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

2. Edit `config.yaml` to configure your target services

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

targets:
  service-name:
    url: "http://backend-service:3000"
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
      method: "POST"
      delay: 5000  # 5 second delay
    response:
      status_code: 408
      body: {"error": "Request timeout"}
```

### Environment Variables

Use environment variables in headers:
```yaml
targets:
  payment-service:
    url: "https://api.stripe.com"
    headers:
      Authorization: "Bearer ${STRIPE_API_KEY}"
```

## Usage Examples

### Debugging API Calls
Set `debug: true` on endpoints to see detailed request/response logging:
```
2024-01-01 10:00:00 - proxy-server - INFO - [user-service] POST /api/users -> http://localhost:3001
2024-01-01 10:00:01 - proxy-server - INFO - [user-service] Response: 201
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