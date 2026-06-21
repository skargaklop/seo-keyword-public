# MODULE_CONTRACT: utils/file_handler
# Purpose: File handler module — parses uploaded files to extract URLs.
# Rationale: Keep the module boundary explicit for GRACE adoption and review.
# Dependencies: io, typing, pandas, config.settings, utils.logger
# Exports: DEFAULT_MAX_FILE_SIZE_MB, DEFAULT_MAX_ROWS, FileParsingError, FileHandler
# LINKS: requirements.xml#UC-001, development-plan.xml#MOD-001
# MODULE_MAP: utils/file_handler.py
# Public Functions: exported callables and classes defined in this module
# Private Helpers: internal helpers and private methods defined in this module
# Key Semantic Blocks: main workflow paths and state transitions in this module
# Critical Flows: preserve existing runtime behavior and integrations
# Verification: python -m py_compile, python -m ruff check ., python -m pytest -q
# CHANGE_SUMMARY: Added file-local module metadata and declaration contracts.

import io
from typing import List

import pandas as pd

from config.settings import UPLOADS_CONFIG
from utils.logger import logger


DEFAULT_MAX_FILE_SIZE_MB = float(UPLOADS_CONFIG.get("max_file_size_mb", 5))
DEFAULT_MAX_ROWS = int(UPLOADS_CONFIG.get("max_rows", 1000))

# CLASS_CONTRACT: FileParsingError
# Purpose: Carry localized upload parsing error keys and message parameters.
# LINKS: requirements.xml#UC-001
class FileParsingError(ValueError):
    # FUNCTION_CONTRACT: __init__
    # Purpose: Initialize the surrounding object state.
    # Input: message_key (str), **message_kwargs (object)
    # Output: None
    # Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
    # Business Rules: Preserves the current validation and control flow for this call path.
    # Failure Modes: Propagates upstream exceptions and existing fallback paths.
    # LINKS: requirements.xml#UC-001
    def __init__(self, message_key: str, **message_kwargs: object) -> None:
        super().__init__(message_key)
        self.message_key = message_key
        self.message_kwargs = message_kwargs

# CLASS_CONTRACT: FileHandler
# Purpose: Validate uploaded files and extract URL lists from supported formats.
# LINKS: requirements.xml#UC-001
class FileHandler:
    # FUNCTION_CONTRACT: _file_size_bytes
    # Purpose: Implement the  file size bytes helper for this module.
    # Input: uploaded_file (Any)
    # Output: int
    # Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
    # Business Rules: Preserves the current validation and control flow for this call path.
    # Failure Modes: Propagates upstream exceptions and existing fallback paths.
    # LINKS: requirements.xml#UC-001
    @staticmethod
    def _file_size_bytes(uploaded_file) -> int:
        if hasattr(uploaded_file, "size"):
            return int(uploaded_file.size)
        if hasattr(uploaded_file, "getbuffer"):
            return int(uploaded_file.getbuffer().nbytes)
        return len(uploaded_file.getvalue())
    # FUNCTION_CONTRACT: _validate_size
    # Purpose: Implement the  validate size helper for this module.
    # Input: uploaded_file (Any), filename (str), max_file_size_mb (float)
    # Output: None
    # Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
    # Business Rules: Preserves the current validation and control flow for this call path.
    # Failure Modes: Propagates upstream exceptions and existing fallback paths.
    # LINKS: requirements.xml#UC-001
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
    # FUNCTION_CONTRACT: _validate_row_count
    # Purpose: Implement the  validate row count helper for this module.
    # Input: values (List[str]), filename (str), max_rows (int)
    # Output: None
    # Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
    # Business Rules: Preserves the current validation and control flow for this call path.
    # Failure Modes: Propagates upstream exceptions and existing fallback paths.
    # LINKS: requirements.xml#UC-001
    @staticmethod
    def _validate_row_count(values: List[str], filename: str, max_rows: int) -> None:
        if max_rows > 0 and len(values) > max_rows:
            raise FileParsingError(
                "upload_file_too_many_rows",
                filename=filename,
                max_rows=max_rows,
            )
    # FUNCTION_CONTRACT: _resolve_csv_column
    # Purpose: Implement the  resolve csv column helper for this module.
    # Input: df (pd.DataFrame), input_mode (str)
    # Output: str
    # Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
    # Business Rules: Preserves the current validation and control flow for this call path.
    # Failure Modes: Propagates upstream exceptions and existing fallback paths.
    # LINKS: requirements.xml#UC-001
    @staticmethod
    def _resolve_csv_column(df: pd.DataFrame, input_mode: str) -> str:
        lowered = {str(col).lower(): col for col in df.columns}
        if input_mode == "keyword":
            for candidate in ("keyword", "keywords"):
                if candidate in lowered:
                    return lowered[candidate]
        elif "url" in lowered:
            return lowered["url"]

        return df.columns[0]
    # FUNCTION_CONTRACT: parse_file
    # Purpose: Implement the parse file helper for this module.
    # Input: uploaded_file (Any), input_mode (str = 'url'), max_file_size_mb (float = DEFAULT_MAX_FILE_SIZE_MB), max_rows (int = DEFAULT_MAX_ROWS)
    # Output: List[str]
    # Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
    # Business Rules: Preserves the current validation and control flow for this call path.
    # Failure Modes: Propagates upstream exceptions and existing fallback paths.
    # LINKS: requirements.xml#UC-001
    @staticmethod
    def parse_file(
        uploaded_file,
        input_mode: str = "url",
        max_file_size_mb: float = DEFAULT_MAX_FILE_SIZE_MB,
        max_rows: int = DEFAULT_MAX_ROWS,
    ) -> List[str]:
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
