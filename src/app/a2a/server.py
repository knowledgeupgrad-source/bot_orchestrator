from datetime import datetime
import json
import time
from uuid import uuid4
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
import asyncio
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.apps import A2AStarletteApplication
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import DatabaseTaskStore, TaskUpdater
from a2a.types import AgentCapabilities, AgentCard, AgentSkill, DataPart, Message, Part, Role, TaskState, TaskStatus, TaskStatusUpdateEvent
from a2a.utils import new_task
from dotenv import find_dotenv, load_dotenv
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import create_async_engine
from starlette.middleware.cors import CORSMiddleware
import uvicorn

from app.agent.run import main
from app.agent.state import AgentState
from app.llm.azure_openai_client import AzureOpenAIClient   
from app.llm.llm_client import LLMClientFactory
from app.utils.agent_registry import AgentRegistry
from app.utils.agent_trace import AgentTrace
from app.utils.enums import TemplateName, TemplateType
from app.utils.logging import logger
from app.utils.settings import SETTINGS
from app.utils.template_manager import TemplateManager
from app.utils.workflow_service import WorkflowService
from app.utils.agent_output_message import AgentMessage, AgentResponse, transform_results_to_agent_message


# Load .env before importing modules that read environment variables
_dotenv_path = find_dotenv(usecwd=True)
if _dotenv_path:
    load_dotenv(_dotenv_path)
else:
    print("Warning: .env file not found (continuing without it)")

