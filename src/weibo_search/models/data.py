"""Pydantic data models for Weibo search crawler."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class CookieBundle(BaseModel):
    """Cookie bundle containing all data from browser session."""

    id: str = Field(description="Unique cookie bundle ID")
    sub: str = Field(description="SUB cookie value")
    subp: Optional[str] = Field(default=None, description="SUBP cookie value")
    cookies: list[dict[str, Any]] = Field(default_factory=list, description="Full cookie list")
    user_agent: str = Field(description="User-Agent string used")
    platform: Optional[str] = Field(default=None, description="Platform string")
    user_agent_data: Optional[dict[str, Any]] = Field(default=None, description="Navigator.userAgentData")
    created_at: datetime = Field(default_factory=datetime.now)
    cookie_source: str = Field(default="browser", description="Source: browser or legacy")

    @property
    def is_expired(self) -> bool:
        """Check if cookie is expired (default 1 hour TTL)."""
        from weibo_search.config import get_settings

        settings = get_settings()
        age = (datetime.now() - self.created_at).total_seconds()
        return age > settings.cookie_ttl

    def get_cookie_header(self) -> str:
        """Build Cookie header string."""
        parts = [f"SUB={self.sub}"]
        if self.subp:
            parts.append(f"SUBP={self.subp}")
        return "; ".join(parts)


class KeywordTask(BaseModel):
    """Keyword task from JSONL input."""

    keyword: str = Field(description="Search keyword")
    category: Optional[str] = Field(default=None, description="Category for grouping")
    priority: int = Field(default=1, description="Priority level (1=highest)")


class WeiboUser(BaseModel):
    """Weibo user data from mblog."""

    id: str = Field(description="User ID")
    screen_name: str = Field(description="Display name")
    profile_url: Optional[str] = Field(default=None)
    avatar_hd: Optional[str] = Field(default=None)
    verified: bool = Field(default=False)
    verified_type: int = Field(default=-1)


class WeiboPost(BaseModel):
    """Parsed Weibo post data."""

    id: str = Field(description="Weibo ID")
    mid: str = Field(description="Message ID")
    text: str = Field(description="HTML content")
    text_raw: Optional[str] = Field(default=None, description="Plain text")
    created_at: str = Field(description="Creation time string")
    source: str = Field(default="", description="Post source")

    # User info
    user: WeiboUser

    # Engagement
    reposts_count: int = Field(default=0)
    comments_count: int = Field(default=0)
    attitudes_count: int = Field(default=0)

    # Media
    pics: list[str] = Field(default_factory=list)
    video_url: Optional[str] = Field(default=None)

    # Long text
    is_long_text: bool = Field(default=False)
    long_text: Optional[str] = Field(default=None)


class SearchResult(BaseModel):
    """Search result containing multiple posts."""

    keyword: str
    page: int
    total_cards: int = Field(default=0)
    posts: list[WeiboPost] = Field(default_factory=list)
    raw_response: Optional[dict[str, Any]] = Field(default=None)
    cookie_bundle_id: Optional[str] = Field(default=None)
    searched_at: datetime = Field(default_factory=datetime.now)
