#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2024/1/4 01:25
@Author  : alexanderwu
@File    : config2.py
"""
import os
from pathlib import Path
from typing import Dict, Iterable, List, Literal, Optional

from pydantic import BaseModel, Field, model_validator

from metagpt.configs.browser_config import BrowserConfig
from metagpt.configs.embedding_config import EmbeddingConfig
from metagpt.configs.enhanced_logging_config import EnhancedLoggingConfig
from metagpt.configs.exp_pool_config import ExperiencePoolConfig
from metagpt.configs.llm_config import LLMConfig, LLMType
from metagpt.configs.mermaid_config import MermaidConfig
from metagpt.configs.omniparse_config import OmniParseConfig
from metagpt.configs.redis_config import RedisConfig
from metagpt.configs.role_custom_config import RoleCustomConfig
from metagpt.configs.role_zero_config import RoleZeroConfig
from metagpt.configs.s3_config import S3Config
from metagpt.configs.search_config import SearchConfig
from metagpt.configs.workspace_config import WorkspaceConfig
from metagpt.const import CONFIG_ROOT, METAGPT_ROOT
from metagpt.utils.yaml_model import YamlModel


class CLIParams(BaseModel):
    """CLI parameters"""

    project_path: str = ""
    project_name: str = ""
    inc: bool = False
    reqa_file: str = ""
    max_auto_summarize_code: int = 0
    git_reinit: bool = False

    @model_validator(mode="after")
    def check_project_path(self):
        """Check project_path and project_name"""
        if self.project_path:
            self.inc = True
            self.project_name = self.project_name or Path(self.project_path).name
        return self


class Config(CLIParams, YamlModel):
    """Configurations for MetaGPT"""

    # Key Parameters
    llm: LLMConfig

    # RAG Embedding
    embedding: EmbeddingConfig = EmbeddingConfig()

    # omniparse
    omniparse: OmniParseConfig = OmniParseConfig()

    # Global Proxy. Will be used if llm.proxy is not set
    proxy: str = ""

    # Tool Parameters
    search: SearchConfig = SearchConfig()
    enable_search: bool = False
    browser: BrowserConfig = BrowserConfig()
    mermaid: MermaidConfig = MermaidConfig()

    # Storage Parameters
    s3: Optional[S3Config] = None
    redis: Optional[RedisConfig] = None

    # Misc Parameters
    repair_llm_output: bool = False
    prompt_schema: Literal["json", "markdown", "raw"] = "json"
    workspace: WorkspaceConfig = Field(default_factory=WorkspaceConfig)
    enable_longterm_memory: bool = False
    code_validate_k_times: int = 2

    # Experience Pool Parameters
    exp_pool: ExperiencePoolConfig = Field(default_factory=ExperiencePoolConfig)

    # Enhanced Logging Parameters
    enhanced_logging: bool = False
    enhanced_log_file_path: Optional[str] = None

    # Will be removed in the future
    metagpt_tti_url: str = ""
    language: str = "English"
    redis_key: str = "placeholder"
    iflytek_app_id: str = ""
    iflytek_api_secret: str = ""
    iflytek_api_key: str = ""
    azure_tts_subscription_key: str = ""
    azure_tts_region: str = ""
    _extra: dict = dict()  # extra config dict

    # Role's custom configuration
    roles: Optional[List[RoleCustomConfig]] = None

    # RoleZero's configuration
    role_zero: RoleZeroConfig = Field(default_factory=RoleZeroConfig)

    @model_validator(mode="after")
    def init_enhanced_logging(self):
        """Initialize enhanced logging if enabled"""
        if self.enhanced_logging:
            from metagpt.enhanced_logger import enhanced_logger
            from datetime import datetime
            from metagpt.const import METAGPT_ROOT
            
            # Set default log file path if not provided
            if not self.enhanced_log_file_path:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                log_dir = METAGPT_ROOT / "enhanced_logs"
                log_dir.mkdir(parents=True, exist_ok=True)
                self.enhanced_log_file_path = str(log_dir / f"{timestamp}.json")
            
            enhanced_logger.configure(
                enabled=self.enhanced_logging,
                log_file_path=self.enhanced_log_file_path
            )
        return self

    @classmethod
    def from_home(cls, path):
        """Load config from ~/.metagpt/config2.yaml"""
        pathname = CONFIG_ROOT / path
        if not pathname.exists():
            return None
        return Config.from_yaml_file(pathname)

    @classmethod
    def default(cls, reload: bool = False, **kwargs) -> "Config":
        """Load default config
        - Priority: env < default_config_paths
        - Inside default_config_paths, the latter one overwrites the former one
        """
        default_config_paths = (
            METAGPT_ROOT / "config/config2.yaml",
            CONFIG_ROOT / "config2.yaml",
        )
        if reload or default_config_paths not in _CONFIG_CACHE:
            dicts = [dict(os.environ), *(Config.read_yaml(path) for path in default_config_paths), kwargs]
            final = merge_dict(dicts)
            _CONFIG_CACHE[default_config_paths] = Config(**final)
        return _CONFIG_CACHE[default_config_paths]

    @classmethod
    def from_llm_config(cls, llm_config: dict):
        """user config llm
        example:
        llm_config = {"api_type": "xxx", "api_key": "xxx", "model": "xxx"}
        gpt4 = Config.from_llm_config(llm_config)
        A = Role(name="A", profile="Democratic candidate", goal="Win the election", actions=[a1], watch=[a2], config=gpt4)
        """
        llm_config = LLMConfig.model_validate(llm_config)
        dicts = [dict(os.environ)]
        dicts += [{"llm": llm_config}]
        final = merge_dict(dicts)
        return Config(**final)

    def update_via_cli(self, project_path, project_name, inc, reqa_file, max_auto_summarize_code):
        """update config via cli"""

        # Use in the PrepareDocuments action according to Section 2.2.3.5.1 of RFC 135.
        if project_path:
            inc = True
            project_name = project_name or Path(project_path).name
        self.project_path = project_path
        self.project_name = project_name
        self.inc = inc
        self.reqa_file = reqa_file
        self.max_auto_summarize_code = max_auto_summarize_code

    @property
    def extra(self):
        return self._extra

    @extra.setter
    def extra(self, value: dict):
        self._extra = value

    def get_openai_llm(self) -> Optional[LLMConfig]:
        """Get OpenAI LLMConfig by name. If no OpenAI, raise Exception"""
        if self.llm.api_type == LLMType.OPENAI:
            return self.llm
        return None

    def get_azure_llm(self) -> Optional[LLMConfig]:
        """Get Azure LLMConfig by name. If no Azure, raise Exception"""
        if self.llm.api_type == LLMType.AZURE:
            return self.llm
        return None


def merge_dict(dicts: Iterable[Dict]) -> Dict:
    """Merge multiple dicts into one, with the latter dict overwriting the former"""
    result = {}
    for dictionary in dicts:
        result.update(dictionary)
    return result


_CONFIG_CACHE = {}
config = Config.default()
