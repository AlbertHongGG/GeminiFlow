import logging
import sys
from gemini_flow.config import AppConfig

def setup_logging(config: AppConfig) -> None:
    level = logging.DEBUG if config.debug else logging.INFO
    
    # Configure the root logger
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout)
        ],
        force=True
    )
    
    # Suppress verbose loggers from external libraries
    logging.getLogger("aiohttp").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    
    # Our app logger
    logger = logging.getLogger("gemini_flow")
    logger.setLevel(level)
    if config.debug:
        logger.debug("Debug logging enabled.")
