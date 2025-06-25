#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time  : 2025/6/24 21:36
@Author  : Enhanced Logging Implementation
@File  : enhanced_logger.py
"""
import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


class EnhancedLogger:
  """
  Singleton enhanced logger that captures LLM API requests and agent messages
  in a unified JSON format without interfering with the existing loguru system.
  """
  
  _instance = None
  _lock = threading.Lock()
  
  def __new__(cls):
    if cls._instance is None:
      with cls._lock:
        if cls._instance is None:
          cls._instance = super().__new__(cls)
    return cls._instance
  
  def __init__(self):
    if not hasattr(self, 'initialized'):
      self.initialized = True
      self.enabled = False
      self.log_file_path: Optional[Path] = None
      self.file_lock = threading.Lock()
      self._log_entries: List[Dict[str, Any]] = []
  
  def configure(self, enabled: bool, log_file_path: Optional[Union[str, Path]] = None):
    """Configure the enhanced logger"""
    self.enabled = enabled
    
    if enabled:
      # Ensure we have a log file path when enabled
      if log_file_path:
        self.log_file_path = Path(log_file_path)
      else:
        # Create default path if none provided
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_dir = Path("enhanced_logs")
        log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file_path = log_dir / f"{timestamp}.json"
      
      # Ensure parent directory exists and initialize file
      self.log_file_path.parent.mkdir(parents=True, exist_ok=True)
      if not self.log_file_path.exists():
        self._write_log_entries([])
      
      print(f"Enhanced logging enabled")
      print(f"Enhanced log file: {self.log_file_path}")
    else:
      print(f"Enhanced logging disabled")
  
  def log_api_request(
    self,
    model: str,
    request_messages: List[Dict[str, Any]],
    response_content: str,
    stream: bool = False
  ):
    """Log an LLM API request and response"""
    if not self.enabled:
      return
    
    try:
      log_entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "event": "api_request",
        "model": model,
        "request": request_messages,
        "response": {
          "role": "assistant",
          "content": response_content
        }
      }
      
      self._append_log_entry(log_entry)
      
    except Exception as e:
      print(f"Enhanced logging failed for API request: {e}")
  
  def log_agent_message(
    self,
    sender: str,
    recipients: List[str],
    content: str,
    generation_source: str = "unknown"
  ):
    """Log an agent message communication"""
    if not self.enabled:
      return
    
    try:
      log_entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "event": "message",
        "message": {
          "sender": sender,
          "recipients": recipients,
          "content": content
        }
      }
      
      self._append_log_entry(log_entry)
      
    except Exception as e:
      print(f"Enhanced logging failed for agent message: {e}")
  
  def _append_log_entry(self, entry: Dict[str, Any]):
    """Thread-safe append of log entry to file"""
    if not self.log_file_path:
      return
    
    with self.file_lock:
      try:
        # Read existing entries
        if self.log_file_path.exists():
          with open(self.log_file_path, 'r', encoding='utf-8') as f:
            try:
              entries = json.load(f)
            except json.JSONDecodeError:
              entries = []
        else:
          entries = []
        
        # Append new entry
        entries.append(entry)
        
        # Write back to file
        self._write_log_entries(entries)
        
      except Exception as e:
        print(f"Failed to write enhanced log entry: {e}")
  
  def _write_log_entries(self, entries: List[Dict[str, Any]]):
    """Write log entries to file"""
    if not self.log_file_path:
      print("Enhanced logging: No log file path set")
      return
    
    try:
      # Ensure parent directory exists
      self.log_file_path.parent.mkdir(parents=True, exist_ok=True)
      with open(self.log_file_path, 'w', encoding='utf-8') as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)
    except Exception as e:
      print(f"Enhanced logging: Failed to write to {self.log_file_path}: {e}")
  
  def get_status(self) -> Dict[str, Any]:
    """Get current status of enhanced logger for debugging"""
    return {
      "enabled": self.enabled,
      "log_file_path": str(self.log_file_path) if self.log_file_path else None,
      "file_exists": self.log_file_path.exists() if self.log_file_path else False,
      "parent_dir_exists": self.log_file_path.parent.exists() if self.log_file_path else False,
    }
  
  def test_logging(self):
    """Test the logging functionality"""
    if not self.enabled:
      print("Enhanced logging is disabled")
      return False
    
    try:
      # Test API request logging
      self.log_api_request(
        model="test-model",
        request_messages=[{"role": "user", "content": "test"}],
        response_content="test response"
      )
      
      # Test agent message logging
      self.log_agent_message(
        sender="TestSender",
        recipients=["TestRecipient"],
        content="test message",
        generation_source="test"
      )
      
      print(f"Enhanced logging test completed. Check file: {self.log_file_path}")
      return True
      
    except Exception as e:
      print(f"Enhanced logging test failed: {e}")
      return False


# Global instance
enhanced_logger = EnhancedLogger()
