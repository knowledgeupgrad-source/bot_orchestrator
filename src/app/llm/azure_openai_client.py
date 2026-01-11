import json
from typing import Any, Dict, List

from openai import AzureOpenAI

from app.llm.llm_client import BaseLLMClient
from app.utils.settings import SETTINGS


class AzureOpenAIClient(BaseLLMClient):
    def __init__(self, api_version: str = None, api_key: str = None, base_url: str = None, model: str = None):
        self.client = AzureOpenAI(
            azure_endpoint=base_url or SETTINGS.openai_endpoint,
            api_key=api_key or SETTINGS.openai_api_key,
            api_version=api_version or SETTINGS.openai_api_version,
        )
        self.model = model or SETTINGS.openai_llm_model

    def chat(self, messages: List[Dict[str, Any]], model=None, **kwargs) -> str:
        model = model or self.model
        resp = self.client.chat.completions.create(model=model, messages=messages, **kwargs)
        return json.loads(resp.choices[0].message.content) or {}

    def responses(self, messages: List[Dict[str, Any]], model=None, **kwargs) -> any:
        model = model or self.model
        resp = self.client.responses.create(model=model, input=messages, **kwargs)
        return resp

    def invoke(self, prompt: str, **kwargs) -> str:
        messages = [{"role": "user", "content": prompt}]
        return self.chat(messages, **kwargs).content
    