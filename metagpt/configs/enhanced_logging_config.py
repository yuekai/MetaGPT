#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time  : 2025/6/24 21:36
@Author  : Enhanced Logging Implementation
@File  : enhanced_logging_config.py
"""
from datetime import datetime
from pathlib import Path
from typing import Optional, Union

from pydantic import field_validator, model_validator

from metagpt.const import METAGPT_ROOT
from metagpt.utils.yaml_model import YamlModel


class EnhancedLoggingConfig(YamlModel):
  """Configuration for enhanced logging system that captures LLM API requests and agent messages"""
  
  enhanced_logging: bool = False
  enhanced_log_file_path: Optional[Union[str, Path]] = None
  
  @field_validator("enhanced_log_file_path")
  @classmethod
  def check_log_file_path(cls, v):
    if v and isinstance(v, str):
      return Path(v)
    return v
  
  @model_validator(mode="after")
  def set_default_log_path(self):
    if self.enhanced_logging and not self.enhanced_log_file_path:
      # Create default path: enhanced_logs/YYYYMMDD_HHMMSS.json
      timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
      log_dir = METAGPT_ROOT / "enhanced_logs"
      log_dir.mkdir(parents=True, exist_ok=True)
      self.enhanced_log_file_path = log_dir / f"{timestamp}.json"
    elif self.enhanced_logging and self.enhanced_log_file_path:
      # Ensure directory exists for custom path
      log_path = Path(self.enhanced_log_file_path)
      log_path.parent.mkdir(parents=True, exist_ok=True)
      self.enhanced_log_file_path = log_path
    
    return self
