import asyncio
import json
import time
from functools import wraps
from typing import List
from a2a.types import Part

from app.agent.state import AgentState, CubeAssistBaseState
from app.utils.agent_trace import AgentTrace
from app.utils.logging import logger


def timed(log_label: str):
    def decorator(func):
        if asyncio.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                start = time.time()
                try:
                    result = await func(*args, **kwargs)
                    return result
                finally:
                    duration = time.time() - start
                    state = next((a for a in args if isinstance(a, CubeAssistBaseState)), None)
                    if state:
                        if state:
                            msg = f"{log_label} - {state.selected_tool} for step - {state.step} execution time: {duration:.2f} seconds"
                        else:
                            msg = f"{log_label} for step - {state.step} execution time: {duration:.2f} seconds"
                        state.event_log.append(msg)
                    else:
                        msg = f"{log_label} execution time: {duration:.2f} seconds"
                    logger.debug({'message': msg})
            return async_wrapper
        else:
            @wraps(func)
            def wrapper(self, *args, **kwargs):
                start = time.time()
                try:
                    result = func(self, *args, **kwargs)
                    return result
                finally:
                    duration = time.time() - start
                    state = next((a for a in args if isinstance(a, CubeAssistBaseState)), None)
                    if state: 
                        msg = f"{log_label} for step - {state.step} execution time: {duration:.2f} seconds"
                        state.event_log.append(msg)
                    else:
                        msg = f"{log_label} execution time: {duration:.2f} seconds"
                    logger.debug({'message': msg})
            return wrapper
    return decorator

def trace_agent_interaction(log_label: str):
    def decorator(func):
        @wraps(func)
        async def wrapper(self, state: AgentState, selected_agent: any, agent_input: List[Part], *args, **kwargs):
            start = time.time()
            result = None
            try:
                result = await func(self, state, selected_agent, agent_input, *args, **kwargs)
                return result
            finally:
                duration = time.time() - start
                input_payload_list = []
                for payload_item in agent_input:
                    payload_item_dump=payload_item.model_dump()
                    if payload_item_dump.get('data',{}).get('token'):
                        payload_item_dump['data']['token'] = "****"
                    input_payload_list.append(payload_item_dump)
                input_payload=json.dumps(input_payload_list)
                msg = f"{log_label} for step - {state.step} executing agent {selected_agent.get("name")} , paramaters: {input_payload} execution time: {duration:.2f} seconds"
                agent_trace = AgentTrace(context_id=state.context_id, agent_name=state.agent_name)
                agent_trace.save_agent_interaction_trace(state.task_id, input_payload, json.dumps(state.output), state.status, duration , selected_agent.get("name"))
                state.event_log.append(msg)
                logger.debug({'message': msg, 'agent_output': result})
        return wrapper
    return decorator

def trace_mcp_interaction(log_label: str):
    def decorator(func):
        @wraps(func)
        async def wrapper(self, state: AgentState, tool_input: any, is_remote: bool, *args, **kwargs):
            start = time.time()
            result = None
            try:
                result = await func(self, state, tool_input, is_remote, *args, **kwargs)
                return result
            finally:
                duration = time.time() - start
                satinized_input = tool_input
                satinized_input['token'] = "****"  # Mask sensitive token info
                msg = f"{log_label} for step - {state.step} executing tool {state.selected_tool} , paramaters: {satinized_input} execution time: {duration:.2f} seconds"
                agent_trace = AgentTrace(context_id=state.context_id, agent_name=state.agent_name)
                agent_trace.save_agent_mcp_interaction_trace(state.task_id, state.selected_tool, satinized_input, result , state.status, duration)
                state.event_log.append(msg)
                logger.debug({'message': msg, 'tool_output': result})
        return wrapper
    return decorator
