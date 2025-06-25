# Enhanced Logging System - Usage Guide

This document provides a comprehensive guide on how to use the enhanced logging system implemented for MetaGPT.

## Overview

The enhanced logging system captures both LLM API requests and agent message communications in a unified JSON format. It operates independently of MetaGPT's existing loguru-based logging system and provides detailed traces of agent interactions and LLM communications.

## Configuration

### Basic Configuration

Enable enhanced logging in your `config2.yaml` file:

```yaml
# Basic configuration - uses default log file path
enhanced_logging: true

# Custom log file path (optional)
enhanced_log_file_path: "/path/to/custom/logfile.json"
```

### Default Behavior

When `enhanced_logging: true` is set without specifying a custom path:
- Log files are created in `enhanced_logs/YYYYMMDD_HHMMSS.json`
- Directory is automatically created if it doesn't exist
- Each session gets a unique timestamped log file

## Log Format

The enhanced logging system produces a unified JSON array with two types of entries:

### 1. LLM API Request Log Entry

```json
{
  "timestamp": "2025-06-24T12:57:00Z",
  "event": "api_request",
  "model": "gpt-4",
  "request": [
    {"role": "system", "content": "You are a ProductManager, named Alice..."},
    {"role": "user", "content": "Create a web-based task management application"}
  ],
  "response": {
    "role": "assistant",
    "content": "I'll create a comprehensive product requirements document..."
  }
}
```

### 2. Agent Message Log Entry

```json
{
  "timestamp": "2025-06-24T13:42:15Z",
  "event": "message",
  "message": {
    "sender": "Bob(Architect)",
    "recipients": ["Engineer", "QAEngineer"],
    "content": "Based on the PRD, I've designed a microservices architecture...",
    "generation_source": "llm_generated"
  }
}
```

## Usage Examples

### Programmatic Configuration

```python
from metagpt.enhanced_logger import enhanced_logger

# Configure the logger directly
enhanced_logger.configure(
    enabled=True,
    log_file_path="my_custom_logs.json"
)

# Manual logging (usually not needed as it's automatic)
enhanced_logger.log_api_request(
    model="gpt-4",
    request_messages=[{"role": "user", "content": "Hello"}],
    response_content="Hi there!"
)

enhanced_logger.log_agent_message(
    sender="ProductManager",
    recipients=["Architect"],
    content="Please design the system",
    generation_source="user_input"
)
```

### Configuration via Config Object

```python
from metagpt.config2 import Config

config = Config(
    enhanced_logging=True,
    enhanced_log_file_path="session_logs.json",
    llm={
        "api_type": "openai",
        "model": "gpt-4",
        "api_key": "your-api-key"
    }
)
```

## Integration Points

### Automatic LLM Logging

The system automatically hooks into:
- `BaseLLM.acompletion_text()` - All LLM API calls
- `BaseLLM._achat_completion_stream()` - Streaming API calls

### Automatic Message Logging

The system automatically hooks into:
- `Environment.publish_message()` - All inter-agent communications

## Log Analysis

### Reading Log Files

```python
import json
from pathlib import Path

# Read the log file
with open("enhanced_logs/20250624_213000.json", "r") as f:
    log_entries = json.load(f)

# Filter by event type
api_requests = [entry for entry in log_entries if entry["event"] == "api_request"]
messages = [entry for entry in log_entries if entry["event"] == "message"]

# Analyze API usage
for request in api_requests:
    print(f"Model: {request['model']}")
    print(f"Request tokens: ~{len(str(request['request']))}")
    print(f"Response length: {len(request['response']['content'])}")

# Analyze agent communications
for message in messages:
    msg = message["message"]
    print(f"{msg['sender']} -> {msg['recipients']}")
    print(f"Source: {msg['generation_source']}")
```

### Debug Mode

Enable debug logging to see enhanced logging operations:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```