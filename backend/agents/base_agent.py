"""
Base agent class for ResearchAgent.

Implements the core ReAct (Reasoning + Acting) loop pattern.
Provides tool management, error recovery, and LLM integration.
"""

import json
from abc import ABC, abstractmethod
from typing import Any, Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI

from backend.memory.conversation_memory import ConversationMemory
from backend.utils.config import settings
from backend.utils.logger import get_logger

logger = get_logger("base_agent")


class BaseAgent(ABC):
    """Abstract base agent implementing the ReAct framework.

    The agent follows a Think → Act → Observe loop:
    1. Think: Analyze the task and plan the approach
    2. Act: Select and execute the appropriate tool
    3. Observe: Process the tool's output and decide next steps
    """

    def __init__(
        self,
        memory: ConversationMemory,
        tools: list[BaseTool],
        system_prompt: str = "",
        model_name: Optional[str] = None,
        temperature: float = 0.7,
        max_iterations: int = 15,
    ):
        """Initialize the base agent.

        Args:
            memory: Conversation memory manager.
            tools: List of available tools.
            system_prompt: System prompt for the agent.
            model_name: LLM model name. Defaults to settings.
            temperature: LLM temperature.
            max_iterations: Maximum ReAct loop iterations.
        """
        self.memory = memory
        self.tools = {tool.name: tool for tool in tools}
        self.tool_list = tools
        self.system_prompt = system_prompt or self._default_system_prompt()
        self.max_iterations = max_iterations

        self.model_name = model_name or settings.default_model
        self.llm = self._create_llm(temperature)
        self.llm_with_tools = self.llm.bind_tools(tools) if self.llm else None

        logger.info(f"Initialized {self.__class__.__name__} with {len(tools)} tools")

    def _create_llm(self, temperature: float):
        """Create the configured chat model, or defer until credentials are available."""
        provider = settings.llm_provider.lower()

        if provider == "anthropic":
            if not settings.anthropic_api_key:
                logger.warning("ANTHROPIC_API_KEY is not configured; agent calls will return a setup message")
                return None
            return ChatAnthropic(
                model=self.model_name,
                temperature=temperature,
                api_key=settings.anthropic_api_key,
            )

        if not settings.openai_api_key:
            logger.warning("OPENAI_API_KEY is not configured; agent calls will return a setup message")
            return None

        return ChatOpenAI(
            model=self.model_name,
            temperature=temperature,
            api_key=settings.openai_api_key,
        )

    def _default_system_prompt(self) -> str:
        """Get the default system prompt."""
        return """You are ResearchAgent, a practical research assistant.

Use tools when they add evidence. Keep answers direct, cite sources when you use them,
and separate confirmed facts from interpretation or uncertainty.
"""

    async def run(self, user_input: str, stream: bool = False) -> str:
        """Execute the ReAct loop to process user input.

        Args:
            user_input: User's message or task description.
            stream: Whether to stream the response.

        Returns:
            Agent's final response.
        """
        logger.info(f"Agent processing: {user_input[:100]}...")
        await self.memory.add_user_message(user_input)

        if not self.llm_with_tools:
            final_response = (
                "The agent is running, but no LLM API key is configured yet. "
                "Add OPENAI_API_KEY or ANTHROPIC_API_KEY to your .env file, then restart the server."
            )
            await self.memory.add_assistant_message(final_response)
            return final_response

        messages = self._build_messages(user_input)

        # ReAct loop
        iterations = 0
        final_response = ""

        while iterations < self.max_iterations:
            iterations += 1
            logger.debug(f"ReAct iteration {iterations}/{self.max_iterations}")

            try:
                # Call LLM
                response = await self.llm_with_tools.ainvoke(messages)

                if isinstance(response, AIMessage):
                    # Check for tool calls
                    if response.tool_calls:
                        # Process tool calls
                        tool_results = await self._process_tool_calls(response.tool_calls)

                        # Add assistant message with tool calls to conversation
                        messages.append(response)

                        # Add tool results to messages
                        for result in tool_results:
                            messages.append(ToolMessage(
                                content=result["output"],
                                tool_call_id=result["tool_call_id"],
                            ))

                        # Continue the loop to let LLM process tool results
                        continue
                    else:
                        # No tool calls - this is the final response
                        final_response = response.content
                        break
                else:
                    final_response = str(response)
                    break

            except Exception as e:
                logger.error(f"Error in ReAct iteration {iterations}: {e}")
                if iterations >= self.max_iterations:
                    final_response = f"I encountered an error while processing your request: {str(e)}"
                else:
                    # Retry with error context
                    messages.append(SystemMessage(
                        content=f"Error occurred: {str(e)}. Please try a different approach."
                    ))
                    continue

        if not final_response:
            final_response = "I was unable to complete the task within the allowed iterations. Please try breaking your request into smaller parts."

        # Save assistant response to memory
        await self.memory.add_assistant_message(final_response)

        # Extract and save key facts to long-term memory
        await self.memory.extract_and_save_key_facts()

        logger.info(f"Agent completed in {iterations} iterations")
        return final_response

    async def _process_tool_calls(self, tool_calls: list[dict]) -> list[dict]:
        """Process a list of tool calls.

        Args:
            tool_calls: List of tool call dictionaries from LLM.

        Returns:
            List of tool result dictionaries.
        """
        results = []

        for tool_call in tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            tool_call_id = tool_call["id"]

            logger.info(f"Executing tool: {tool_name} with args: {json.dumps(tool_args, default=str)[:200]}")

            if tool_name not in self.tools:
                error_msg = f"Unknown tool: {tool_name}. Available tools: {', '.join(self.tools.keys())}"
                logger.warning(error_msg)
                results.append({"tool_call_id": tool_call_id, "output": error_msg})
                continue

            try:
                tool = self.tools[tool_name]

                # Execute tool
                if hasattr(tool, '_arun'):
                    output = await tool._arun(**tool_args)
                else:
                    output = tool.run(tool_args)

                # Save tool interaction to memory
                await self.memory.add_tool_message(tool_name, str(output)[:2000], tool_call_id)

                results.append({
                    "tool_call_id": tool_call_id,
                    "output": str(output)[:5000],  # Truncate very long outputs
                })

                logger.info(f"Tool {tool_name} completed successfully")

            except Exception as e:
                error_msg = f"Tool {tool_name} failed: {str(e)}"
                logger.error(error_msg)
                results.append({"tool_call_id": tool_call_id, "output": error_msg})

        return results

    def _build_messages(self, user_input: str) -> list:
        """Build the message list for LLM invocation.

        Args:
            user_input: Current user input.

        Returns:
            List of messages for the LLM.
        """
        messages = [SystemMessage(content=self.system_prompt)]

        # Add conversation history from memory
        context = self.memory.get_context_messages(limit=30)
        for msg in context[:-1]:  # Exclude the last user message (already adding it)
            role = msg["role"]
            content = msg["content"]
            if role == "user":
                messages.append(HumanMessage(content=content))
            elif role == "assistant":
                messages.append(AIMessage(content=content))
            elif role == "tool":
                messages.append(ToolMessage(
                    content=content,
                    tool_call_id=msg.get("tool_call_id", ""),
                ))

        # Add current user input
        messages.append(HumanMessage(content=user_input))

        return messages

    def get_tool_descriptions(self) -> str:
        """Get formatted descriptions of all available tools.

        Returns:
            Formatted tool description string.
        """
        descriptions = []
        for name, tool in self.tools.items():
            descriptions.append(f"- **{name}**: {tool.description}")
        return "\n".join(descriptions)

    @abstractmethod
    async def plan(self, task: str) -> list[str]:
        """Plan the steps to accomplish a task.

        Args:
            task: Task description.

        Returns:
            List of planned steps.
        """
        pass
