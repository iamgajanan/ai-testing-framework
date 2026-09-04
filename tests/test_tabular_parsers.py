from pathlib import Path

from openpyxl import Workbook

from ai_testing_framework.parsers.csv_parser import CSVParser
from ai_testing_framework.parsers.xlsx_parser import XLSXParser


def test_csv_parser():
    suite = CSVParser().parse(Path(__file__).parent / "test_data" / "sample_suite.csv")
    assert suite.name == "CSV Test Suite"
    assert len(suite.tests) == 1
    test = suite.tests[0]
    assert test.id == "TC-CSV-001"
    assert len(test.steps) == 3
    assert test.steps[0].value == "OpenAI"
    assert test.validations[0].type == "text_contains"
    assert test.validations[0].expected == "OpenAI"


def test_xlsx_parser(tmp_path):
    path = tmp_path / "suite.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["TestID", "Name", "URL", "Action", "Selector", "Value", "Expected", "ValidationType", "Validation"])
    sheet.append(["TC-XLSX-001", "Excel Search", "/", "type", "#query", "OpenAI", "", "", ""])
    sheet.append(["TC-XLSX-001", "Excel Search", "/", "click", "#submit", "", "", "", ""])
    sheet.append(["TC-XLSX-001", "Excel Search", "", "", "", "", "OpenAI", "text_contains", ""])
    workbook.save(path)

    suite = XLSXParser().parse(path)
    assert suite.name == "XLSX Test Suite"
    assert len(suite.tests) == 1
    assert suite.tests[0].id == "TC-XLSX-001"
    assert len(suite.tests[0].steps) == 2
    assert suite.tests[0].validations[0].expected == "OpenAI"
