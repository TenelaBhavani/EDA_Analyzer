import unittest
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd

from app.models.dataset import AssistantMessageRequest
from app.services.assistant_service import answer_question


class AssistantGraphTests(unittest.TestCase):
    def setUp(self) -> None:
        self.dataset = SimpleNamespace(
            dataframe=pd.DataFrame(
                {
                    "Month": [1, 2, 3, 4],
                    "Revenue": [10, 20, 15, 40],
                    "Region": ["West", "East", "West", "West"],
                }
            ),
            metadata=SimpleNamespace(filename="sales.xlsx"),
        )

    def ask(self, question: str, plot_type: str, columns: list[str]) -> str:
        request = AssistantMessageRequest(
            question=question,
            dataset_id="dataset-1",
            plot_type=plot_type,
            selected_columns=columns,
            graph_generated=True,
        )
        with patch("app.services.assistant_service.get_dataset", return_value=self.dataset):
            return answer_question(request).answer

    def test_single_column_graph_uses_plotted_values(self) -> None:
        answer = self.ask("What is the highest value?", "histogram", ["Revenue"])
        self.assertIn("Revenue", answer)
        self.assertIn("40", answer)

    def test_numeric_bar_graph_answers_numeric_extrema(self) -> None:
        highest = self.ask("What is the highest value?", "bar", ["Revenue"])
        lowest = self.ask("What is the lowest value?", "bar", ["Revenue"])
        self.assertIn("highest value shown for Revenue is 40", highest)
        self.assertIn("lowest value shown for Revenue is 10", lowest)

    def test_categorical_bar_graph_keeps_frequency_answers(self) -> None:
        answer = self.ask("Explain this graph", "bar", ["Region"])
        self.assertIn("highest frequency", answer)
        self.assertIn("West", answer)

    def test_graph_name_identifies_generated_chart(self) -> None:
        answer = self.ask("What is the graph name?", "bar", ["Revenue"])
        self.assertIn("bar chart", answer)
        self.assertIn("Revenue", answer)

    def test_two_column_graph_uses_both_selected_columns(self) -> None:
        answer = self.ask("Explain this graph", "line", ["Month", "Revenue"])
        self.assertIn("Month", answer)
        self.assertIn("Revenue", answer)
        self.assertIn("paired points", answer)

    def test_graph_row_limit_matches_chart_scope(self) -> None:
        request = AssistantMessageRequest(
            question="What is the highest value?",
            dataset_id="dataset-1",
            plot_type="histogram",
            selected_columns=["Revenue"],
            graph_generated=True,
            graph_row_limit=2,
        )
        with patch("app.services.assistant_service.get_dataset", return_value=self.dataset):
            answer = answer_question(request).answer
        self.assertIn("20", answer)
        self.assertNotIn("40", answer)

    def test_graph_question_before_generation_is_guarded(self) -> None:
        request = AssistantMessageRequest(
            question="Explain this graph",
            dataset_id="dataset-1",
        )
        with patch("app.services.assistant_service.get_dataset", return_value=self.dataset):
            answer = answer_question(request).answer
        self.assertIn("Generate graph", answer)


if __name__ == "__main__":
    unittest.main()