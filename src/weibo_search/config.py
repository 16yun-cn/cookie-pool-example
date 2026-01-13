"""Configuration management using pydantic-settings."""

import logging
import os
import sys
from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="WEIBO_",
        case_sensitive=False,
        extra="ignore",  # Ignore unknown env vars from old config
    )

    # Debug mode
    debug: bool = Field(default=False, description="Enable debug mode with verbose logging")

    # Redis
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL",
    )

    # Proxy (no-auth by default)
    proxy_host: str = Field(default="localhost", description="Proxy host")
    proxy_port: int = Field(default=18080, description="Proxy port")
    proxy_user: Optional[str] = Field(default=None, description="Proxy username (optional)")
    proxy_pass: Optional[str] = Field(default=None, description="Proxy password (optional)")

    # Browser settings
    browser_headless: bool = Field(default=True, description="Run browser in headless mode")
    browser_timeout: int = Field(default=30, description="Browser operation timeout in seconds")
    chrome_path: Optional[str] = Field(default=None, description="Path to Chrome/Chromium binary")

    # Cookie settings
    cookie_ttl: int = Field(default=3600, description="Cookie TTL in seconds")
    cookie_wait_timeout: int = Field(default=15, description="Wait time for SUB cookie in seconds")

    # Search settings
    max_pages: int = Field(default=10, description="Max pages to crawl per keyword")
    max_retries: int = Field(default=3, description="Max retries on failure")
    search_delay: float = Field(default=1.0, description="Delay between search requests in seconds")

    # Output
    log_dir: str = Field(default="logs", description="Log directory")

    # print all settings
    def __repr__(self):
        return f"Settings({self.model_dump()})"

    @property
    def proxy_url(self) -> str:
        """Get proxy URL (with or without authentication)."""
        if self.proxy_user and self.proxy_pass:
            return f"http://{self.proxy_user}:{self.proxy_pass}@{self.proxy_host}:{self.proxy_port}"
        return f"http://{self.proxy_host}:{self.proxy_port}"


class QueueConfig:
    """RQ Queue names."""

    COOKIE = "queue:cookie"
    SEARCH = "queue:search"

    ALL = [COOKIE, SEARCH]


def setup_logging(debug: bool = False) -> None:
    """Setup logging configuration."""
    level = logging.DEBUG if debug else logging.INFO

    # Configure root logger
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stderr,
    )

    # Set level for our loggers
    for name in ["weibo.cookie", "weibo.search", "weibo.storage"]:
        logging.getLogger(name).setLevel(level)

    if debug:
        # More detailed format for debug
        for handler in logging.root.handlers:
            handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s [%(levelname)s] %(name)s:%(lineno)d: %(message)s",
                    datefmt="%H:%M:%S",
                )
            )


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the weibo prefix."""
    return logging.getLogger(f"weibo.{name}")


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    settings = Settings()
    # Auto-setup logging based on debug mode or env var
    debug = settings.debug or os.environ.get("WEIBO_DEBUG", "0") == "1"
    setup_logging(debug)
    get_logger("config").info(settings)
    return settings
