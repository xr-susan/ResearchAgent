"""
CLI commands for ResearchAgent.

Provides interactive command-line interface for the research agent.
"""

import asyncio
import sys
from typing import Optional

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt

from backend.agents.research_agent import ResearchAgent
from backend.memory.conversation_memory import ConversationMemory
from backend.memory.storage import StorageManager
from backend.utils.logger import get_logger

logger = get_logger("cli")
console = Console()


class ResearchCLI:
    """Interactive CLI for ResearchAgent.

    Provides a rich terminal interface for interacting with
    the research agent in conversational mode.
    """

    def __init__(self):
        """Initialize the CLI."""
        self.storage: Optional[StorageManager] = None
        self.agent: Optional[ResearchAgent] = None
        self.memory: Optional[ConversationMemory] = None
        self.running = False

    async def setup(self):
        """Initialize storage, agent, and memory."""
        self.storage = StorageManager()
        await self.storage.connect()

        self.memory = ConversationMemory(self.storage)
        self.agent = ResearchAgent(memory=self.memory)

        console.print("[green]ResearchAgent initialized[/green]")

    async def cleanup(self):
        """Clean up resources."""
        if self.storage:
            await self.storage.close()

    def print_welcome(self):
        """Display welcome message."""
        welcome = """
# ResearchAgent

I can help you with:
- **Web Research** - Search for information on any topic
- **Document Analysis** - Analyze PDF, CSV, Excel files
- **Data Analysis** - Statistical analysis and visualizations
- **Report Generation** - Create structured research reports

## Commands
- Type your research question or task to get started
- `/new` - Start a new conversation
- `/history` - Show conversation history
- `/clear` - Clear current context
- `/help` - Show this help message
- `/quit` - Exit the application
"""
        console.print(Markdown(welcome))

    async def handle_command(self, command: str) -> bool:
        """Handle special commands.

        Args:
            command: User input starting with /

        Returns:
            True to continue, False to quit.
        """
        cmd = command.strip().lower()

        if cmd == "/quit" or cmd == "/exit":
            console.print("[yellow]Goodbye.[/yellow]")
            return False

        elif cmd == "/new":
            conv_id = await self.memory.start_conversation()
            console.print(f"[green]Started new conversation: {conv_id[:8]}...[/green]")

        elif cmd == "/history":
            summary = self.memory.get_conversation_summary()
            console.print(Panel(
                f"Conversation: {summary['conversation_id'][:8]}...\n"
                f"Messages: {summary['total_messages']}\n"
                f"User: {summary['user_messages']} | Assistant: {summary['assistant_messages']} | Tools: {summary['tool_calls']}",
                title="Conversation History",
            ))

        elif cmd == "/clear":
            await self.memory.clear_context()
            console.print("[yellow]Context cleared[/yellow]")

        elif cmd == "/help":
            self.print_welcome()

        elif cmd == "/tools":
            console.print(Panel(self.agent.get_tool_descriptions(), title="Available Tools"))

        else:
            console.print(f"[red]Unknown command: {command}[/red]")

        return True

    async def process_input(self, user_input: str) -> None:
        """Process user input and display response.

        Args:
            user_input: User's message.
        """
        with console.status("[bold green]Researching...", spinner="dots"):
            try:
                response = await self.agent.run(user_input)
            except Exception as e:
                console.print(f"[red]Error: {str(e)}[/red]")
                return

        # Display response
        console.print()
        console.print(Panel(
            Markdown(response),
            title="ResearchAgent",
            border_style="blue",
        ))
        console.print()

    async def run_interactive(self):
        """Run the interactive CLI loop."""
        await self.setup()
        self.print_welcome()
        self.running = True

        while self.running:
            try:
                user_input = Prompt.ask("\n[bold cyan]You[/bold cyan]")

                if not user_input.strip():
                    continue

                if user_input.startswith("/"):
                    self.running = await self.handle_command(user_input)
                    continue

                await self.process_input(user_input)

            except KeyboardInterrupt:
                console.print("\n[yellow]Use /quit to exit[/yellow]")
            except EOFError:
                break

        await self.cleanup()

    async def run_single_query(self, query: str) -> str:
        """Run a single query and return the result.

        Args:
            query: Research query.

        Returns:
            Agent response.
        """
        await self.setup()
        try:
            response = await self.agent.run(query)
            return response
        finally:
            await self.cleanup()


async def main():
    """CLI entry point."""
    cli = ResearchCLI()
    await cli.run_interactive()
