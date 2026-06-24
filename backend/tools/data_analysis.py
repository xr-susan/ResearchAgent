"""
Data analysis tool for ResearchAgent.

Provides exploratory data analysis, statistical calculations,
and data visualization capabilities for tabular data.
"""

import io
import json
from pathlib import Path
from typing import Any, Optional

from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from backend.utils.config import settings
from backend.utils.logger import get_logger

logger = get_logger("data_analysis")


class DataAnalysisInput(BaseModel):
    """Input schema for data analysis tool."""
    file_path: str = Field(description="Path to CSV or Excel file to analyze")
    analysis_query: str = Field(
        description="What to analyze, e.g. 'sales by category', 'trend over time', 'top 10 products'"
    )
    chart_type: Optional[str] = Field(
        default=None,
        description="Optional chart type: 'bar', 'line', 'pie', 'scatter', 'histogram', 'heatmap'"
    )


class DataAnalysisTool(BaseTool):
    """Tool for analyzing tabular data.

    Supports CSV and Excel files. Can perform:
    - Exploratory data analysis (EDA)
    - Statistical calculations
    - Group-by aggregations
    - Trend analysis
    - Data visualization
    """

    name: str = "data_analysis"
    description: str = (
        "Analyze data from CSV or Excel files. Can perform statistical analysis, "
        "group-by aggregations, trend analysis, and generate visualizations. "
        "Input should include the file path and what analysis to perform."
    )
    args_schema: type[BaseModel] = DataAnalysisInput

    def _run(self, file_path: str, analysis_query: str, chart_type: Optional[str] = None) -> str:
        """Synchronous data analysis."""
        import asyncio
        try:
            return asyncio.run(self._arun(file_path, analysis_query, chart_type))
        except Exception as e:
            return f"Data analysis failed: {str(e)}"

    async def _arun(self, file_path: str, analysis_query: str, chart_type: Optional[str] = None) -> str:
        """Perform data analysis asynchronously.

        Args:
            file_path: Path to data file.
            analysis_query: Description of what to analyze.
            chart_type: Optional visualization type.

        Returns:
            Analysis results as formatted string.
        """
        path = Path(file_path)
        logger.info(f"Analyzing data: {path.name} - Query: {analysis_query}")

        if not path.exists():
            return f"File not found: {file_path}"

        try:
            import pandas as pd

            # Load data
            df = self._load_data(path)
            if df is None:
                return f"Could not load file: {file_path}"

            # Perform analysis based on query
            result = self._perform_analysis(df, analysis_query)

            # Generate chart if requested
            chart_path = None
            if chart_type:
                chart_path = self._generate_chart(df, analysis_query, chart_type, path.stem)

            # Format output
            output = f"**Data Analysis Results:** {path.name}\n\n"
            output += f"**Query:** {analysis_query}\n\n"
            output += f"**Dataset Info:** {len(df)} rows × {len(df.columns)} columns\n\n"
            output += result

            if chart_path:
                output += f"\n\n**Chart generated:** {chart_path}"

            return output

        except Exception as e:
            logger.error(f"Data analysis error: {e}")
            return f"Analysis failed: {str(e)}"

    def _load_data(self, path: Path):
        """Load data from file.

        Args:
            path: File path.

        Returns:
            pandas DataFrame or None.
        """
        import pandas as pd

        ext = path.suffix.lower()
        try:
            if ext == '.csv':
                return pd.read_csv(str(path), parse_dates=True, infer_datetime_format=True)
            elif ext in ('.xlsx', '.xls'):
                return pd.read_excel(str(path))
            else:
                return pd.read_csv(str(path))
        except Exception as e:
            logger.error(f"Failed to load {path}: {e}")
            return None

    def _perform_analysis(self, df, query: str) -> str:
        """Perform analysis based on natural language query.

        Args:
            df: DataFrame to analyze.
            query: Analysis query.

        Returns:
            Formatted analysis results.
        """
        import pandas as pd

        query_lower = query.lower()
        results = []

        # Always include basic stats
        results.append("**Basic Statistics:**")
        results.append(df.describe().to_string())
        results.append("")

        # Null values
        null_counts = df.isnull().sum()
        if null_counts.any():
            results.append("**Missing Values:**")
            for col, count in null_counts[null_counts > 0].items():
                pct = count / len(df) * 100
                results.append(f"- {col}: {count} ({pct:.1f}%)")
            results.append("")

        # Detect numeric and categorical columns
        numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
        categorical_cols = df.select_dtypes(include=['object', 'category']).columns.tolist()
        datetime_cols = df.select_dtypes(include=['datetime']).columns.tolist()

        # Try to detect datetime from object columns
        for col in categorical_cols[:]:
            try:
                pd.to_datetime(df[col].head(10))
                datetime_cols.append(col)
                categorical_cols.remove(col)
            except (ValueError, TypeError):
                pass

        # Group-by analysis
        if any(word in query_lower for word in ['by', 'per', 'group', 'category', 'breakdown']):
            results.append("**Group Analysis:**")
            for cat_col in categorical_cols[:3]:
                for num_col in numeric_cols[:3]:
                    try:
                        grouped = df.groupby(cat_col)[num_col].agg(['sum', 'mean', 'count'])
                        grouped = grouped.sort_values('sum', ascending=False).head(15)
                        results.append(f"\n*{num_col} by {cat_col}:*")
                        results.append(grouped.to_string())
                    except Exception:
                        pass

        # Top N analysis
        if any(word in query_lower for word in ['top', 'best', 'highest', 'largest', 'most']):
            results.append("\n**Top Entries:**")
            for num_col in numeric_cols[:2]:
                top = df.nlargest(10, num_col)
                display_cols = (categorical_cols[:2] + [num_col])[:4]
                results.append(f"\n*Top 10 by {num_col}:*")
                results.append(top[display_cols].to_string())

        # Trend analysis
        if any(word in query_lower for word in ['trend', 'time', 'over', 'growth', 'change']):
            results.append("\n**Trend Analysis:**")
            if datetime_cols:
                time_col = datetime_cols[0]
                for num_col in numeric_cols[:3]:
                    try:
                        df_sorted = df.sort_values(time_col)
                        time_series = df_sorted.groupby(time_col)[num_col].sum()
                        if len(time_series) > 1:
                            change = ((time_series.iloc[-1] - time_series.iloc[0]) / time_series.iloc[0] * 100)
                            results.append(f"- {num_col}: {change:+.1f}% change over period")
                    except Exception:
                        pass

        # Correlation analysis
        if len(numeric_cols) > 1 and any(word in query_lower for word in ['correlat', 'relation', 'associat']):
            results.append("\n**Correlation Matrix (top pairs):**")
            corr = df[numeric_cols].corr()
            # Get top correlated pairs
            pairs = []
            for i in range(len(corr.columns)):
                for j in range(i + 1, len(corr.columns)):
                    pairs.append((corr.columns[i], corr.columns[j], corr.iloc[i, j]))
            pairs.sort(key=lambda x: abs(x[2]), reverse=True)
            for col1, col2, r in pairs[:10]:
                results.append(f"- {col1} ↔ {col2}: r = {r:.3f}")

        return "\n".join(results)

    def _generate_chart(self, df, query: str, chart_type: str, file_stem: str) -> Optional[str]:
        """Generate a data visualization chart.

        Args:
            df: DataFrame with data.
            query: Analysis query for context.
            chart_type: Type of chart to generate.
            file_stem: Original filename stem.

        Returns:
            Path to saved chart image, or None if failed.
        """
        try:
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt

            numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
            categorical_cols = df.select_dtypes(include=['object', 'category']).columns.tolist()

            fig, ax = plt.subplots(figsize=(12, 6))

            if chart_type == 'bar' and categorical_cols and numeric_cols:
                data = df.groupby(categorical_cols[0])[numeric_cols[0]].sum().sort_values(ascending=False).head(15)
                data.plot(kind='bar', ax=ax)
                ax.set_title(f'{numeric_cols[0]} by {categorical_cols[0]}')
                ax.set_xlabel(categorical_cols[0])
                ax.set_ylabel(numeric_cols[0])
                plt.xticks(rotation=45, ha='right')

            elif chart_type == 'line' and numeric_cols:
                if len(numeric_cols) >= 2:
                    df[numeric_cols[:5]].plot(ax=ax)
                else:
                    df[numeric_cols[0]].plot(ax=ax)
                ax.set_title('Trend Analysis')
                ax.legend()

            elif chart_type == 'pie' and categorical_cols and numeric_cols:
                data = df.groupby(categorical_cols[0])[numeric_cols[0]].sum().head(8)
                data.plot(kind='pie', ax=ax, autopct='%1.1f%%')
                ax.set_title(f'{numeric_cols[0]} Distribution')
                ax.set_ylabel('')

            elif chart_type == 'scatter' and len(numeric_cols) >= 2:
                df.plot.scatter(x=numeric_cols[0], y=numeric_cols[1], ax=ax, alpha=0.6)
                ax.set_title(f'{numeric_cols[1]} vs {numeric_cols[0]}')

            elif chart_type == 'histogram' and numeric_cols:
                df[numeric_cols[0]].hist(ax=ax, bins=30)
                ax.set_title(f'Distribution of {numeric_cols[0]}')
                ax.set_xlabel(numeric_cols[0])
                ax.set_ylabel('Frequency')

            else:
                # Default: bar chart of first categorical vs first numeric
                if categorical_cols and numeric_cols:
                    data = df.groupby(categorical_cols[0])[numeric_cols[0]].sum().sort_values(ascending=False).head(10)
                    data.plot(kind='bar', ax=ax)
                    plt.xticks(rotation=45, ha='right')

            plt.tight_layout()

            # Save chart
            chart_dir = settings.reports_path / "charts"
            chart_dir.mkdir(parents=True, exist_ok=True)
            chart_path = chart_dir / f"{file_stem}_{chart_type}.png"
            plt.savefig(str(chart_path), dpi=150, bbox_inches='tight')
            plt.close(fig)

            logger.info(f"Chart saved: {chart_path}")
            return str(chart_path)

        except Exception as e:
            logger.error(f"Chart generation failed: {e}")
            plt.close('all')
            return None
