"""
Tests for ResearchAgent tools.
"""

import json
from pathlib import Path

import pytest

from backend.tools.file_analyzer import FileAnalyzerTool
from backend.tools.data_analysis import DataAnalysisTool
from backend.tools.report_generator import ReportGeneratorTool
from backend.tools.search_tool import SearchTool
from backend.tools.web_scraper import WebScraperTool


class TestFileAnalyzerTool:
    """Tests for FileAnalyzerTool."""

    def test_tool_initialization(self):
        """Test that the tool initializes correctly."""
        tool = FileAnalyzerTool()
        assert tool.name == "file_analyzer"
        assert "file" in tool.description.lower()

    @pytest.mark.asyncio
    async def test_analyze_text_file(self, sample_text):
        """Test analyzing a text file."""
        tool = FileAnalyzerTool()
        result = await tool._arun(str(sample_text), "summary")

        assert "Text File Analysis" in result
        assert "sample_research.txt" in result
        assert "AI adoption" in result

    @pytest.mark.asyncio
    async def test_analyze_csv_file(self, sample_csv):
        """Test analyzing a CSV file."""
        tool = FileAnalyzerTool()
        result = await tool._arun(str(sample_csv), "summary")

        assert "CSV Analysis" in result
        assert "name" in result
        assert "salary" in result
        assert "10 rows" in result or "Rows: 10" in result

    @pytest.mark.asyncio
    async def test_analyze_markdown_file(self, sample_markdown):
        """Test analyzing a markdown file."""
        tool = FileAnalyzerTool()
        result = await tool._arun(str(sample_markdown), "summary")

        assert "Markdown Analysis" in result
        assert "Executive Summary" in result

    @pytest.mark.asyncio
    async def test_analyze_nonexistent_file(self):
        """Test analyzing a file that doesn't exist."""
        tool = FileAnalyzerTool()
        result = await tool._arun("/nonexistent/file.txt")

        assert "not found" in result.lower() or "error" in result.lower()

    @pytest.mark.asyncio
    async def test_metadata_mode(self, sample_csv):
        """Test metadata-only analysis mode."""
        tool = FileAnalyzerTool()
        result = await tool._arun(str(sample_csv), "metadata")

        assert "File Metadata" in result
        assert "test_data.csv" in result


class TestDataAnalysisTool:
    """Tests for DataAnalysisTool."""

    def test_tool_initialization(self):
        """Test that the tool initializes correctly."""
        tool = DataAnalysisTool()
        assert tool.name == "data_analysis"

    @pytest.mark.asyncio
    async def test_analyze_csv_data(self, sample_csv):
        """Test basic CSV data analysis."""
        tool = DataAnalysisTool()
        result = await tool._arun(str(sample_csv), "summary statistics")

        assert "Data Analysis Results" in result
        assert "salary" in result

    @pytest.mark.asyncio
    async def test_group_analysis(self, sample_csv):
        """Test group-by analysis."""
        tool = DataAnalysisTool()
        result = await tool._arun(str(sample_csv), "salary by department")

        assert "Data Analysis Results" in result

    @pytest.mark.asyncio
    async def test_top_analysis(self, sample_csv):
        """Test top-N analysis."""
        tool = DataAnalysisTool()
        result = await tool._arun(str(sample_csv), "top 5 highest salary")

        assert "Data Analysis Results" in result

    @pytest.mark.asyncio
    async def test_chart_generation(self, sample_csv, tmp_path):
        """Test chart generation."""
        tool = DataAnalysisTool()
        result = await tool._arun(str(sample_csv), "salary by department", chart_type="bar")

        assert "Data Analysis Results" in result


class TestReportGeneratorTool:
    """Tests for ReportGeneratorTool."""

    def test_tool_initialization(self):
        """Test that the tool initializes correctly."""
        tool = ReportGeneratorTool()
        assert tool.name == "report_generator"

    @pytest.mark.asyncio
    async def test_generate_markdown_report(self, tmp_path):
        """Test markdown report generation."""
        tool = ReportGeneratorTool()

        # Monkey-patch the reports path
        from backend.utils.config import settings
        original = settings.reports_dir
        settings.reports_dir = str(tmp_path / "reports")

        result = await tool._arun(
            title="Test Report",
            content="## Introduction\nThis is a test report.\n\n## Findings\nWe found interesting results.",
            output_format="markdown",
        )

        assert "Report saved" in result or "Test Report" in result

        # Restore
        settings.reports_dir = original

    @pytest.mark.asyncio
    async def test_generate_report_with_sections(self, tmp_path):
        """Test report generation with section structure."""
        tool = ReportGeneratorTool()

        from backend.utils.config import settings
        original = settings.reports_dir
        settings.reports_dir = str(tmp_path / "reports")

        sections = json.dumps([
            {"title": "Background", "content": "Some background info."},
            {"title": "Results", "content": "The results are positive."},
        ])

        result = await tool._arun(
            title="Structured Report",
            content="Main content here.",
            sections=sections,
            output_format="markdown",
        )

        assert "Report saved" in result or "Structured Report" in result
        settings.reports_dir = original


class TestSearchTool:
    """Tests for SearchTool."""

    def test_tool_initialization(self):
        """Test that the tool initializes correctly."""
        tool = SearchTool()
        assert tool.name == "web_search"

    def test_cache_key_generation(self):
        """Test cache key generation."""
        tool = SearchTool()
        key1 = tool._get_cache_key("test query")
        key2 = tool._get_cache_key("TEST QUERY")
        key3 = tool._get_cache_key("different query")

        # Same query (case insensitive) should produce same key
        assert key1 == key2
        # Different query should produce different key
        assert key1 != key3


class TestWebScraperTool:
    """Tests for WebScraperTool."""

    def test_tool_initialization(self):
        """Test that the tool initializes correctly."""
        tool = WebScraperTool()
        assert tool.name == "web_scraper"

    @pytest.mark.asyncio
    async def test_invalid_url(self):
        """Test scraping an invalid URL."""
        tool = WebScraperTool()
        result = await tool._arun("not-a-valid-url")

        assert "invalid" in result.lower() or "error" in result.lower()

    def test_supported_extractions(self):
        """Test that all extraction modes are documented."""
        tool = WebScraperTool()
        assert "text" in tool.description.lower() or "extract" in tool.description.lower()
