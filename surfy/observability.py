import logging
import os
import urllib.error
import urllib.request

logger = logging.getLogger(__name__)


def create_langfuse_handler():
    """Langfuse 환경변수가 설정되어 있으면 CallbackHandler를 생성, 없으면 None 반환."""
    public_key = os.environ.get("LANGFUSE_PUBLIC_KEY")
    secret_key = os.environ.get("LANGFUSE_SECRET_KEY")

    if not public_key or not secret_key:
        return None

    try:
        from langfuse.langchain import CallbackHandler

        base_url = os.environ.get("LANGFUSE_BASE_URL", "http://localhost:3000")
        try:
            urllib.request.urlopen(f"{base_url}/api/public/health", timeout=2)
        except (urllib.error.URLError, OSError, Exception):
            logger.warning("Langfuse unreachable at %s — tracing disabled", base_url)
            return None

        handler = CallbackHandler()
        logger.info("Langfuse tracing enabled (host=%s)", os.environ.get("LANGFUSE_BASE_URL", "default"))
        return handler
    except ImportError:
        logger.warning("langfuse package not installed — tracing disabled")
        return None
