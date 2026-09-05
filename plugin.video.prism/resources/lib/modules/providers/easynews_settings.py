"""Easynews provider settings configuration.

This module defines all available settings for the Easynews provider.
Settings are automatically picked up by the configure_provider_package.py
window when a user configures the Easynews provider package.
"""

# Easynews settings definition
# These settings will be automatically loaded into the database when Easynews is installed
EASYNEWS_SETTINGS = [
    {
        "id": "easynews.username",
        "label": "Easynews Username",
        "type": "str",
        "visible": True,
        "default": "",
        "definition": {
            "sensitive": True,  # Masks with *******
            "help": "Your Easynews account username"
        }
    },
    {
        "id": "easynews.password",
        "label": "Easynews Password",
        "type": "str",
        "visible": True,
        "default": "",
        "definition": {
            "sensitive": True,  # Masks with *******
            "help": "Your Easynews account password"
        }
    },
    {
        "id": "easynews.api_key",
        "label": "Easynews API Key",
        "type": "str",
        "visible": True,
        "default": "",
        "definition": {
            "sensitive": True,  # Masks with *******
            "help": "Optional: Your Easynews API key for enhanced features"
        }
    },
    {
        "id": "easynews.enable_ssl",
        "label": "Enable SSL/TLS",
        "type": "bool",
        "visible": True,
        "default": True,
        "definition": {
            "help": "Use secure connection for Easynews API requests"
        }
    },
    {
        "id": "easynews.connection_timeout",
        "label": "Connection Timeout (seconds)",
        "type": "int",
        "visible": True,
        "default": 10,
        "definition": {
            "help": "Timeout for Easynews API requests"
        }
    },
    {
        "id": "easynews.max_results",
        "label": "Maximum Results Per Query",
        "type": "int",
        "visible": True,
        "default": 100,
        "definition": {
            "help": "Maximum number of search results to return from Easynews"
        }
    },
]


def get_easynews_settings():
    """
    Returns the Easynews settings configuration.
    
    Returns:
        list: List of setting dictionaries for Easynews provider
    """
    return EASYNEWS_SETTINGS
