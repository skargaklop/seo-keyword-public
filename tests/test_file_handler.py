import io

import pytest

from utils.file_handler import FileHandler, FileParsingError


# Purpose:  UploadedFile implementation
class _UploadedFile(io.BytesIO):
    # Purpose:   init   implementation
    def __init__(self, name: str, content: bytes, size: int | None = None) -> None:
        super().__init__(content)
        self.name = name
        self.size = size if size is not None else len(content)


# Purpose: TestFileHandler implementation
class TestFileHandler:
    # Purpose: Test parse txt keywords for keyword mode
    def test_parse_txt_keywords_for_keyword_mode(self) -> None:
        uploaded = _UploadedFile(
            "keywords.txt",
            b"alpha\n beta \n\nalpha\n",
        )

        parsed = FileHandler.parse_file(uploaded, input_mode="keyword")

        assert parsed == ["alpha", "beta", "alpha"]

    # Purpose: Test parse csv prefers keyword column in keyword mode
    def test_parse_csv_prefers_keyword_column_in_keyword_mode(self) -> None:
        uploaded = _UploadedFile(
            "keywords.csv",
            b"url,keyword,keywords\nhttps://example.com,alpha,group-a\nhttps://example.org,beta,group-b\n",
        )

        parsed = FileHandler.parse_file(uploaded, input_mode="keyword")

        assert parsed == ["alpha", "beta"]

    # Purpose: Test parse csv falls back to first column in keyword mode
    def test_parse_csv_falls_back_to_first_column_in_keyword_mode(self) -> None:
        uploaded = _UploadedFile(
            "keywords.csv",
            b"seed,notes\nalpha,one\nbeta,two\n",
        )

        parsed = FileHandler.parse_file(uploaded, input_mode="keyword")

        assert parsed == ["alpha", "beta"]

    # Purpose: Test parse csv prefers url column in url mode
    def test_parse_csv_prefers_url_column_in_url_mode(self) -> None:
        uploaded = _UploadedFile(
            "urls.csv",
            b"keyword,url\nalpha,https://example.com\nbeta,https://example.org\n",
        )

        parsed = FileHandler.parse_file(uploaded, input_mode="url")

        assert parsed == ["https://example.com", "https://example.org"]

    # Purpose: Test rejects files larger than configured limit
    def test_rejects_files_larger_than_configured_limit(self) -> None:
        uploaded = _UploadedFile("urls.txt", b"https://example.com\n", size=6 * 1024 * 1024)

        with pytest.raises(FileParsingError):
            FileHandler.parse_file(uploaded, input_mode="url", max_file_size_mb=5, max_rows=100)

    # Purpose: Test rejects csv when row limit is exceeded
    def test_rejects_csv_when_row_limit_is_exceeded(self) -> None:
        uploaded = _UploadedFile(
            "urls.csv",
            b"url\nhttps://example.com\nhttps://example.org\nhttps://example.net\n",
        )

        with pytest.raises(FileParsingError):
            FileHandler.parse_file(uploaded, input_mode="url", max_file_size_mb=5, max_rows=2)

    # Purpose: Test accepts uppercase extensions
    def test_accepts_uppercase_extensions(self) -> None:
        uploaded = _UploadedFile(
            "URLS.CSV",
            b"url\nhttps://example.com\n",
        )

        parsed = FileHandler.parse_file(uploaded, input_mode="url")

        assert parsed == ["https://example.com"]