class OrchestratorAgentExecutor(AgentExecutor):
    def __init__(self, agent_name: str):

        self.agent_registry = AgentRegistry(agent_name=agent_name)
        self.agent_description = self.agent_registry.get_description()
        self.skills = self.agent_registry.get_skills()

        self.public_agent_card = AgentCard(
            name='Orchestrator Agent Server',
            description=self.agent_description,
            url=self.agent_registry.get_url(),
            version='1.0.0',
            default_input_modes=['text'],
            default_output_modes=['text'],
            capabilities=AgentCapabilities(streaming=True),
            skills=self.skills,
            supports_authenticated_extended_card=False
        )
        self.agent_trace = None

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        try:
            method = context.call_context.state.get("method").strip()
            logger.info(f"Received request with context_id: {context.context_id}, task_id: {context.task_id}, method: {method}")
        
            state = await self._create_agent_state(context, event_queue)

            if not state.user_id or (state.user_roles and len(state.user_roles) == 0):
                raise ValueError("User ID or User Roles could not be retrieved. Unauthorized access.")
            
            self.agent_trace = AgentTrace(state.context_id, state.agent_name, user_id=state.user_id)
            state = self.agent_trace.load_agent_session(state)
            

            state.conversation.append({"role": "user", "content": state.input})

            if not state.is_new_conversation:
                state.current_state.get("messages", []).append({"role": "user", "content": state.input})
                state.messages = state.current_state.get("messages", [])
                state.selected_skill = state.current_state.get("selected_skill", "")
            else:    
                state.selected_skill, state.workflow_id = self._classify_skill(state.input, user_roles=state.user_roles)

            conversation_name=f"Chat {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            self.agent_trace.save_agent_session(state, conversation_name)    

            if method == "message/stream":
                await self._run_workflow_with_streaming(state)
            else:
                await self._run_workflow_without_streaming(state)

        except Exception as e:
            logger.error(f"Error during execution: {e}", stack_info=True)
            raise e

    async def _create_agent_state(self, context, event_queue):
        
        #is_workflow=False
        workflow_id=None
        #Reference for future use.
        # if len(context.message.parts) > 0 and isinstance(context.message.parts[0].root, DataPart):
        #     data = context.message.parts[0].root.data
        #     is_workflow = data.get("is_workflow", False)
        #     workflow_id = data.get("workflow_id", None)

        state = AgentState.get_initial_state()
        state.token = context.call_context.state.get("headers", {}).get("authorization", "").replace("Bearer ", "").strip()
        state.user_id, state.user_roles = await self.get_user_info(state.token)
        user_input = context.get_user_input()
        state.input = user_input.strip() if user_input else ""

        if context.message and context.message.parts and len(context.message.parts) > 0:
            part_root = context.message.parts[0].root
            if isinstance(part_root, DataPart):
                state.input_data = part_root.data
                if "input" in state.input_data:
                    state.input = state.input_data["input"]
            else:
                state.input_data = {}
        
        state.context_id = context.context_id
        state.task_id = context.task_id
        state.event_queue=event_queue
        state.is_new_conversation = False
        state.agent_name = SETTINGS.app_name
        state.agent_description = self.agent_description
        state.agent_skills=self.skills
        state.workflow_id = workflow_id
        self._validate_state(state)
        
        #Task logic is still left so that we can track task status in future. Specially for task based multi-turn interactions.
        task = context.current_task
        if not task:
            state.is_new_conversation=True
            task = new_task(context.message)
            await event_queue.enqueue_event(task)

        state.task = task
        return state

    def _cast_to_agent_state(self, result: dict, base: AgentState) -> AgentState:
        for k, v in result.items():
            if hasattr(base, k):
                setattr(base, k, v)
        return base

    def _create_message(self, agent_state:AgentState, for_partial: bool = False) -> Message:
        metadata = {}
        part = None
        if for_partial:
            part = Part(root=DataPart(kind="data", data={"status": agent_state.status}, metadata=metadata))
        else:
            metadata = agent_state.sub_agent_events if agent_state.sub_agent_events else {}
            metadata[agent_state.agent_name] = agent_state.event_log
            try:
                if "result" in agent_state.output:
                    raise ValueError("Older message format detected, transforming to AgentMessage.")
                agent_message = AgentMessage(**agent_state.output)
            except Exception as e:
                logger.warning(f"Failed to parse agent_state.output to AgentMessage: {e}")
                agent_message = transform_results_to_agent_message(agent_state.output)
            
            agent_response=AgentResponse.create(data=agent_message, metadata=metadata)
            #part = Part(root=DataPart(kind="data", data=agent_state.output, metadata=metadata))

        
        message = Message( role=Role.agent,
            message_id=str(uuid4()),
            task_id=agent_state.task_id,
            context_id=agent_state.context_id,
            parts = [agent_response.root]
        )
        return message   

    async def _run_workflow_without_streaming(self, agent_state: AgentState):
        result = await main(agent_state)
        agent_state = self._cast_to_agent_state(result, agent_state)        
        agent_state.mark_end()

        message = self._create_message(agent_state)
        final=False
        if not agent_state.task_state == TaskState.input_required.value:
            final=True

        await agent_state.event_queue.enqueue_event(
                    TaskStatusUpdateEvent(
                        status=TaskStatus(
                            state=agent_state.task_state,
                            message=message,
                        ),
                        message=message,
                        final=final,
                        context_id=agent_state.context_id,
                        task_id=agent_state.task_id,
                    )
            )
        task_updater = TaskUpdater(agent_state.event_queue, agent_state.task_id, agent_state.context_id)
        await task_updater.update_status( agent_state.task_state, message, final=final)

        agent_state.conversation.append({"role": "agent", "content": agent_state.output})
        agent_state.current_state = {"messages": agent_state.messages, "selected_skill": agent_state.selected_skill}
        self.agent_trace.save_agent_session(agent_state) 

    async def _run_workflow_with_streaming(self, agent_state: AgentState):
        async def stream_callback(partial_state: AgentState, task: any):
            logger.debug(f"Streaming partial state for task_id: {task.id}, context_id: {task.context_id}")

            if isinstance(partial_state, dict):
                fragment = next(iter(partial_state.values()))
                agent_state.status = fragment.get("status", agent_state.status)

            logger.debug(f"Streaming partial state current status:{agent_state.status}")
            message = self._create_message(agent_state, for_partial=True)
            updater = TaskUpdater(agent_state.event_queue, task.id, task.context_id)
            await updater.update_status(state = TaskState.working, message = message, final=False, timestamp = str(time.time()))
            #await agent_state.event_queue.enqueue_event(message)

        agent_state.call_back_function = stream_callback
        logger.info(f"Starting streaming execution for : prompt={agent_state.input}, token={agent_state.token}, task={agent_state.task}, stream_callback={stream_callback}")
        result = await main(agent_state)
        agent_state = self._cast_to_agent_state(result, agent_state)        
        agent_state.mark_end()
        message = self._create_message(agent_state)
        agent_state.conversation.append({"role": "agent", "content": agent_state.output})
        agent_state.current_state = {"messages": agent_state.messages}
        self.agent_trace.save_agent_session(agent_state) 

        updater = TaskUpdater(agent_state.event_queue, agent_state.task_id, agent_state.context_id)
        await updater.update_status( TaskState.completed, message, final=True)

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise ValueError('cancel not supported')

    def _validate_state(self, state: AgentState) -> None:
        token = state.token.replace("Bearer ", "").strip()
        if not state.input and len(state.input_data.keys())==0:
            raise ValueError("Input payload is missing or empty.")

        if not token:
            raise ValueError("Authorization token is missing or empty.")
    
    def _classify_skill(self, prompt: str, user_roles: List[str]) -> str:
        tm = TemplateManager(SETTINGS.app_name)
        workflow_manager = WorkflowService()
        workflows = workflow_manager.get_all_workflows(user_roles=tuple(user_roles))

        # Extract skill descriptions from self.skills (AgentSkill objects)
        skill_names = [skill.name for skill in self.skills]
        
        SKILL_CLASSIFIER_PROMPT = tm.render_template(
            TemplateType.PROMPT, 
            TemplateName.AGENT_SKILLS_CLASSIFIER_PROMPT,
            capabilities=skill_names,
            workflows=json.dumps(workflows)
        )
        
        client = LLMClientFactory.create_client()
        messages = [{'role': 'system', 'content': SKILL_CLASSIFIER_PROMPT}, {'role': 'user', 'content': prompt}]
        logger.info(f"Skill Prompt")
        logger.info(f"{messages}")
        response = client.chat(messages)
        skill = response.get("skill","").strip()
        workflow_id = response.get("workflow_id", None)
        if skill in ['capability', 'workflow', 'other']:
            return skill,workflow_id
        else:
            raise ValueError(f'Unrecognized skill: {skill}')
        
    async def get_user_info(self, token: str) -> str:
        async with asyncio.timeout(100):
            async with streamablehttp_client(SETTINGS.cubeassist_mcp_server_url) as (read, write, _):
                async with ClientSession(read, write) as mcp_session:
                    await mcp_session.initialize()
                    result = await mcp_session.call_tool(
                        "get_user_info",
                        {"token": token}
                    )
                    user_info = json.loads(result.content[0].text)
                    user_id = user_info.get("output", {}).get("data", {}).get("userId")
                    user_roles = user_info.get("output", {}).get("data", {}).get("roles", [])
                    if not user_id or (user_roles and len(user_roles) == 0):
                        raise ValueError("User ID or User Roles could not be retrieved. Unauthorized access.")
                    return user_id, user_roles



if __name__ == '__main__':
    db_url = f"postgresql+asyncpg://{SETTINGS.agent_db_user}:{SETTINGS.agent_db_password}@{SETTINGS.agent_db_host}:{SETTINGS.agent_db_port}/postgres"
    engine = create_async_engine(db_url)

    agent_name = SETTINGS.app_name
    agent_executor = OrchestratorAgentExecutor(agent_name=agent_name)
    request_handler = DefaultRequestHandler( agent_executor=agent_executor, task_store=DatabaseTaskStore(engine=engine))
    server_app = A2AStarletteApplication(agent_card=agent_executor.public_agent_card, http_handler=request_handler)
    app = server_app.build()
    app.add_middleware( CORSMiddleware,
    allow_origins=["*"],  # Or specify allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
    uvicorn.run(app, host='0.0.0.0', port=8080)
