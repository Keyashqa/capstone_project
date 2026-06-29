import logging
import os

from google.genai import types


def check_env_variables() -> None:
    """
    Ensure GOOGLE_API_KEY is set in the environment.
    Export it or load via dotenv before running.
    """
    if not os.getenv("GOOGLE_API_KEY"):
        raise RuntimeError(
            """
            GOOGLE_API_KEY environment variable is not set.
            Please export it or load it from a .env file before running.
            """
        )


def configure_logging() -> None:
    """
    Configure process-wide logging.

    """

    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(name)s - %(message)s'
    )


APP_NAME = "DaedalusApp"
USER_ID = "daedalus_user"
MODEL = "gemini-2.5-flash"
# MODEL = "gemini-2.0-flash"
MODEL_LITE = "gemini-2.5-flash-lite"

retry_options = types.HttpRetryOptions(
    attempts=5,
    exp_base=7,
    initial_delay=1,
    http_status_codes=[429, 500, 503, 504],
)
