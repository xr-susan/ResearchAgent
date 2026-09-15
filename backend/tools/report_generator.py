"""
Report generator tool for ResearchAgent.

Generates structured reports in Markdown and PDF formats.
Supports automatic formatting with sections, citations, and charts.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from backend.utils.config import settings
from backend.utils.logger import get_logger

logger = get_logger("report_generator")


class ReportInput(BaseModel):
    """Input schema for report generator tool."""
    title: str = Field(description="Report title")
    content: str = Field(description="Report content in markdown format")
    sections: Optional[str] = Field(
        default=None,
        description="JSON string of section structure, e.g. [{\"title\": \"Introduction\", \"content\": \"...\"}]"
    )
    output_format: str = Field(
        default="markdown",
        description="Output format: 'markdown' or 'pdf'"
    )
    include_toc: bool = Field(default=True, description="Include table of contents")


class ReportGeneratorTool(BaseTool):
    """Tool for generating structured research reports.

    Creates reports with:
    - Automatic table of contents
    - Section structuring
    - Citation management
    - Markdown and PDF output
    """

    name: str = "report_generator"
    description: str = (
        "Generate a structured research report. Use this tool when you need to compile "
            "findings into a readable report. Input should include a title and content. "
        "Output formats: 'markdown' or 'pdf'."
    )
    args_schema: type[BaseModel] = ReportInput

    def _run(
        self,
        title: str,
        content: str,
        sections: Optional[str] = None,
        output_format: str = "markdown",
        include_toc: bool = True,
    ) -> str:
        """Generate a report synchronously."""
        import asyncio
        try:
            return asyncio.run(self._arun(title, content, sections, output_format, include_toc))
        except Exception as e:
            return f"Report generation failed: {str(e)}"

    async def _run_async(
        self,
        title: str,
        content: str,
        sections: Optional[str] = None,
        output_format: str = "markdown",
        include_toc: bool = True,
    ) -> str:
        """Generate a report asynchronously."""
        return self._run(title, content, sections, output_format, include_toc)

    async def _arun(
        self,
        title: str,
        content: str,
        sections: Optional[str] = None,
        output_format: str = "markdown",
        include_toc: bool = True,
    ) -> str:
        """Generate a research report.

        Args:
            title: Report title.
            content: Main content in markdown.
            sections: Optional JSON section structure.
            output_format: Output format (markdown/pdf).
            include_toc: Whether to include table of contents.

        Returns:
            Path to generated report or report content.
        """
        logger.info(f"Generating report: {title} (format={output_format})")

        try:
            # Parse sections if provided
            section_list = []
            if sections:
                try:
                    section_list = json.loads(sections)
                except json.JSONDecodeError:
                    logger.warning("Failed to parse sections JSON, using content as-is")

            # Generate markdown report
            md_content = self._build_markdown(title, content, section_list, include_toc)

            if output_format == "markdown":
                return self._save_markdown(title, md_content)
            elif output_format == "pdf":
                return self._save_pdf(title, md_content)
            else:
                return md_content

        except Exception as e:
            logger.error(f"Report generation error: {e}")
            return f"Report generation failed: {str(e)}"

    def _build_markdown(
        self,
        title: str,
        content: str,
        sections: list[dict],
        include_toc: bool,
    ) -> str:
        """Build markdown report content.

        Args:
            title: Report title.
            content: Main content.
            sections: List of section dictionaries.
            include_toc: Include table of contents.

        Returns:
            Complete markdown string.
        """
        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        lines = []

        # Header
        lines.append(f"# {title}")
        lines.append("")
        lines.append(f"**Generated:** {now}  ")
        lines.append("**Author:** ResearchAgent  ")
        lines.append("")
        lines.append("---")
        lines.append("")

        # Table of Contents
        if include_toc:
            lines.append("## Table of Contents")
            lines.append("")
            if sections:
                for i, sec in enumerate(sections, 1):
                    sec_title = sec.get("title", f"Section {i}")
                    anchor = sec_title.lower().replace(" ", "-").replace(".", "")
                    lines.append(f"{i}. [{sec_title}](#{anchor})")
            else:
                # Auto-generate TOC from content headers
                import re
                headers = re.findall(r'^(#{2,4})\s+(.+)$', content, re.MULTILINE)
                for i, (level, header) in enumerate(headers, 1):
                    indent = "  " * (len(level) - 2)
                    anchor = header.lower().replace(" ", "-").replace(".", "")
                    lines.append(f"{indent}- [{header}](#{anchor})")
            lines.append("")
            lines.append("---")
            lines.append("")

        # Executive Summary
        lines.append("## Executive Summary")
        lines.append("")
        # Extract first paragraph or first 500 chars as summary
        summary_text = content.split("\n\n")[0] if "\n\n" in content else content[:500]
        lines.append(summary_text)
        lines.append("")

        # Main content or sections
        if sections:
            for i, sec in enumerate(sections, 1):
                lines.append(f"## {i}. {sec.get('title', f'Section {i}')}")
                lines.append("")
                lines.append(sec.get("content", ""))
                lines.append("")
        else:
            lines.append(content)
            lines.append("")

        # Footer
        lines.append("---")
        lines.append("")
        lines.append(f"*Created with ResearchAgent on {now}.*")

        return "\n".join(lines)

    def _save_markdown(self, title: str, content: str) -> str:
        """Save report as markdown file.

        Args:
            title: Report title (used for filename).
            content: Markdown content.

        Returns:
            Path to saved file.
        """
        reports_dir = settings.reports_path
        reports_dir.mkdir(parents=True, exist_ok=True)

        # Create safe filename
        safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).strip()
        safe_title = safe_title.replace(' ', '_')[:50]
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"{safe_title}_{timestamp}.md"

        filepath = reports_dir / filename
        filepath.write_text(content, encoding='utf-8')

        logger.info(f"Markdown report saved: {filepath}")
        return f"Report saved as Markdown: {filepath}\n\n{content[:2000]}"

    def _save_pdf(self, title: str, md_content: str) -> str:
        """Save report as PDF file.

        Args:
            title: Report title.
            md_content: Markdown content.

        Returns:
            Path to saved file and preview.
        """
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
            from reportlab.lib.enums import TA_CENTER, TA_LEFT
            import re

            reports_dir = settings.reports_path
            reports_dir.mkdir(parents=True, exist_ok=True)

            safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).strip()
            safe_title = safe_title.replace(' ', '_')[:50]
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            filename = f"{safe_title}_{timestamp}.pdf"
            filepath = reports_dir / filename

            # Create PDF
            doc = SimpleDocTemplate(str(filepath), pagesize=A4, topMargin=inch, bottomMargin=inch)
            styles = getSampleStyleSheet()

            # Custom styles
            title_style = ParagraphStyle('CustomTitle', parent=styles['Title'], fontSize=24, alignment=TA_CENTER, spaceAfter=30)
            heading_style = ParagraphStyle('CustomHeading', parent=styles['Heading1'], fontSize=16, spaceBefore=20, spaceAfter=10)
            body_style = ParagraphStyle('CustomBody', parent=styles['Normal'], fontSize=11, leading=14, spaceAfter=8)

            story = []
            story.append(Paragraph(title, title_style))
            story.append(Paragraph(f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}", body_style))
            story.append(Spacer(1, 30))

            # Parse markdown into reportlab elements
            for line in md_content.split('\n'):
                line = line.strip()
                if not line:
                    story.append(Spacer(1, 6))
                elif line.startswith('# '):
                    story.append(Paragraph(line[2:], title_style))
                elif line.startswith('## '):
                    story.append(Paragraph(line[3:], heading_style))
                elif line.startswith('### '):
                    story.append(Paragraph(line[4:], styles['Heading2']))
                elif line.startswith('---'):
                    story.append(Spacer(1, 12))
                elif line.startswith('*') and line.endswith('*'):
                    story.append(Paragraph(line.strip('*'), body_style))
                else:
                    # Clean markdown formatting for PDF
                    clean_line = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', line)
                    clean_line = re.sub(r'\*(.+?)\*', r'<i>\1</i>', clean_line)
                    try:
                        story.append(Paragraph(clean_line, body_style))
                    except Exception:
                        story.append(Paragraph(line, body_style))

            doc.build(story)
            logger.info(f"PDF report saved: {filepath}")

            return f"Report saved as PDF: {filepath}"

        except ImportError:
            logger.warning("reportlab not installed, falling back to markdown")
            return self._save_markdown(title, md_content) + "\n\n(PDF generation requires reportlab: pip install reportlab)"
