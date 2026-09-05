from resources.lib.modules.providers.settings import SettingsManager


def get_setting(package_name, setting_id):
    """
    Retrieves a setting value for a provider package
    :param package_name: name of package
    :type package_name: str
    :param setting_id: ID of the setting to retrieve
    :type setting_id: str
    :return: Value of settings
    :rtype: object
    """
    return SettingsManager().get_setting(package_name, setting_id)


def set_setting(package_name, setting_id, value):
    """
    Sets the value of a setting for a provider package
    :param package_name: name of package
    :type package_name: str
    :param setting_id: ID of the setting to set
    :type setting_id: str
    :param value: New value for setting
    :rtype value: object
    :return: Value of settings
    :rtype: object
    """
    SettingsManager().set_setting(package_name, setting_id, value)

def get_easynews_credentials():
    """
    Retrieves Easynews credentials from settings
    :return: Tuple of (username, password) or (None, None)
    :rtype: tuple
    """
    from resources.lib.modules.globals import g
    username = g.get_setting("easynews.username") or ""
    password = g.get_setting("easynews.password") or ""
    return (username.strip(), password.strip()) if username and password else (None, None)
