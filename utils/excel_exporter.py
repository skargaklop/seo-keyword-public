"""
Excel exporter module — exports DataFrames to formatted Excel files.
Type hints added (improvement #5).
CSV export support added (improvement #13).
"""

import io
from pathlib import Path
from typing import Optional

import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.workbook import Workbook

from utils.logger import logger

# Allowed output directory for file exports
_ALLOWED_OUTPUT_DIR = Path(__file__).parent.parent / "outputs"


class ExcelExporter:
    _WRAPPED_KEYWORD_HEADERS = {"Keyword", "Ключевые слова", "Ключові слова"}

    @staticmethod
    def _format_workbook(wb: Workbook) -> None:
        """
        Применение форматирования к рабочей книге Excel.
        """
        ws = wb.active

        # Стили заголовков
        header_font: Font = Font(bold=True, color="FFFFFF")
        header_fill: PatternFill = PatternFill(
            start_color="4F81BD", end_color="4F81BD", fill_type="solid"
        )

        # Форматирование заголовков
        for cell in ws[1]:
            cell.font = header_font
            cell.fill = header_fill
        #    cell.alignment = Alignment(horizontal="center")

        # Автоподбор ширины колонок
        keyword_col_letter: Optional[str] = None
        url_col_letter: Optional[str] = None
        seo_text_col_letter: Optional[str] = None
        page_content_col_letter: Optional[str] = None

        # Поиск специальных колонок
        for cell in ws[1]:
            if cell.value in ExcelExporter._WRAPPED_KEYWORD_HEADERS:
                keyword_col_letter = cell.column_letter
            elif cell.value == "URL":
                url_col_letter = cell.column_letter
            elif cell.value == "SEO Text" or cell.value == "SEO текст":
                seo_text_col_letter = cell.column_letter
            elif cell.value == "Page Content":
                page_content_col_letter = cell.column_letter

        for column in ws.columns:
            max_length: int = 0
            col_letter: str = column[0].column_letter

            # Специальная обработка для колонки с ключевыми словами
            if col_letter == keyword_col_letter:
                ws.column_dimensions[col_letter].width = 40
                for cell in column:
                    cell.alignment = Alignment(wrap_text=True, vertical="top")
                continue

            # Специальная обработка для URL
            if col_letter == url_col_letter:
                ws.column_dimensions[col_letter].width = 30
                for cell in column:
                    cell.alignment = Alignment(
                        wrap_text=True, horizontal="left", vertical="top"
                    )
                continue

            # Специальная обработка для Page Content
            if col_letter == page_content_col_letter:
                ws.column_dimensions[col_letter].width = 120
                for cell in column:
                    cell.alignment = Alignment(wrap_text=True, vertical="top")
                continue

            # Специальная обработка для SEO текста
            if col_letter == seo_text_col_letter:
                ws.column_dimensions[col_letter].width = 70
                for cell in column:
                    cell.alignment = Alignment(wrap_text=True, vertical="top")
                continue

            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except Exception:
                    pass

            adjusted_width: int = max_length + 2
            if adjusted_width > 50:
                adjusted_width = 50

            ws.column_dimensions[column[0].column_letter].width = adjusted_width

        # Добавление фильтров
        ws.auto_filter.ref = ws.dimensions

    @staticmethod
    def _validate_export_path(file_path: str) -> None:
        """Validate that the export path is within the allowed output directory."""
        resolved = Path(file_path).resolve()
        allowed = _ALLOWED_OUTPUT_DIR.resolve()
        try:
            resolved.relative_to(allowed)
        except ValueError:
            raise ValueError(
                f"Export path must be within the outputs/ directory. Got: {file_path}"
            )

    @staticmethod
    def export(data: pd.DataFrame, file_path: str) -> bool:
        """
        Экспорт DataFrame в Excel файл с форматированием.
        """
        try:
            ExcelExporter._validate_export_path(file_path)
            # 1. Базовая запись
            data.to_excel(file_path, index=False, engine="openpyxl")

            # 2. Расширенное форматирование
            wb: Workbook = load_workbook(file_path)
            ExcelExporter._format_workbook(wb)
            wb.save(file_path)

            logger.info(f"Successfully exported data to {file_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to export Excel: {e}")
            return False

    @staticmethod
    def export_to_buffer(data: pd.DataFrame, buffer: io.BytesIO) -> bool:
        """
        Экспорт DataFrame в буфер в памяти (для кнопки скачивания без сохранения на диск).
        """
        try:
            data.to_excel(buffer, index=False, engine="openpyxl")
            buffer.seek(0)

            wb: Workbook = load_workbook(buffer)
            ExcelExporter._format_workbook(wb)

            buffer.seek(0)
            buffer.truncate()
            wb.save(buffer)
            buffer.seek(0)

            return True

        except Exception as e:
            logger.error(f"Failed to export Excel to buffer: {e}")
            return False

    @staticmethod
    def export_csv(data: pd.DataFrame, file_path: str) -> bool:
        """
        Экспорт DataFrame в CSV файл (improvement #13).
        """
        try:
            ExcelExporter._validate_export_path(file_path)
            Path(file_path).write_bytes(ExcelExporter.export_csv_to_bytes(data))
            logger.info(f"Successfully exported CSV to {file_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to export CSV: {e}")
            return False

    @staticmethod
    def export_csv_to_bytes(data: pd.DataFrame) -> bytes:
        """
        Build an Excel-friendly CSV payload with UTF-8 BOM encoding.
        The BOM (Byte Order Mark) tells Excel to interpret the file as UTF-8,
        ensuring correct display of Cyrillic and other Unicode characters.
        """
        csv_body = data.to_csv(index=False, lineterminator="\r\n")
        return csv_body.encode("utf-8-sig")
