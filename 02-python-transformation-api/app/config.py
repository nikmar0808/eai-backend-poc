from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class ApplicationSettings(BaseSettings):
    """
    Centralized configuration engine for the enterprise transformation layer.
    Automatically merges operating system environment variables with local config overrides.
    """
    # Application Deployment Parameters
    APP_TITLE: str = "Enterprise Integration Transformation API"
    APP_VERSION: str = "1.0.0"
    
    # Network Layer Settings
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8082
    
    # Inbound security key contract. Required: supplied by the environment or a local .env file.
    # Deliberately not assigned a value here, so that Pydantic will raise a validation error
    # if it is not provided in the environment or .env file to enforce fail-fast security posture.
    # This is a critical security measure to prevent unauthorized access.
    # If we declare just API_SECURITY_TOKEN: str, mypy fails on this, as it expects a constructor argument
    # Instead we use Field(default=...) to indicate that it is required but without a default value.
    # Pydantic Settings will still look for API_SECURITY_TOKEN in the environment or .env file
    # and raise a validation error if it is missing.
    API_SECURITY_TOKEN: str = Field(default=...)

    # Instructs Pydantic to read configuration from a local file if available
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

# Initialize a singleton instance of our settings model for the entire app package
settings = ApplicationSettings()
