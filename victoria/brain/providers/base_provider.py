"""
Victoria - Base AI Provider Interface
All AI model providers must implement this interface.
This makes Victoria's brain truly pluggable - add any model with a simple class.
"""

from abc import ABC, abstractmethod
from typing import Any, Optional
from dataclasses import dataclass, field


@dataclass
class ToolParameter:
    """A parameter for a tool function."""
    name: str
    type: str          # "string", "integer", "number", "boolean", "array", "object"
    description: str
    required: bool = True
    enum: Optional[list] = None
    default: Any = None


@dataclass
class ToolDefinition:
    """Definition of a tool that the AI can call."""
    name: str
    description: str
    parameters: list[ToolParameter] = field(default_factory=list)
    category: str = "general"          # For organization
    dangerous: bool = False            # Requires confirmation
    # When set (e.g. for MCP tools), providers pass this JSON schema through
    # to the model verbatim instead of building one from `parameters`.
    raw_schema: Optional[dict] = None


@dataclass
class ToolCall:
    """A tool call request from the AI model."""
    name: str
    arguments: dict[str, Any]
    id: Optional[str] = None


@dataclass
class Message:
    """A message in the conversation."""
    role: str              # "system", "user", "assistant", "tool"
    content: str
    tool_calls: Optional[list[ToolCall]] = None
    tool_call_id: Optional[str] = None
    name: Optional[str] = None  # Tool name for tool results


@dataclass
class BrainResponse:
    """Response from the AI brain."""
    text: str                                    # The text response to speak
    tool_calls: list[ToolCall] = field(default_factory=list)  # Tools to execute
    raw_response: Any = None                     # Raw provider response
    model_used: str = ""
    tokens_used: int = 0


class BaseProvider(ABC):
    """
    Abstract base class for all AI model providers.

    To add a new provider:
      1. Create a new file in victoria/brain/providers/
      2. Implement this interface
      3. Add it to the config victoria.yaml
      4. The router will automatically pick it up
    """

    def __init__(self, model_config: dict):
        """
        Initialize the provider.

        Args:
            model_config: Configuration dict from victoria.yaml
        """
        self.model_name: str = model_config.get("model", "")
        self.temperature: float = model_config.get("temperature", 0.7)
        self.max_tokens: int = model_config.get("max_tokens", 4096)
        self.api_key: Optional[str] = model_config.get("api_key")
        self.base_url: Optional[str] = model_config.get("base_url")
        self.config = model_config

    @abstractmethod
    def chat(
        self,
        messages: list[Message],
        tools: Optional[list[ToolDefinition]] = None,
        system_prompt: Optional[str] = None,
    ) -> BrainResponse:
        """
        Send a chat message and get a response.

        Args:
            messages: Conversation history
            tools: Available tools for function calling
            system_prompt: System prompt (personality)

        Returns:
            BrainResponse with text and optional tool calls
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this provider is available and properly configured."""
        pass

    def get_name(self) -> str:
        """Get a human-readable name for this provider."""
        return f"{self.__class__.__name__}({self.model_name})"
