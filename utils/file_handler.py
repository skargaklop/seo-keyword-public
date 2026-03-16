"""
File handler module — parses uploaded files to extract URLs.
Unused validate_file_size() removed (improvement #2).
Type hints added (improvement #5).
"""

import io
from typing import List

import pandas as pd

from config.settings import UPLOADS_CONFIG
from utils.logger import logger


DEFAULT_MAX_FILE_SIZE_MB = float(UPLOADS_CONFIG.get("max_file_size_mb", 5))
DEFAULT_MAX_ROWS = int(UPLOADS_CONFIG.get("max_rows", 1000))


class FileParsingError(ValueError):
    """Raised when an uploaded file violates configured parsing limits."""

    def __init__(self, message_key: str, **message_kwargs: object) -> None:
        super().__init__(message_key)
        self.message_key = message_key
        self.message_kwargs = message_kwargs


class FileHandler:
    @staticmethod
    def _file_size_bytes(uploaded_file) -> int:
        """Resolve uploaded file size without parsing the file first."""
        if hasattr(uploaded_file, "size"):
            return int(uploaded_file.size)
        if hasattr(uploaded_file, "getbuffer"):
            return int(uploaded_file.getbuffer().nbytes)
        return len(uploaded_file.getvalue())

    @staticmethod
    def _validate_size(
        uploaded_file,
        filename: str,
        max_file_size_mb: float,
    ) -> None:
        if max_file_size_mb <= 0:
            return
        max_bytes = int(max_file_size_mb * 1024 * 1024)
        if FileHandler._file_size_bytes(uploaded_file) > max_bytes:
            raise FileParsingError(
                "upload_file_too_large",
                filename=filename,
                max_size_mb=int(max_file_size_mb),
            )

    @staticmethod
    def _validate_row_count(values: List[str], filename: str, max_rows: int) -> None:
        if max_rows > 0 and len(values) > max_rows:
            raise FileParsingError(
                "upload_file_too_many_rows",
                filename=filename,
                max_rows=max_rows,
            )

    @staticmethod
    def _resolve_csv_column(df: pd.DataFrame, input_mode: str) -> str:
        """Resolve the preferred CSV column based on workflow input mode."""
        lowered = {str(col).lower(): col for col in df.columns}
        if input_mode == "keyword":
            for candidate in ("keyword", "keywords"):
                if candidate in lowered:
                    return lowered[candidate]
        elif "url" in lowered:
            return lowered["url"]

        return df.columns[0]

    @staticmethod
    def parse_file(
        uploaded_file,
        input_mode: str = "url",
        max_file_size_mb: float = DEFAULT_MAX_FILE_SIZE_MB,
        max_rows: int = DEFAULT_MAX_ROWS,
    ) -> List[str]:
        """
        Parse uploaded file (streamlit UploadedFile or file path) and extract values.
        Supports .txt and .csv for both URL and keyword seed inputs.
        """
        filename: str = uploaded_file.name
        normalized_filename = filename.lower()
        values: List[str] = []

        try:
            FileHandler._validate_size(uploaded_file, filename, max_file_size_mb)

            if normalized_filename.endswith(".txt"):
                stringio = io.StringIO(uploaded_file.getvalue().decode("utf-8"))
                values = [line.strip() for line in stringio.readlines() if line.strip()]
                FileHandler._validate_row_count(values, filename, max_rows)

            elif normalized_filename.endswith(".csv"):
                if hasattr(uploaded_file, "seek"):
                    uploaded_file.seek(0)
                read_limit = max_rows + 1 if max_rows > 0 else None
                df: pd.DataFrame = pd.read_csv(uploaded_file, nrows=read_limit)
                target_column = FileHandler._resolve_csv_column(df, input_mode)
                values = df[target_column].dropna().astype(str).str.strip().tolist()
                FileHandler._validate_row_count(values, filename, max_rows)

            else:
                logger.error(f"Unsupported file format: {filename}")
                raise FileParsingError(
                    "upload_file_unsupported_format",
                    filename=filename,
                )

            logger.info(
                f"Parsed {len(values)} {input_mode} value(s) from file {filename}"
            )
            return values

        except FileParsingError:
            raise
        except Exception as e:
            logger.error(f"Error parsing file {filename}: {str(e)}")
            raise FileParsingError(
                "upload_file_parse_error",
                filename=filename,
                error=str(e),
            ) from e
