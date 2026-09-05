"""EasyNews API client for authentication and API requests."""
import xbmcgui
from functools import cached_property
from resources.lib.modules.globals import g

EASYNEWS_AUTH_KEY = "easynews.auth"
EASYNEWS_STATUS_KEY = "easynews.premiumstatus"
EASYNEWS_USERNAME_KEY = "easynews.username"


class EasyNews:
    """EasyNews premium service integration."""
    
    def __init__(self):
        self.base_url = "https://members.easynews.com/login"
        self.timeout = 10
        self._load_settings()
    
    @cached_property
    def session(self):
        """Create a requests session with retry logic."""
        import requests
        from requests.adapters import HTTPAdapter
        from urllib3 import Retry
        
        session = requests.Session()
        retries = Retry(total=3, backoff_factor=0.1, status_forcelist=[500, 502, 503, 504])
        session.mount("https://", HTTPAdapter(max_retries=retries))
        return session
    
    def _load_settings(self):
        """Load EasyNews settings from Kodi."""
        self.username = g.get_setting("easynews.username") or ""
        self.password = g.get_setting("easynews.password") or ""
        self.auth_token = g.get_setting(EASYNEWS_AUTH_KEY)
        self.premium_status = g.get_setting(EASYNEWS_STATUS_KEY) or ""
    
    def test_auth(self):
        """Test EasyNews authentication with supplied credentials.
        
        Makes an API request to verify the credentials and sets premium status.
        Shows a popup notification with the result.
        """
        if not self.username or not self.password:
            xbmcgui.Dialog().notification(
                g.ADDON_NAME,
                "Please enter EasyNews username and password",
                xbmcgui.NOTIFICATION_WARNING,
                3000
            )
            g.log("EasyNews auth test failed: Missing credentials", "warning")
            return False
        
        try:
            # Test authentication by making a simple API call
            response = self.session.get(
                f"{self.base_url}/test",
                auth=(self.username, self.password),
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                # Authentication successful
                try:
                    data = response.json()
                    # Set status to Premium if we got a valid response
                    status = "Premium"
                    g.set_setting(EASYNEWS_STATUS_KEY, status)
                    g.set_setting(EASYNEWS_USERNAME_KEY, self.username)
                    
                    g.log(f"EasyNews authentication successful for {self.username}", "info")
                    xbmcgui.Dialog().notification(
                        g.ADDON_NAME,
                        f"EasyNews Authentication Successful\nStatus: {status}",
                        xbmcgui.NOTIFICATION_INFO,
                        3000
                    )
                    return True
                except Exception as e:
                    g.log(f"EasyNews response parsing error: {e}", "error")
                    xbmcgui.Dialog().notification(
                        g.ADDON_NAME,
                        "Authentication failed: Invalid response",
                        xbmcgui.NOTIFICATION_ERROR,
                        3000
                    )
                    return False
            
            elif response.status_code == 401:
                # Invalid credentials
                g.log("EasyNews auth test failed: Invalid credentials (401)", "warning")
                xbmcgui.Dialog().notification(
                    g.ADDON_NAME,
                    "EasyNews Authentication Failed\nInvalid credentials",
                    xbmcgui.NOTIFICATION_ERROR,
                    3000
                )
                return False
            
            else:
                # Other error
                g.log(f"EasyNews auth test failed with status {response.status_code}", "warning")
                xbmcgui.Dialog().notification(
                    g.ADDON_NAME,
                    f"EasyNews Authentication Failed\nStatus: {response.status_code}",
                    xbmcgui.NOTIFICATION_ERROR,
                    3000
                )
                return False
        
        except Exception as e:
            g.log(f"EasyNews authentication test error: {e}", "error")
            xbmcgui.Dialog().notification(
                g.ADDON_NAME,
                f"EasyNews Connection Error\n{str(e)}",
                xbmcgui.NOTIFICATION_ERROR,
                3000
            )
            return False
    
    def get_account_status(self):
        """Get EasyNews account status.
        
        Returns the premium status stored in settings.
        """
        return g.get_setting(EASYNEWS_STATUS_KEY) or "Unknown"
    
    @staticmethod
    def is_service_enabled():
        """Check if EasyNews service is enabled and authenticated."""
        return (
            g.get_bool_setting("easynews.enabled") and
            g.get_setting(EASYNEWS_AUTH_KEY) is not None
        )
