#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Desc   : base env of executing environment

import asyncio
from abc import abstractmethod
from enum import Enum
from typing import Any, Dict, Iterable, Optional, Set, Union

from gymnasium import spaces
from gymnasium.core import ActType, ObsType
from pydantic import BaseModel, ConfigDict, Field, SerializeAsAny, model_validator

from metagpt.base import BaseEnvironment, BaseRole
from metagpt.base.base_env_space import BaseEnvAction, BaseEnvObsParams
from metagpt.context import Context
from metagpt.environment.api.env_api import (
    EnvAPIAbstract,
    ReadAPIRegistry,
    WriteAPIRegistry,
)
from metagpt.logs import logger
from metagpt.memory import Memory
from metagpt.schema import Message
from metagpt.utils.common import get_function_schema, is_coroutine_func, is_send_to
from metagpt.utils.git_repository import GitRepository


class EnvType(Enum):
    ANDROID = "Android"
    GYM = "Gym"
    WEREWOLF = "Werewolf"
    MINECRAFT = "Minecraft"
    STANFORDTOWN = "StanfordTown"


env_write_api_registry = WriteAPIRegistry()
env_read_api_registry = ReadAPIRegistry()


def mark_as_readable(func):
    """mark functionn as a readable one in ExtEnv, it observes something from ExtEnv"""
    env_read_api_registry[func.__name__] = get_function_schema(func)
    return func


def mark_as_writeable(func):
    """mark functionn as a writeable one in ExtEnv, it does something to ExtEnv"""
    env_write_api_registry[func.__name__] = get_function_schema(func)
    return func


