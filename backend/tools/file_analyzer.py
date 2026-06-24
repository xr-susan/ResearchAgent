"""
File analyzer tool for ResearchAgent.

Supports analyzing PDF, TXT, CSV, and Excel files.
Provides content extraction and basic analysis.
"""

import csv
import io
from pathlib import Path
from typing import Optional

from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from backend.utils.logger import get_logger

logger = get_logger("file_analyzer")


class FileAnalyzerInput(BaseModel):
    """Input schema for file analyzer tool."""
    file_path: str = Field(description="Path to the file to analyze")
    analysis_type: str = Field(
        default="summary",
        description="Type of analysis: 'summary' for overview, 'full' for complete content, 'metadata' for file info only"
    )


class FileAnalyzerTool(BaseTool):
    """Tool for analyzing various file types.

    Supports: PDF, TXT, CSV, Excel (xlsx/xls), JSON, Markdown.
    Provides content extraction, metadata, and summary analysis.
    """

    name: str = "file_analyzer"
    description: str = (
        "Analyze the contents of a file. Supports PDF, TXT, CSV, Excel, JSON, and Markdown files. "
        "Use this tool when the user uploads a file or references a local file that needs to be read. "
        "Input should be the file path."
    )
    args_schema: type[BaseModel] = FileAnalyzerInput

    # Supported file extensions
    _supported_extensions: set = {'.pdf', '.txt', '.csv', '.xlsx', '.xls', '.json', '.md', '.markdown'}

    def _run(self, file_path: str, analysis_type: str = "summary") -> str:
        """Analyze a file synchronously."""
        import asyncio
        try:
            return asyncio.run(self._arun(file_path, analysis_type))
        except Exception as e:
            return f"File analysis failed: {str(e)}"

    async def _arun(self, file_path: str, analysis_type: str = "summary") -> str:
        """Analyze a file asynchronously.

        Args:
            file_path: Path to the file.
            analysis_type: Type of analysis to perform.

        Returns:
            Analysis results as formatted string.
        """
        path = Path(file_path)
        logger.info(f"Analyzing file: {path.name} (type={analysis_type})")

        if not path.exists():
            return f"File not found: {file_path}"

        if path.suffix.lower() not in self._supported_extensions:
            return f"Unsupported file type: {path.suffix}. Supported: {', '.join(sorted(self._supported_extensions))}"

        try:
            if analysis_type == "metadata":
                return self._get_metadata(path)

            # Route to appropriate handler
            ext = path.suffix.lower()
            if ext == '.pdf':
                content = self._analyze_pdf(path)
            elif ext == '.txt':
                content = self._analyze_text(path)
            elif ext == '.csv':
                content = self._analyze_csv(path, analysis_type)
            elif ext in ('.xlsx', '.xls'):
                content = self._analyze_excel(path, analysis_type)
            elif ext == '.json':
                content = self._analyze_json(path)
            elif ext in ('.md', '.markdown'):
                content = self._analyze_markdown(path)
            else:
                content = self._analyze_text(path)

            return content

        except Exception as e:
            logger.error(f"Error analyzing {file_path}: {e}")
            return f"Error analyzing file: {str(e)}"

    def _get_metadata(self, path: Path) -> str:
        """Get file metadata.

        Args:
            path: File path.

        Returns:
            Formatted metadata string.
        """
        stat = path.stat()
        size_kb = stat.st_size / 1024

        return (
            f"**File Metadata:**\n"
            f"- Name: {path.name}\n"
            f"- Type: {path.suffix}\n"
            f"- Size: {size_kb:.1f} KB\n"
            f"- Path: {path.absolute()}"
        )

    def _analyze_pdf(self, path: Path) -> str:
        """Extract text from PDF file.

        Args:
            path: PDF file path.

        Returns:
            Extracted text content.
        """
        try:
            from PyPDF2 import PdfReader

            reader = PdfReader(str(path))
            pages_text = []

            for i, page in enumerate(reader.pages[:50], 1):  # Limit to 50 pages
                text = page.extract_text()
                if text and text.strip():
                    pages_text.append(f"--- Page {i} ---\n{text.strip()}")

            if not pages_text:
                return "Could not extract text from the PDF. It may be image-based or protected."

            total_pages = len(reader.pages)
            content = "\n\n".join(pages_text)

            # Truncate if too long
            if len(content) > 10000:
                content = content[:10000] + "\n\n[Content truncated - showing first 50 pages]"

            return (
                f"**PDF Analysis:** {path.name}\n"
                f"- Total pages: {total_pages}\n"
                f"- Pages analyzed: {min(total_pages, 50)}\n\n"
                f"**Content:**\n{content}"
            )
        except ImportError:
            return "PDF analysis requires PyPDF2. Install with: pip install PyPDF2"

    def _analyze_text(self, path: Path) -> str:
        """Read text file content.

        Args:
            path: Text file path.

        Returns:
            File content.
        """
        content = path.read_text(encoding='utf-8', errors='replace')

        lines = content.split('\n')
        word_count = len(content.split())

        if len(content) > 10000:
            content = content[:10000] + "\n\n[Content truncated]"

        return (
            f"**Text File Analysis:** {path.name}\n"
            f"- Lines: {len(lines)}\n"
            f"- Words: {word_count}\n\n"
            f"**Content:**\n{content}"
        )

    def _analyze_csv(self, path: Path, analysis_type: str) -> str:
        """Analyze CSV file.

        Args:
            path: CSV file path.
            analysis_type: Type of analysis.

        Returns:
            CSV analysis results.
        """
        try:
            import pandas as pd

            df = pd.read_csv(str(path), nrows=1000)  # Limit rows for preview

            summary = (
                f"**CSV Analysis:** {path.name}\n"
                f"- Rows: {len(df)}\n"
                f"- Columns: {len(df.columns)}\n"
                f"- Column names: {', '.join(df.columns.tolist())}\n\n"
            )

            # Column types
            summary += "**Column Types:**\n"
            for col in df.columns:
                summary += f"- {col}: {df[col].dtype} ({df[col].nunique()} unique values)\n"

            if analysis_type == "full":
                summary += f"\n**First 20 rows:**\n{df.head(20).to_string()}\n\n"
                summary += f"**Basic Statistics:**\n{df.describe().to_string()}"
            else:
                summary += f"\n**First 5 rows:**\n{df.head().to_string()}"

            return summary

        except ImportError:
            return "CSV analysis requires pandas. Install with: pip install pandas"

    def _analyze_excel(self, path: Path, analysis_type: str) -> str:
        """Analyze Excel file.

        Args:
            path: Excel file path.
            analysis_type: Type of analysis.

        Returns:
            Excel analysis results.
        """
        try:
            import pandas as pd

            # Read all sheet names
            xl = pd.ExcelFile(str(path))
            sheets = xl.sheet_names

            result = f"**Excel Analysis:** {path.name}\n- Sheets: {len(sheets)}\n- Sheet names: {', '.join(sheets)}\n\n"

            for sheet in sheets[:5]:  # Analyze first 5 sheets
                df = pd.read_excel(str(path), sheet_name=sheet, nrows=500)
                result += (
                    f"**Sheet: {sheet}**\n"
                    f"- Rows: {len(df)}, Columns: {len(df.columns)}\n"
                    f"- Columns: {', '.join(df.columns.tolist())}\n"
                )
                if analysis_type == "full":
                    result += f"\n{df.head(10).to_string()}\n\n"
                else:
                    result += f"\n{df.head(3).to_string()}\n\n"

            return result

        except ImportError:
            return "Excel analysis requires pandas and openpyxl. Install with: pip install pandas openpyxl"

    def _analyze_json(self, path: Path) -> str:
        """Analyze JSON file.

        Args:
            path: JSON file path.

        Returns:
            JSON structure analysis.
        """
        import json

        data = json.loads(path.read_text(encoding='utf-8'))

        def describe_structure(obj, depth=0, max_depth=3):
            if depth >= max_depth:
                return "..."
            if isinstance(obj, dict):
                return {k: describe_structure(v, depth + 1) for k, v in list(obj.items())[:10]}
            elif isinstance(obj, list):
                if len(obj) == 0:
                    return "[]"
                return [describe_structure(obj[0], depth + 1)] + (f"... ({len(obj)} items)" if len(obj) > 1 else "")
            else:
                return type(obj).__name__

        structure = describe_structure(data)

        return (
            f"**JSON Analysis:** {path.name}\n"
            f"- Top-level type: {type(data).__name__}\n"
            f"- Structure:\n{json.dumps(structure, indent=2, default=str)}"
        )

    def _analyze_markdown(self, path: Path) -> str:
        """Analyze Markdown file.

        Args:
            path: Markdown file path.

        Returns:
            Markdown content with structure overview.
        """
        content = path.read_text(encoding='utf-8')

        # Extract headers
        import re
        headers = re.findall(r'^(#{1,6})\s+(.+)$', content, re.MULTILINE)
        header_summary = "\n".join(f"{'  ' * (len(h[0])-1)}- {h[1]}" for h in headers)

        return (
            f"**Markdown Analysis:** {path.name}\n\n"
            f"**Document Structure:**\n{header_summary}\n\n"
            f"**Content Preview:**\n{content[:5000]}"
            + ("\n\n[Content truncated]" if len(content) > 5000 else "")
        )
