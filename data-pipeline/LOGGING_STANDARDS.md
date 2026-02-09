# Logging Standards

## Logging Level Guidelines

Use the following guidelines when adding log statements to the codebase:

### ERROR
Use for **failures that prevent normal operation** and require immediate attention:
- Database connection failures
- Critical resource unavailability
- Unrecoverable errors in core functionality
- Data corruption detected

**Examples:**
```python
logger.error("Failed to connect to database after 5 retries", exc_info=True)
logger.error("Critical: Data integrity violation detected in charity table")
```

### WARNING
Use for **recoverable issues** that should be investigated but don't stop execution:
- Fallback to default behavior
- Degraded functionality
- Expected errors with retries
- Configuration issues with sensible defaults
- Failed external API calls (will retry or skip)

**Examples:**
```python
logger.warning("Failed to fetch from API, using cached data")
logger.warning("Missing optional field 'website_url' for charity EIN 12-3456789")
logger.warning("Robots.txt fetch failed, assuming allow-all policy")
```

### INFO
Use for **important milestones** in normal operation:
- Process start/complete
- Major state changes
- Successful operations worth tracking
- Data pipeline phase completions
- Configuration loaded

**Examples:**
```python
logger.info("Starting data collection for 50 charities")
logger.info("Reconciliation complete for EIN 12-3456789: 25 fields updated")
logger.info("Database sync completed: 10,523 rows synced")
```

### DEBUG
Use for **detailed diagnostic information** useful during development:
- Individual step progress
- Intermediate calculations
- Detailed flow information
- Values at checkpoints
- Fallback logic triggered

**Examples:**
```python
logger.debug(f"Trying profile {profile_name} for URL {url}")
logger.debug(f"Selected {source} by priority for field {field_name}")
logger.debug(f"Cache hit for charity {ein}")
```

## Common Anti-Patterns to Avoid

### ❌ Don't Log Errors as Warnings
```python
# BAD
logger.warning("Database write failed: disk full")

# GOOD
logger.error("Database write failed: disk full", exc_info=True)
```

### ❌ Don't Log Warnings as Errors
```python
# BAD
logger.error("Optional field missing, using default")

# GOOD
logger.warning("Optional field missing, using default value")
```

### ❌ Don't Log Expected Failures as Errors
```python
# BAD - This is expected during sitemap parsing
logger.error(f"URL {url} returned 404")

# GOOD
logger.debug(f"URL {url} returned 404, skipping")
```

### ❌ Don't Log Success as Warnings
```python
# BAD
logger.warning("Successfully used fallback method")

# GOOD
logger.info("Primary method failed, fallback succeeded")
```

## Exception Logging

Always use `exc_info=True` for ERROR level logs to get full stack traces:

```python
try:
    risky_operation()
except Exception as e:
    logger.error(f"Operation failed: {e}", exc_info=True)
```

For WARNING level, include exc_info only if the stack trace adds value:

```python
try:
    optional_operation()
except ValueError as e:
    # Stack trace not needed for validation errors
    logger.warning(f"Validation failed: {e}")
```

## Performance Considerations

Use lazy logging for expensive operations:

```python
# BAD - String formatting happens even if debug is disabled
logger.debug(f"Processing data: {expensive_computation()}")

# GOOD - Computation only happens if debug enabled
logger.debug("Processing data: %s", lambda: expensive_computation())

# BETTER - Use conditional
if logger.isEnabledFor(logging.DEBUG):
    logger.debug(f"Processing data: {expensive_computation()}")
```
