import json
import time
from asyncio import Task
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, List, Optional

from a2a.server.events import EventQueue
from a2a.types import TaskState

from app.utils.settings import SETTINGS


@dataclass
class CubeAssistBaseState:
    """Base class containing core conversation fields"""
    input: Optional[str] = None
    output: Optional[str] = None
    token: Optional[str] = None
    event_log: Optional[List[str]] = field(default_factory=list)
    context_id: Optional[str] = None
    input_data: Optional[Dict[str, Any]] = field(default_factory=dict)
    is_new_conversation: bool = True


@dataclass
class AgentState(CubeAssistBaseState):
    """Agent state extending CubeAssist base state"""
    # for workflow state
    messages: List[Dict[str, Any]] = field(default_factory=list)
    sub_agent_events: Optional[Dict[str, Any]] = field(default_factory=dict)
    available_agents: Optional[Dict[str, Any]] = field(default_factory=dict)
    selected_agent: str = ""
    available_tools: Optional[List[Dict[str, Any]]] = field(default_factory=list)
    agent_tools: Optional[List[str]] = field(default_factory=list)
    selected_tool: Optional[str] = None
    results: List[Dict[str, Any]] = field(default_factory=list)
    step: int = 0
    seen_decisions: Optional[Any] = None
    status: str = "in_progress"
    filter: Optional[Dict[str, Any]] = None
    agent_name: Optional[str] = None
    
    # for agent context
    task_id: Optional[str] = None
    task: Optional[Task] = None
    task_state: Optional[str] = None
    event_queue: EventQueue = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    call_back_function: Optional[Callable] = None
    conversation: Optional[list] = field(default_factory=list)
    current_state: Optional[Dict[str, Any]] = field(default_factory=dict)
    
    # New workflow-related attributes
    selected_skill: Optional[str] = None
    agent_description: Optional[str] = None
    agent_skills: Optional[Dict[str, Any]] = field(default_factory=dict)
    workflow_id: Optional[str] = None
    user_roles: Optional[List[str]] = field(default_factory=lambda: [])
    user_id: Optional[str] = None

    def __post_init__(self):
        """Initialize default mutable values"""
        if self.event_log is None:
            self.event_log = []

    def mark_end(self):
        self.end_time = time.time()

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def get_initial_state():
        return AgentState(
            messages=[],
            input=None,
            output={},  # Changed from json.dumps({}) to {}
            event_log=[],
            sub_agent_events={},
            available_agents={},
            selected_agent="",
            available_tools=[],
            agent_tools=[],
            selected_tool=None,
            results=[],
            token="",
            step=0,
            seen_decisions=set(),
            status="in_progress",
            agent_name=SETTINGS.app_name,
            context_id=None,
            task_state=TaskState.completed.value,
            is_new_conversation=True,
            conversation=[],
            current_state={},
            workflow_id=None,
            user_roles=["CUBE_E2E_ADMIN"],
            user_id=None,
            selected_skill=None,
            agent_description=None,
            agent_skills={},
            start_time=time.time()
        )
