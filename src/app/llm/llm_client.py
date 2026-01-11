from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union
from enum import Enum

from app.utils.settings import SETTINGS


class LLMType(Enum):
    OPENAI = "OPENAI"
    TOYOTA = "TOYOTA"


class BaseLLMClient(ABC):
    """Abstract base class for LLM clients"""
    
    
    @abstractmethod
    def chat(self, messages: list, **kwargs) -> Any:
        """Send chat completion request"""
        pass
    
    @staticmethod
    def mcp_tools_reformating(is_remote: bool, tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        openai_tools: List[Dict[str, Any]] = []
        for t in tools:
            name = getattr(t, "name", None) or t.get("name")
            desc = getattr(t, "description", None) or t.get("description")
            schema = getattr(t, "inputSchema", None) or t.get("inputSchema")
            if not name or not schema:
                continue
            openai_tools.append(
                {
                    "name": name,
                    "type": "function",
                    "function": {
                        "name": name,
                        "description": desc or "",
                        "parameters": schema, 
                    },
                    "is_remote": is_remote,
                }
            )
        return openai_tools


class LLMClientFactory:
    """Factory class to create appropriate LLM client instances"""
    
    @staticmethod
    def create_client(
        **kwargs
    ) -> BaseLLMClient:
        """
        Create an LLM client based on type
        
        Args:
            llm_type: Type of LLM client to create
            model: Model name to use
            **kwargs: Additional arguments passed to client
            
        Returns:
            Instantiated LLM client
        """
        # Use settings defaults if not provided
        llm_type = SETTINGS.llm_type 
        
        if SETTINGS.llm_type == LLMType.OPENAI.value:
            from app.llm.azure_openai_client import AzureOpenAIClient
            return AzureOpenAIClient(model=SETTINGS.openai_llm_model, **kwargs)
        
        elif SETTINGS.llm_type == LLMType.TOYOTA.value:
            from app.llm.toyota_llm import ToyotaLLMClient
            return ToyotaLLMClient(model=SETTINGS.toyota_llm_model, **kwargs)
        
        else:
            raise ValueError(f"Unsupported LLM type: {llm_type}")

