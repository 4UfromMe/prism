"""EasyNews API client for authentication and API requests."""
import requests
import xbmcgui
from functools import cached_property
from resources.lib.modules.globals import g

EASYNEWS_AUTH_KEY = "easynews.auth"
EASYNEWS_STATUS_KEY = "easynews.premiumstatus"
EASYNEWS_USERNAME_KEY = "easynews.username"


class EasyNews:
    """EasyNews premium service integration."""
    
    LOGIN_URL = "https://members.easynews.com/login/"
    DEFAULT_TIMEOUT = 120
    
    def __init__(self):
        self.username = g.get_setting("easynews.username") or ""
        self.password = g.get_setting("easynews.password") or ""
        self.session = requests.Session()
        self.is_logged_in = False
        self._setup_session()
        self._load_settings()
    
    def _setup_session(self):
        """Configure session with proper headers."""
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/json,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
            'X-Requested-With': 'XMLHttpRequest',
            'Referer': 'https://members.easynews.com/',
        })
    
    def _load_settings(self):
        """Load EasyNews settings from Kodi."""
        self.auth_token = g.get_setting(EASYNEWS_AUTH_KEY)
        self.premium_status = g.get_setting(EASYNEWS_STATUS_KEY) or ""
    
    def _secure_request(self, method: str, url: str, **kwargs) -> requests.Response or None:
        """Make a secure HTTP request with proper error handling.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            url: URL to request
            **kwargs: Additional arguments to pass to requests
            
        Returns:
            Response object or None on error
        """
        try:
            g.log(f"[REQUEST] {method} {url}", "info")
            
            response = self.session.request(
                method, url,
                timeout=kwargs.pop('timeout', self.DEFAULT_TIMEOUT),
                **kwargs
            )
            
            return response
            
        except requests.exceptions.Timeout:
            g.log(f"[ERROR] Request timeout for {url}", "error")
            return None
        except requests.exceptions.ConnectionError:
            g.log(f"[ERROR] Connection error for {url}", "error")
            return None
        except requests.exceptions.RequestException as e:
            g.log(f"[ERROR] Request failed: {e}", "error")
            return None
        except Exception as e:
            g.log(f"[ERROR] Unexpected error: {e}", "error")
            return None
    
    def _wipe_response(self, response: requests.Response) -> None:
        """Safely close and wipe a response object."""
        try:
            if response and hasattr(response, 'content'):
                response.content  # Force content to be read
            if response:
                response.close()
        except Exception:
            pass
    
    def test_auth(self) -> bool:
        """Test EasyNews authentication with supplied credentials.
        
        Makes a login request to verify the credentials and sets premium status.
        Shows a popup notification with the result.
        
        Returns:
            bool: True if authentication successful, False otherwise
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
        
        get_resp = None
        post_resp = None
        
        try:
            g.log("[*] Getting EasyNews login page...", "info")
            
            # GET request to load login page
            get_resp = self._secure_request('GET', self.LOGIN_URL, timeout=30)
            
            if get_resp is None or get_resp.status_code != 200:
                status_code = get_resp.status_code if get_resp else 'no response'
                g.log(f"[LOGIN] Failed to load page: {status_code}", "error")
                xbmcgui.Dialog().notification(
                    g.ADDON_NAME,
                    f"EasyNews Connection Failed\nStatus: {status_code}",
                    xbmcgui.NOTIFICATION_ERROR,
                    3000
                )
                if get_resp:
                    self._wipe_response(get_resp)
                return False
            
            # Prepare login data
            login_data = {
                'user': self.username,
                'pass': self.password
            }
            
            g.log("[*] Submitting EasyNews login form...", "info")
            
            # POST request to submit login
            post_resp = self._secure_request(
                'POST', 
                self.LOGIN_URL,
                data=login_data,
                allow_redirects=True,
                timeout=30
            )
            
            if post_resp is None:
                g.log("[LOGIN] No response from server", "error")
                xbmcgui.Dialog().notification(
                    g.ADDON_NAME,
                    "EasyNews Connection Failed\nNo response from server",
                    xbmcgui.NOTIFICATION_ERROR,
                    3000
                )
                self._wipe_response(get_resp)
                return False
            
            if post_resp.status_code != 200:
                g.log(f"[LOGIN] POST failed: {post_resp.status_code}", "error")
                xbmcgui.Dialog().notification(
                    g.ADDON_NAME,
                    f"EasyNews Authentication Failed\nStatus: {post_resp.status_code}",
                    xbmcgui.NOTIFICATION_ERROR,
                    3000
                )
                self._wipe_response(get_resp)
                self._wipe_response(post_resp)
                return False
            
            # Check if still on login page (invalid credentials)
            try:
                post_content = post_resp.content.decode('utf-8', errors='ignore')
                is_still_on_login = '<form name="login"' in post_content or '/login/' in post_resp.url
            except Exception as e:
                g.log(f"[LOGIN] Error checking response content: {e}", "error")
                is_still_on_login = True
            
            if is_still_on_login:
                g.log("[LOGIN] Still on login page - credentials invalid or auth failed", "error")
                xbmcgui.Dialog().notification(
                    g.ADDON_NAME,
                    "EasyNews Authentication Failed\nInvalid credentials",
                    xbmcgui.NOTIFICATION_ERROR,
                    3000
                )
                self._wipe_response(get_resp)
                self._wipe_response(post_resp)
                return False
            
            # Authentication successful
            self.is_logged_in = True
            status = "Premium"
            g.set_setting(EASYNEWS_STATUS_KEY, status)
            g.set_setting(EASYNEWS_USERNAME_KEY, self.username)
            
            g.log(f"[+] EasyNews authentication successful for {self.username}", "info")
            xbmcgui.Dialog().notification(
                g.ADDON_NAME,
                f"EasyNews Authentication Successful\nStatus: {status}",
                xbmcgui.NOTIFICATION_INFO,
                3000
            )
            return True
            
        except Exception as e:
            g.log(f"[LOGIN] Error: {e}", "error")
            g.log_stacktrace()
            xbmcgui.Dialog().notification(
                g.ADDON_NAME,
                f"EasyNews Connection Error\n{str(e)}",
                xbmcgui.NOTIFICATION_ERROR,
                3000
            )
            return False
        
        finally:
            if get_resp:
                try:
                    self._wipe_response(get_resp)
                except Exception:
                    pass
            if post_resp:
                try:
                    self._wipe_response(post_resp)
                except Exception:
                    pass
    
    def get_account_status(self) -> str:
        """Get EasyNews account status.
        
        Returns:
            str: Premium status stored in settings
        """
        return g.get_setting(EASYNEWS_STATUS_KEY) or "Unknown"
    
    @staticmethod
    def is_service_enabled() -> bool:
        """Check if EasyNews service is enabled and authenticated.
        
        Returns:
            bool: True if enabled and authenticated
        """
        return (
            g.get_bool_setting("easynews.enabled") and
            g.get_setting(EASYNEWS_AUTH_KEY) is not None
        )
