import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    APP_ID = os.getenv("APP_ID")
    APP_SECRET = os.getenv("APP_SECRET")
    # Default to generic feishu.cn, but allow override for tenant-specific domains
    FEISHU_DOC_HOST = os.getenv("FEISHU_DOC_HOST", "https://www.feishu.cn")

    @classmethod
    def validate(cls):
        if not cls.APP_ID:
            raise ValueError("APP_ID not found in environment variables.")
        if not cls.APP_SECRET:
            raise ValueError("APP_SECRET not found in environment variables.")
