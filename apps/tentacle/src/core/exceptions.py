"""
Core exceptions for the Tentacle system.
"""


class TentacleException(Exception):
    """Base exception for all Tentacle errors"""
    pass


class AgentExecutionError(TentacleException):
    """Error during agent execution"""
    pass


class ValidationError(TentacleException):
    """Validation error"""
    pass


class ConfigurationError(TentacleException):
    """Configuration error"""
    pass


# Capability-related exceptions
class CapabilityError(TentacleException):
    """Base capability error"""
    pass


class CapabilityNotFoundError(CapabilityError):
    """Capability not found in registry"""
    pass


class CapabilityBindingError(CapabilityError):
    """Error binding capability to agent"""
    pass


# LLM-related exceptions
class LLMError(TentacleException):
    """LLM operation error"""
    pass


class PromptError(LLMError):
    """Prompt-related error"""
    pass


# State-related exceptions
class StateError(TentacleException):
    """State management error"""
    pass


class BudgetError(TentacleException):
    """Budget-related error"""
    pass
