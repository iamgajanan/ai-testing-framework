from ai_testing_framework.automation.element_locator import AIElementLocator


def test_locator_uses_heuristic_button():
    class FakeLocator:
        def count(self):
            return 1

    class FakePage:
        def get_by_role(self, role, name=None):
            assert role == "button"
            assert name is not None
            return FakeLocator()

    locator = AIElementLocator(provider="none")
    result = locator._heuristic(FakePage(), "the Search button")
    assert result is not None


def test_locator_requires_description():
    locator = AIElementLocator(provider="none")
    try:
        locator.find_element(object(), "")
    except ValueError as exc:
        assert "description" in str(exc).lower()
    else:
        raise AssertionError("Expected empty description to fail")
