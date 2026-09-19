from __future__ import annotations

import pandas as pd

from app.models.dataset import AssistantMessageRequest, AssistantMessageResponse
from app.services.dataset_service import DatasetUploadError, get_dataset


def _format_number(value: float) -> str:
    return f"{value:,.2f}".rstrip("0").rstrip(".")


def _selected_series(dataframe: pd.DataFrame, column: str) -> pd.Series:
    if column not in dataframe.columns:
        raise DatasetUploadError(f"Column '{column}' was not found in the dataset.")
    return dataframe[column].dropna()


def _numeric_series(dataframe: pd.DataFrame, column: str) -> pd.Series:
    return pd.to_numeric(_selected_series(dataframe, column), errors="coerce").dropna()


def _graph_answer(request: AssistantMessageRequest, dataframe: pd.DataFrame) -> str | None:
    columns = request.selected_columns
    plot_type = request.plot_type
    if not plot_type or not columns:
        return None

    graph_data = dataframe.head(request.graph_row_limit)
    question = request.question.lower()
    explain = any(word in question for word in ("explain", "graph", "plot", "chart"))

    if "graph name" in question or "plot name" in question or "chart name" in question:
        return f"The generated graph is a {plot_type} chart for {', '.join(columns)}."

    if plot_type in {"line", "scatter"}:
        if len(columns) < 2:
            return "Select two columns to explain this graph."
        paired = graph_data[columns].apply(pd.to_numeric, errors="coerce").dropna()
        if paired.empty:
            return f"The {plot_type} graph has no paired numeric values to analyze."
        x_column, y_column = columns[:2]
        x_values = paired[x_column]
        y_values = paired[y_column]
        correlation = x_values.corr(y_values)
        if "correlation" in question or "related" in question:
            correlation_text = "not available" if pd.isna(correlation) else _format_number(correlation)
            return f"The correlation between {x_column} and {y_column} in the graph is {correlation_text}."
        if "highest" in question or "maximum" in question:
            index = y_values.idxmax()
            return f"The highest {y_column} value in the graph is {_format_number(y_values.loc[index])}, when {x_column} is {_format_number(x_values.loc[index])}."
        if "lowest" in question or "minimum" in question:
            index = y_values.idxmin()
            return f"The lowest {y_column} value in the graph is {_format_number(y_values.loc[index])}, when {x_column} is {_format_number(x_values.loc[index])}."
        direction = "upward" if y_values.iloc[-1] > y_values.iloc[0] else "downward" if y_values.iloc[-1] < y_values.iloc[0] else "flat"
        if "trend" in question or explain or plot_type == "line":
            return f"The {plot_type} graph shows {y_column} with a {direction} direction across {len(paired):,} paired points, from {_format_number(y_values.iloc[0])} to {_format_number(y_values.iloc[-1])}, against {x_column}."
        return f"The graph compares {x_column} with {y_column} across {len(paired):,} paired points."

    column = columns[0]
    if plot_type in {"bar", "pie"}:
        numeric_values = pd.to_numeric(graph_data[column], errors="coerce").dropna()
        if not numeric_values.empty:
            minimum, maximum = numeric_values.min(), numeric_values.max()
            mean = numeric_values.mean()
            if "highest" in question or "maximum" in question:
                return f"The highest value shown for {column} is {_format_number(maximum)}."
            if "lowest" in question or "minimum" in question:
                return f"The lowest value shown for {column} is {_format_number(minimum)}."
            if "average" in question or "mean" in question:
                return f"The average shown for {column} is {_format_number(mean)} across {len(numeric_values):,} values."
            if "median" in question:
                return f"The median shown for {column} is {_format_number(numeric_values.median())}."
            if explain:
                return f"The {plot_type} graph for numeric column {column} contains {len(numeric_values):,} values, ranging from {_format_number(minimum)} to {_format_number(maximum)}, with an average of {_format_number(mean)}."
            return f"The {plot_type} graph shows numeric values for {column}, ranging from {_format_number(minimum)} to {_format_number(maximum)}."

        values = graph_data[column].dropna().astype(str).value_counts()
        if values.empty:
            return f"The {plot_type} graph has no non-empty values for {column}."
        value, count = values.index[0], int(values.iloc[0])
        if "highest" in question or "most" in question or "frequency" in question or explain:
            return f"The {plot_type} graph shows {column} as the category with the highest frequency: '{value}' appears {count:,} times."
        return f"The {plot_type} graph contains {values.size:,} categories for {column}; the most common is '{value}' with {count:,} occurrences."

    values = _numeric_series(graph_data, column)
    if values.empty:
        return f"The {plot_type} graph has no usable numeric values for {column}."
    minimum, maximum = values.min(), values.max()
    mean = values.mean()
    if "highest" in question or "maximum" in question:
        return f"The highest value shown for {column} is {_format_number(maximum)}."
    if "lowest" in question or "minimum" in question:
        return f"The lowest value shown for {column} is {_format_number(minimum)}."
    if "average" in question or "mean" in question:
        return f"The average shown for {column} is {_format_number(mean)} across {len(values):,} values."
    if "median" in question:
        return f"The median shown for {column} is {_format_number(values.median())}."
    if "outlier" in question or plot_type == "box":
        first_quartile, third_quartile = values.quantile([0.25, 0.75])
        spread = third_quartile - first_quartile
        outliers = values[(values < first_quartile - 1.5 * spread) | (values > third_quartile + 1.5 * spread)]
        return f"The {plot_type} graph has {len(outliers):,} IQR outliers for {column}, ranging from {_format_number(minimum)} to {_format_number(maximum)}."
    if explain or plot_type in {"histogram", "distribution"}:
        return f"The {plot_type} graph for {column} contains {len(values):,} numeric values, ranging from {_format_number(minimum)} to {_format_number(maximum)}, with an average of {_format_number(mean)}."
    return None