class ExtEnv(BaseEnvironment, BaseModel):
    """External Env to integrate actual game environment"""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    action_space: spaces.Space[ActType] = Field(default_factory=spaces.Space, exclude=True)
    observation_space: spaces.Space[ObsType] = Field(default_factory=spaces.Space, exclude=True)

    def _check_api_exist(self, rw_api: Optional[str] = None):
        if not rw_api:
            raise ValueError(f"{rw_api} not exists")

    def get_all_available_apis(self, mode: str = "read") -> list[Any]:
        """get available read/write apis definition"""
        assert mode in ["read", "write"]
        if mode == "read":
            return env_read_api_registry.get_apis()
        else:
            return env_write_api_registry.get_apis()

    async def read_from_api(self, env_action: Union[str, EnvAPIAbstract]):
        """get observation from particular api of ExtEnv"""
        if isinstance(env_action, str):
            env_read_api = env_read_api_registry.get(api_name=env_action)["func"]
            self._check_api_exist(env_read_api)
            if is_coroutine_func(env_read_api):
                res = await env_read_api(self)
            else:
                res = env_read_api(self)
        elif isinstance(env_action, EnvAPIAbstract):
            env_read_api = env_read_api_registry.get(api_name=env_action.api_name)["func"]
            self._check_api_exist(env_read_api)
            if is_coroutine_func(env_read_api):
                res = await env_read_api(self, *env_action.args, **env_action.kwargs)
            else:
                res = env_read_api(self, *env_action.args, **env_action.kwargs)
        return res

    async def write_thru_api(self, env_action: Union[str, Message, EnvAPIAbstract, list[EnvAPIAbstract]]):
        """execute through particular api of ExtEnv"""
        res = None
        if isinstance(env_action, Message):
            self.publish_message(env_action)
        elif isinstance(env_action, EnvAPIAbstract):
            env_write_api = env_write_api_registry.get(env_action.api_name)["func"]
            self._check_api_exist(env_write_api)
            if is_coroutine_func(env_write_api):
                res = await env_write_api(self, *env_action.args, **env_action.kwargs)
            else:
                res = env_write_api(self, *env_action.args, **env_action.kwargs)

        return res

    @abstractmethod
    def reset(
        self,
        *,
        seed: Optional[int] = None,
        options: Optional[dict[str, Any]] = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Implement this to get init observation"""

    @abstractmethod
    def observe(self, obs_params: Optional[BaseEnvObsParams] = None) -> Any:
        """Implement this if you want to get partial observation from the env"""

    @abstractmethod
    def step(self, action: BaseEnvAction) -> tuple[dict[str, Any], float, bool, bool, dict[str, Any]]:
        """Implement this to feed a action and then get new observation from the env"""


class Environment(ExtEnv):
    """环境，承载一批角色，角色可以向环境发布消息，可以被其他角色观察到
    Environment, hosting a batch of roles, roles can publish messages to the environment, and can be observed by other roles
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    desc: str = Field(default="")  # 环境描述
    roles: dict[str, SerializeAsAny[BaseRole]] = Field(default_factory=dict, validate_default=True)
    member_addrs: Dict[BaseRole, Set] = Field(default_factory=dict, exclude=True)
    history: Memory = Field(default_factory=Memory)  # For debug
    context: Context = Field(default_factory=Context, exclude=True)

    def reset(
        self,
        *,
        seed: Optional[int] = None,
        options: Optional[dict[str, Any]] = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        pass

    def observe(self, obs_params: Optional[BaseEnvObsParams] = None) -> Any:
        pass

    def step(self, action: BaseEnvAction) -> tuple[dict[str, Any], float, bool, bool, dict[str, Any]]:
        pass

    @model_validator(mode="after")
    def init_roles(self):
        self.add_roles(self.roles.values())
        return self

    def add_role(self, role: BaseRole):
        """增加一个在当前环境的角色
        Add a role in the current environment
        """
        self.roles[role.name] = role
        role.set_env(self)
        role.context = self.context

    def add_roles(self, roles: Iterable[BaseRole]):
        """增加一批在当前环境的角色
        Add a batch of characters in the current environment
        """
        for role in roles:
            self.roles[role.name] = role

        for role in roles:  # setup system message with roles
            role.context = self.context
            role.set_env(self)

    def _find_sender_role(self, sent_from: str) -> Optional[BaseRole]:
        """Find the role that sent the message using multiple matching strategies."""
        if not sent_from:
            return None
        
        # Strategy 1: Match by role name
        for role in self.roles.values():
            if hasattr(role, 'name') and role.name == sent_from:
                return role
        
        # Strategy 2: Match by string representation (any_to_str)
        from metagpt.utils.common import any_to_str
        for role in self.roles.values():
            if any_to_str(role) == sent_from:
                return role
        
        # Strategy 3: Match by class name (handle cases like "__mp_main__.SimpleCoder")
        if "." in sent_from:
            class_name = sent_from.split(".")[-1]
            for role in self.roles.values():
                if role.__class__.__name__ == class_name:
                    return role
        
        return None
    
    def _format_sender(self, message: Message) -> str:
        """Format sender as Name(Role) or fallback to a reasonable representation."""
        if not message.sent_from:
            return "Unknown"
        
        sender_role = self._find_sender_role(message.sent_from)
        if sender_role:
            role_name = getattr(sender_role, 'name', 'Unknown')
            role_class = sender_role.__class__.__name__
            return f"{role_name}({role_class})"
        
        # Fallback: extract class name if possible
        if "." in message.sent_from:
            class_name = message.sent_from.split(".")[-1]
            return f"Unknown({class_name})"
        
        return message.sent_from
    
    def _format_recipients(self, message: Message) -> list[str]:
        """Format recipients as list of Name(Role) strings."""
        recipients = []
        for role, addrs in self.member_addrs.items():
            if is_send_to(message, addrs):
                role_name = getattr(role, 'name', 'Unknown')
                role_class = role.__class__.__name__
                recipients.append(f"{role_name}({role_class})")
        return recipients
    
    def _log_enhanced_message(self, message: Message) -> None:
        """Log agent message communication to enhanced logger."""
        try:
            from metagpt.enhanced_logger import enhanced_logger
            
            sender = self._format_sender(message)
            recipients = self._format_recipients(message)
            
            enhanced_logger.log_agent_message(
                sender=sender,
                recipients=recipients,
                content=message.content
            )
        except Exception as e:
            # Don't let logging errors interrupt the main flow
            logger.debug(f"Enhanced logging failed for agent message: {e}")

    def publish_message(self, message: Message, peekable: bool = True) -> bool:
        """
        Distribute the message to the recipients.
        In accordance with the Message routing structure design in Chapter 2.2.1 of RFC 116, as already planned
        in RFC 113 for the entire system, the routing information in the Message is only responsible for
        specifying the message recipient, without concern for where the message recipient is located. How to
        route the message to the message recipient is a problem addressed by the transport framework designed
        in RFC 113.
        """
        logger.debug(f"publish_message: {message.dump()}")
        
        # Enhanced logging - log agent message communication
        self._log_enhanced_message(message)
        
        # Route message to recipients
        found = False
        for role, addrs in self.member_addrs.items():
            if is_send_to(message, addrs):
                role.put_message(message)
                found = True
        
        if not found:
            logger.warning(f"Message no recipients: {message.dump()}")
        
        self.history.add(message)  # For debug
        return True

    async def run(self, k=1):
        """处理一次所有信息的运行
        Process all Role runs at once
        """
        for _ in range(k):
            futures = []
            for role in self.roles.values():
                if role.is_idle:
                    continue
                future = role.run()
                futures.append(future)

            if futures:
                await asyncio.gather(*futures)
            logger.debug(f"is idle: {self.is_idle}")

    def get_roles(self) -> dict[str, BaseRole]:
        """获得环境内的所有角色
        Process all Role runs at once
        """
        return self.roles

    def get_role(self, name: str) -> BaseRole:
        """获得环境内的指定角色
        get all the environment roles
        """
        return self.roles.get(name, None)

    def role_names(self) -> list[str]:
        return [i.name for i in self.roles.values()]

    @property
    def is_idle(self):
        """If true, all actions have been executed."""
        for r in self.roles.values():
            if not r.is_idle:
                return False
        return True

    def get_addresses(self, obj):
        """Get the addresses of the object."""
        return self.member_addrs.get(obj, {})

    def set_addresses(self, obj, addresses):
        """Set the addresses of the object"""
        self.member_addrs[obj] = addresses

    def archive(self, auto_archive=True):
        if auto_archive and self.context.kwargs.get("project_path"):
            git_repo = GitRepository(self.context.kwargs.project_path)
            git_repo.archive()
