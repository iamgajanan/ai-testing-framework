class AITestingFrameworkError(Exception):
    """Base framework exception."""


class TestDefinitionError(AITestingFrameworkError):
    """Raised when a test definition is invalid."""


class StepExecutionError(AITestingFrameworkError):
    """Raised when a browser step fails."""


class ValidationError(AITestingFrameworkError):
    """Raised when validation configuration is invalid."""