def answer_question(request: AssistantMessageRequest) -> AssistantMessageResponse:
    question = request.question.strip()
    if not question:
        return AssistantMessageResponse(answer="Ask me a question about your uploaded data or generated graph.")
    if request.dataset_id is None:
        return AssistantMessageResponse(answer="Upload a dataset first, then I can answer questions about its columns and graphs.")

    dataset = get_dataset(request.dataset_id)
    if dataset is None:
        raise DatasetUploadError("The requested dataset was not found. Upload it again to continue.")

    dataframe = dataset.dataframe
    lower_question = question.lower()
    columns = request.selected_columns
    if not request.graph_generated and any(word in lower_question for word in ("graph", "plot", "chart", "trend", "distribution")):
        return AssistantMessageResponse(answer="Choose a plot type and column in Build a graph, then select Generate graph. After that I can explain the chart, trends, values, and outliers.")

    if columns:
        for column in columns:
            if column not in dataframe.columns:
                raise DatasetUploadError(f"Column '{column}' was not found in the dataset.")

    if request.graph_generated:
        graph_answer = _graph_answer(request, dataframe)
        if graph_answer is not None:
            return AssistantMessageResponse(answer=graph_answer)

    if "column" in lower_question and not columns:
        return AssistantMessageResponse(answer=f"This dataset has {len(dataframe.columns)} columns: {', '.join(map(str, dataframe.columns))}.")

    if any(word in lower_question for word in ("missing", "null", "empty")):
        missing = dataframe.isna().sum().sort_values(ascending=False)
        details = ", ".join(f"{column}: {int(count)}" for column, count in missing.items() if count > 0)
        return AssistantMessageResponse(answer=f"Missing values: {details}." if details else "There are no missing values in this dataset.")

    if "row" in lower_question or "record" in lower_question:
        return AssistantMessageResponse(answer=f"The dataset contains {len(dataframe):,} rows and {len(dataframe.columns)} columns.")

    if columns:
        column = columns[0]
        series = _selected_series(dataframe, column)
        numeric = pd.to_numeric(series, errors="coerce").dropna()
        if len(numeric) > 0 and (any(word in lower_question for word in ("average", "mean", "median", "range", "minimum", "maximum", "highest", "lowest", "outlier", "distribution", "trend", "value")) or request.plot_type in {"histogram", "box", "distribution", "line", "scatter"}):
            mean = numeric.mean()
            median = numeric.median()
            minimum = numeric.min()
            maximum = numeric.max()
            if "average" in lower_question or "mean" in lower_question:
                return AssistantMessageResponse(answer=f"The average of {column} is {_format_number(mean)} across {len(numeric):,} numeric values.")
            if "median" in lower_question:
                return AssistantMessageResponse(answer=f"The median of {column} is {_format_number(median)}.")
            if "minimum" in lower_question or "lowest" in lower_question:
                return AssistantMessageResponse(answer=f"The lowest value in {column} is {_format_number(minimum)}.")
            if "maximum" in lower_question or "highest" in lower_question:
                return AssistantMessageResponse(answer=f"The highest value in {column} is {_format_number(maximum)}.")
            if "outlier" in lower_question or request.plot_type == "box":
                first_quartile, third_quartile = numeric.quantile([0.25, 0.75])
                spread = third_quartile - first_quartile
                outliers = numeric[(numeric < first_quartile - 1.5 * spread) | (numeric > third_quartile + 1.5 * spread)]
                return AssistantMessageResponse(answer=f"{column} has {len(outliers):,} IQR outliers. Its range is {_format_number(minimum)} to {_format_number(maximum)}.")
            if "trend" in lower_question or request.plot_type in {"line", "scatter"}:
                direction = "upward" if numeric.iloc[-1] > numeric.iloc[0] else "downward" if numeric.iloc[-1] < numeric.iloc[0] else "flat"
                return AssistantMessageResponse(answer=f"The observed {column} series has a {direction} end-to-end direction, from {_format_number(numeric.iloc[0])} to {_format_number(numeric.iloc[-1])}.")
            return AssistantMessageResponse(answer=f"{column} has {len(numeric):,} numeric values, ranging from {_format_number(minimum)} to {_format_number(maximum)}, with an average of {_format_number(mean)}.")

        values = series.astype(str).value_counts()
        if "highest" in lower_question or "most" in lower_question or request.plot_type in {"bar", "pie"}:
            value, count = values.index[0], int(values.iloc[0])
            return AssistantMessageResponse(answer=f"The most common value in {column} is '{value}', appearing {count:,} times.")
        if "count" in lower_question or "frequency" in lower_question:
            summary = ", ".join(f"{value}: {int(count)}" for value, count in values.head(5).items())
            return AssistantMessageResponse(answer=f"The most frequent values in {column} are {summary}.")
        return AssistantMessageResponse(answer=f"{column} contains {series.nunique():,} distinct non-empty values. The most common is '{values.index[0]}'.")

    numeric_columns = dataframe.select_dtypes(include="number").columns.tolist()
    if "correlation" in lower_question and len(numeric_columns) >= 2:
        correlation = dataframe[numeric_columns].corr().iloc[0, 1]
        return AssistantMessageResponse(answer=f"The correlation between {numeric_columns[0]} and {numeric_columns[1]} is {_format_number(correlation)}.")
    if "summary" in lower_question or "data" in lower_question or "dataset" in lower_question:
        return AssistantMessageResponse(answer=f"{dataset.metadata.filename} contains {len(dataframe):,} rows and {len(dataframe.columns)} columns. Numeric columns: {', '.join(map(str, numeric_columns)) or 'none'}.")
    return AssistantMessageResponse(answer="I can explain the generated graph, compare values, find trends or outliers, and calculate averages, medians, ranges, counts, missing values, and correlations. Select the relevant column and ask again.")