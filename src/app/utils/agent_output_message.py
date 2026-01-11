from typing import List, Optional, Union, Any, Dict, Literal
from pydantic import BaseModel, Field
from a2a.types import Part, DataPart
import json


class SelectOption(BaseModel):
    label: str
    value: str


class DropdownField(BaseModel):
    type: Literal["dropdown"] = "dropdown"
    label: str
    name: str
    options: List[SelectOption]
    required: Optional[bool] = False


FormField = DropdownField  # Currently only dropdown is supported


class FormBlock(BaseModel):
    type: Literal["form"] = "form"
    name: str  # Changed from 'id' to 'name'
    submitLabel: str
    fields: List[FormField]


class TextBlock(BaseModel):
    type: Literal["text"] = "text"
    text: str


class ActionItem(BaseModel):
    action: Union[bool, Literal["true"], Literal["false"]]
    type: Literal["message"] = "message"
    label: str
    value: str


class TableBlock(BaseModel):
    type: Literal["table"] = "table"
    data: List[Dict[str, Any]]
    filter: Optional[Dict[str, Any]] = None


class RecommendationsBlock(BaseModel):
    type: Literal["recommendations"] = "recommendations"
    name: str  # Added name field as requested
    actions: List[ActionItem]


# New classes for capabilities
class CapabilityExample(BaseModel):
    label: str
    value: str


class CapabilityCategory(BaseModel):
    title: str
    description: Optional[str] = None


class CapabilitiesBlock(BaseModel):
    type: Literal["capabilities"] = "capabilities"
    capabilities: List[CapabilityCategory]


ContentBlock = Union[TextBlock, TableBlock, FormBlock, RecommendationsBlock, CapabilitiesBlock]


class Workflow(BaseModel):
    name: str
    id: Optional[str] = None
    cancelationText: Optional[str] = None


class AgentMessage(BaseModel):
    disableUserInput: Optional[bool] = False
    summary: str
    workflow: Optional[Workflow] = None
    content: Optional[List[ContentBlock]] = None
    subagent_environment: Optional[str] = None
    subagent_endpoint: Optional[str] = None


class AgentResponse(BaseModel):
    root: Part

    @classmethod
    def create(cls, data: AgentMessage, metadata: Any) -> "AgentResponse":
        data_part = DataPart(kind="data", data=data.model_dump(), metadata=metadata)
        root_part = Part(root=data_part)
        return cls(root=root_part)


def transform_results_to_agent_message(output_data: dict) -> AgentMessage:
    """Transform agent_state.output to AgentMessage format dynamically"""
    
    # Extract summary
    summary = output_data.get("summary", "")
    
    content_blocks = []

    # Transform result to table block
    if "result" in output_data and output_data["result"]:
        table_block = TableBlock(
            type="table",
            data=output_data["result"],
            filter=output_data["filter"] if "filter" in output_data else None
        )
        content_blocks.append(table_block)
    
    # Add recommendations block if present
    if "recommendations" in output_data and output_data["recommendations"]:
        recommendations_data = output_data["recommendations"]
        if isinstance(recommendations_data, dict) and "actions" in recommendations_data:
            recommendations_block = RecommendationsBlock(
                type="recommendations",
                name=recommendations_data.get("name", "recommendations"),
                actions=[ActionItem(**action) for action in recommendations_data["actions"]]
            )
            content_blocks.append(recommendations_block)
    
    # Add capabilities block if present
    if "capabilities" in output_data and output_data["capabilities"]:
        capabilities_data = output_data["capabilities"]
        if isinstance(capabilities_data, list):
            capabilities_block = CapabilitiesBlock(
                type="capabilities",
                capabilities=[CapabilityCategory(**category) for category in capabilities_data]
            )
            content_blocks.append(capabilities_block)
    
    # Extract workflow info
    workflow = None
    workflow_data = output_data.get("workflow")
    if workflow_data:
        workflow = Workflow(name=workflow_data.get("name", "Workflow"))
    
    # Create AgentMessage
    agent_message = AgentMessage(
        disableUserInput=output_data.get("disableUserInput", False),
        summary=summary,
        workflow=workflow,
        content=content_blocks,
        subagent_environment=output_data.get("environment"),
        subagent_endpoint=output_data.get("api_endpoint")
    )
    
    return agent_message