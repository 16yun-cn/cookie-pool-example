"""Parse Weibo search API responses into structured data."""

from typing import Any, Optional

from weibo_search.config import get_logger
from weibo_search.models import SearchResult, WeiboPost, WeiboUser

logger = get_logger("search")


def parse_search_response(
    keyword: str,
    page: int,
    raw_response: dict[str, Any],
    cookie_bundle_id: Optional[str] = None,
) -> SearchResult:
    """Parse raw Weibo API response into SearchResult.
    
    Args:
        keyword: Search keyword
        page: Page number
        raw_response: Raw API response dict
        cookie_bundle_id: ID of cookie bundle used
        
    Returns:
        SearchResult with parsed posts
    """
    posts = []
    total_cards = 0
    
    try:
        data = raw_response.get("data", {})
        cards = data.get("cards", [])
        total_cards = len(cards)
        
        for card in cards:
            card_type = card.get("card_type")
            
            # Type 9 = normal post
            if card_type == 9:
                mblog = card.get("mblog")
                if mblog:
                    post = _parse_mblog(mblog)
                    if post:
                        posts.append(post)
            
            # Type 11 = card group (contains nested cards)
            elif card_type == 11:
                card_group = card.get("card_group", [])
                for sub_card in card_group:
                    if sub_card.get("card_type") == 9:
                        mblog = sub_card.get("mblog")
                        if mblog:
                            post = _parse_mblog(mblog)
                            if post:
                                posts.append(post)
        
        logger.debug(f"Parsed {len(posts)} posts from {total_cards} cards")
        
    except Exception as e:
        logger.error(f"Parse error: {e}")
    
    return SearchResult(
        keyword=keyword,
        page=page,
        total_cards=total_cards,
        posts=posts,
        raw_response=raw_response,
        cookie_bundle_id=cookie_bundle_id,
    )


def _parse_mblog(mblog: dict[str, Any]) -> Optional[WeiboPost]:
    """Parse a single mblog dict into WeiboPost."""
    try:
        # Parse user
        user_data = mblog.get("user", {})
        user = WeiboUser(
            id=str(user_data.get("id", "")),
            screen_name=user_data.get("screen_name", ""),
            profile_url=user_data.get("profile_url"),
            avatar_hd=user_data.get("avatar_hd"),
            verified=user_data.get("verified", False),
            verified_type=user_data.get("verified_type", -1),
        )
        
        # Parse pics
        pics = []
        pics_data = mblog.get("pics", [])
        for pic in pics_data:
            url = pic.get("large", {}).get("url") or pic.get("url")
            if url:
                pics.append(url)
        
        # Parse video URL
        video_url = None
        page_info = mblog.get("page_info", {})
        if page_info.get("type") == "video":
            urls = page_info.get("urls", {})
            video_url = urls.get("mp4_720p_mp4") or urls.get("mp4_hd_mp4") or urls.get("mp4_ld_mp4")
        
        # Long text check
        is_long_text = mblog.get("isLongText", False)
        
        post = WeiboPost(
            id=str(mblog.get("id", "")),
            mid=str(mblog.get("mid", "")),
            text=mblog.get("text", ""),
            text_raw=mblog.get("text_raw"),
            created_at=mblog.get("created_at", ""),
            source=mblog.get("source", ""),
            user=user,
            reposts_count=mblog.get("reposts_count", 0),
            comments_count=mblog.get("comments_count", 0),
            attitudes_count=mblog.get("attitudes_count", 0),
            pics=pics,
            video_url=video_url,
            is_long_text=is_long_text,
        )
        
        return post
        
    except Exception as e:
        logger.debug(f"Failed to parse mblog: {e}")
        return None
