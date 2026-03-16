"""
Unit tests for ExcelExporter (improvement #17).
"""

import io
import os
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest
from openpyxl import load_workbook

from utils.excel_exporter import ExcelExporter


@pytest.fixture
def sample_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Keyword": ["купить кофе", "чай зеленый", "молоко"],
            "Source URL": [
                "https://example.com",
                "https://example.com",
                "https://test.org",
            ],
            "Avg Monthly Searches": [1000, 500, 200],
        }
    )


class TestExport:
    @patch.object(ExcelExporter, "_validate_export_path")
    def test_export_creates_file(
        self, mock_validate, sample_df: pd.DataFrame, tmp_path: Path
    ) -> None:
        file_path: str = str(tmp_path / "test_export.xlsx")
        result: bool = ExcelExporter.export(sample_df, file_path)
        assert result is True
        assert os.path.exists(file_path)

    @patch.object(ExcelExporter, "_validate_export_path")
    def test_export_readable(
        self, mock_validate, sample_df: pd.DataFrame, tmp_path: Path
    ) -> None:
        file_path: str = str(tmp_path / "test_export.xlsx")
        ExcelExporter.export(sample_df, file_path)
        df_read: pd.DataFrame = pd.read_excel(file_path)
        assert len(df_read) == 3
        assert "Keyword" in df_read.columns


class TestExportToBuffer:
    def test_export_to_buffer(self, sample_df: pd.DataFrame) -> None:
        buffer: io.BytesIO = io.BytesIO()
        result: bool = ExcelExporter.export_to_buffer(sample_df, buffer)
        assert result is True
        assert buffer.tell() == 0  # Should be seeked to start
        assert len(buffer.getvalue()) > 0

    def test_buffer_readable(self, sample_df: pd.DataFrame) -> None:
        buffer: io.BytesIO = io.BytesIO()
        ExcelExporter.export_to_buffer(sample_df, buffer)
        df_read: pd.DataFrame = pd.read_excel(buffer)
        assert len(df_read) == 3

    def test_seo_keywords_column_wraps_text(self) -> None:
        data = pd.DataFrame(
            {
                "Ключевые слова": [
                    "купить наполнитель, цена наполнителя, бумажный наполнитель, опт"
                ],
                "URL": ["https://example.com"],
                "SEO Text": ["<p>text</p>"],
                "Page Content": ["source content"],
            }
        )
        buffer = io.BytesIO()

        ExcelExporter.export_to_buffer(data, buffer)

        workbook = load_workbook(buffer)
        sheet = workbook.active

        assert sheet["A2"].alignment.wrap_text is True
        assert sheet["B2"].alignment.vertical == "top"
        assert sheet["B2"].alignment.horizontal == "left"


class TestExportCsv:
    def test_export_csv_to_bytes_has_utf8_bom(self, sample_df: pd.DataFrame) -> None:
        csv_bytes = ExcelExporter.export_csv_to_bytes(sample_df)

        # UTF-8 BOM
        assert csv_bytes.startswith(b"\xef\xbb\xbf")

        decoded = csv_bytes.decode("utf-8-sig")
        lines = decoded.splitlines()

        assert lines[0] == "Keyword,Source URL,Avg Monthly Searches"

        df_read = pd.read_csv(io.BytesIO(csv_bytes), encoding="utf-8-sig")
        assert len(df_read) == 3
        assert df_read.iloc[0]["Keyword"] == sample_df.iloc[0]["Keyword"]

    @patch.object(ExcelExporter, "_validate_export_path")
    def test_export_csv_creates_file(
        self, mock_validate, sample_df: pd.DataFrame, tmp_path: Path
    ) -> None:
        file_path: str = str(tmp_path / "test_export.csv")
        result: bool = ExcelExporter.export_csv(sample_df, file_path)
        assert result is True
        assert os.path.exists(file_path)

    @patch.object(ExcelExporter, "_validate_export_path")
    def test_csv_readable(
        self, mock_validate, sample_df: pd.DataFrame, tmp_path: Path
    ) -> None:
        file_path: str = str(tmp_path / "test_export.csv")
        ExcelExporter.export_csv(sample_df, file_path)
        with open(file_path, "rb") as exported_file:
            raw_data = exported_file.read()

        # UTF-8 BOM
        assert raw_data.startswith(b"\xef\xbb\xbf")

        df_read: pd.DataFrame = pd.read_csv(file_path, encoding="utf-8-sig")
        assert len(df_read) == 3
        assert "Keyword" in df_read.columns
