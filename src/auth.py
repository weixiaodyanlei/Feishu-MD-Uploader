import lark_oapi as lark
from .config import Config

def get_client():
    """
    Initialize and return a Lark client.
    """
    Config.validate()
    client = lark.Client.builder() \
        .app_id(Config.APP_ID) \
        .app_secret(Config.APP_SECRET) \
        .log_level(lark.LogLevel.DEBUG) \
        .build()
    return client
