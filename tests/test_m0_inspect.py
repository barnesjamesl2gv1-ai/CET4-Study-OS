import zipfile

from backend.m0_inspect import inspect, inspect_file


def test_docx_is_readable_but_not_mock_ready(tmp_path):
    path = tmp_path / "sample.docx"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", '<w:document xmlns:w="x"><w:t>Question 1</w:t></w:document>')
    result = inspect([path])
    assert result["ready_for_mock"] is False
    assert result["files"][0]["text_characters"] == 10
    assert result["files"][0]["status"] == "needs_review"


def test_mismatched_extension_is_rejected(tmp_path):
    path = tmp_path / "fake.mp3"
    path.write_bytes(b"not an audio file")
    assert inspect_file(path)["status"] == "invalid"


def test_empty_directory_is_not_mock_ready(tmp_path):
    assert inspect([tmp_path])["files"] == []
    assert inspect([tmp_path])["ready_for_mock"] is False
