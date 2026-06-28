"""
Research agent for ResearchAgent.

Specialized agent for conducting research tasks with goal decomposition,
adaptive tool selection, and multi-source information synthesis.
"""

import json
from typing import Any, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import BaseTool

from backend.agents.base_agent import BaseAgent
from backend.memory.conversation_memory import ConversationMemory
from backend.tools import (
    DataAnalysisTool,
    FileAnalyzerTool,
    ReportGeneratorTool,
    SearchTool,
    WebScraperTool,
)
from backend.utils.logger import get_logger

logger = get_logger("research_agent")


class ResearchAgent(BaseAgent):
    """Specialized agent for research tasks.

    Extends BaseAgent with:
    - Goal decomposition for complex research tasks
    - Adaptive tool selection based on task type
    - Multi-source information synthesis
    - Research-specific system prompts and planning
    """

    def __init__(
        self,
        memory: ConversationMemory,
        tools: Optional[list[BaseTool]] = None,
        model_name: Optional[str] = None,
    ):
        """Initialize the research agent.

        Args:
            memory: Conversation memory manager.
            tools: List of research tools. If None, uses default tool set.
            model_name: LLM model name.
        """
        # Use default research tools if none provided
        if tools is None:
            storage = memory.storage
            tools = [
                SearchTool(storage=storage),
                WebScraperTool(),
                FileAnalyzerTool(),
                DataAnalysisTool(),
                ReportGeneratorTool(),
            ]

        super().__init__(
            memory=memory,
            tools=tools,
            system_prompt=self._research_system_prompt(),
            model_name=model_name,
        )

    def _research_system_prompt(self) -> str:
        """Get the research-specific system prompt."""
        return """You are ResearchAgent, a research assistant focused on clear sourcing and careful analysis.

## Your Core Capabilities

1. **Web Search**: Find current information, data, news, and statistics
2. **Web Scraping**: Extract detailed content from specific web pages
3. **Document Analysis**: Parse and analyze PDF, CSV, Excel, and text files
4. **Data Analysis**: Perform statistical analysis, trend detection, and data visualization
5. **Report Generation**: Create structured research reports in Markdown or PDF

## Research Method

### 1. Understand the Research Question
- Clarify the scope and objectives
- Identify key terms and concepts
- Determine what types of sources are needed

### 2. Gather Information
- Search for relevant data from multiple queries
- Scrape authoritative sources for detailed information
- Analyze any provided documents or datasets
- Cross-reference information across sources

### 3. Analyze and Synthesize
- Identify patterns, trends, and insights
- Compare different perspectives and data points
- Evaluate source reliability
- Draw evidence-based conclusions

### 4. Present Findings
- Structure findings logically
- Include data and statistics to support points
- Cite all sources
- Provide actionable recommendations

## Tool Usage Guidelines

- **web_search**: Use for initial research and finding sources. Try multiple queries with different phrasings.
- **web_scraper**: Use when you need full content from a specific URL found in search results.
- **file_analyzer**: Use when the user uploads or references a file.
- **data_analysis**: Use for CSV/Excel data to find patterns, statistics, and generate charts.
- **report_generator**: Use to compile findings into a structured report when requested.

## Ground Rules

1. Always verify information from multiple sources when possible
2. Clearly distinguish between facts, analysis, and speculation
3. Acknowledge limitations in available data
4. When data conflicts, present both perspectives
5. Use specific numbers and statistics rather than vague statements
6. Use concise headings when the answer is complex
"""

    async def plan(self, task: str) -> list[str]:
        """Plan research steps for a complex task.

        Uses the LLM to decompose a research task into actionable steps.

        Args:
            task: Research task description.

        Returns:
            List of planned research steps.
        """
        planning_prompt = f"""Break down this research task into specific, actionable steps.

Task: {task}

Available tools:
{self.get_tool_descriptions()}

Provide a numbered list of 3-8 concrete steps. Each step should:
- Be specific and actionable
- Indicate which tool(s) to use
- Build on previous steps

Format: Return ONLY a JSON array of strings, e.g. ["Step 1...", "Step 2..."]
"""

        try:
            if not self.llm:
                raise RuntimeError("No LLM is configured")

            response = await self.llm.ainvoke([HumanMessage(content=planning_prompt)])
            # Parse the response as a JSON array
            content = response.content.strip()
            # Handle markdown code blocks
            if "```" in content:
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()

            steps = json.loads(content)
            if isinstance(steps, list):
                logger.info(f"Research plan: {len(steps)} steps")
                return steps
        except Exception as e:
            logger.warning(f"Planning failed, using default plan: {e}")

        # Fallback: default research plan
        return [
            f"Search the web for information about: {task}",
            "Scrape the most relevant search results for detailed information",
            "Analyze and synthesize the gathered information",
            "Generate a structured summary of findings",
        ]

    async def conduct_research(self, topic: str, depth: str = "standard") -> str:
        """Conduct a research session.

        This is a high-level method that plans and executes a full research workflow.

        Args:
            topic: Research topic or question.
            depth: Research depth - 'quick', 'standard', or 'deep'.

        Returns:
            Research findings.
        """
        logger.info(f"Starting research: {topic} (depth={depth})")

        # Adjust max iterations based on depth
        depth_iterations = {"quick": 5, "standard": 10, "deep": 20}
        self.max_iterations = depth_iterations.get(depth, 10)

        # Build a research-focused prompt
        research_prompt = f"""Research the following topic:

**Topic:** {topic}

**Research Depth:** {depth}

Please:
1. Search for current and relevant information
2. Scrape detailed content from authoritative sources
3. Analyze findings and identify key insights
4. Synthesize the findings into a readable summary

Provide your findings with proper citations and source URLs.
"""

        return await self.run(research_prompt)

    async def analyze_uploaded_file(self, file_path: str, question: str) -> str:
        """Analyze an uploaded file with a specific question.

        Args:
            file_path: Path to the uploaded file.
            question: Question to answer about the file.

        Returns:
            Analysis results.
        """
        prompt = f"""I've uploaded a file at: {file_path}

Please analyze this file and answer the following question:
{question}

Use the file_analyzer tool to read the file, and if it contains data (CSV/Excel),
use the data_analysis tool for deeper analysis.
"""
        return await self.run(prompt)

    async def generate_report(self, topic: str, findings: str, format: str = "markdown") -> str:
        """Generate a structured research report.

        Args:
            topic: Report topic/title.
            findings: Research findings content.
            format: Output format (markdown or pdf).

        Returns:
            Report generation result with file path.
        """
        prompt = f"""Generate a research report on: {topic}

Use the following findings to create the report:

{findings}

Create a well-structured report with:
- Executive Summary
- Key Findings
- Detailed Analysis
- Conclusions and Recommendations
- Sources

Output format: {format}
"""
        return await self.run(prompt)
