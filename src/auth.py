import lark_oapi as lark
from .config import Config

def get_client(debug=False):
    """
    Initialize and return a Lark client.
    
    Args:
        debug: If True, enable DEBUG logging; otherwise use ERROR level.
    """
    Config.validate()
    
    # Choose log level based on debug flag
    log_level = lark.LogLevel.DEBUG if debug else lark.LogLevel.ERROR
    
    client = lark.Client.builder() \
        .app_id(Config.APP_ID) \
        .app_secret(Config.APP_SECRET) \
        .log_level(log_level) \
        .build()
    return client
