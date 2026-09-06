from ai_testing_framework.validators.file_validator import validate_file


def test_csv_file_validation(tmp_path):
    path = tmp_path / "sample.csv"
    path.write_text("First Name,Last Name\nAsha,Patil\n", encoding="utf-8")
    ok, reason, meta = validate_file(str(path), expected_filename="sample.csv", expected_extension=".csv", file_type="csv", expected_columns=["First Name", "Last Name"])
    assert ok, reason
    assert meta["size"] > 0


def test_json_file_validation(tmp_path):
    path = tmp_path / "data.json"
    path.write_text('{"success": true, "items": [1, 2]}', encoding="utf-8")
    ok, reason, _ = validate_file(str(path), file_type="json", json_path="success", expected=True)
    assert ok, reason


def test_file_content_regex(tmp_path):
    path = tmp_path / "hello.txt"
    path.write_text("Hello Framework", encoding="utf-8")
    ok, reason, _ = validate_file(str(path), text_contains="framework", pattern=r"Hello\s+Framework")
    assert ok, reason


def test_missing_file_fails(tmp_path):
    ok, reason, _ = validate_file(str(tmp_path / "missing.csv"))
    assert not ok
    assert "does not exist" in reason
