"""Utility functions for WordPress scraper."""

import re
import json
from typing import Any, Dict, Optional


def strip_html_tags(text: Optional[str]) -> str:
    """
    Remove HTML tags from text.

    Args:
        text: Text potentially containing HTML tags

    Returns:
        Clean text without HTML tags
    """
    if not text:
        return ""

    clean = re.compile('<.*?>')
    return re.sub(clean, '', text)


def extract_rendered_field(field: Optional[Dict[str, Any]], key: str = 'rendered') -> str:
    """
    Extract rendered field from WordPress API response.

    Args:
        field: Dictionary containing the field
        key: Key to extract (default: 'rendered')

    Returns:
        Extracted value or empty string
    """
    if not field or not isinstance(field, dict):
        return ""
    return field.get(key, "")


def safe_join(items: list, separator: str = ',') -> str:
    """
    Safely join list items into a string.

    Args:
        items: List of items to join
        separator: String to use as separator

    Returns:
        Joined string
    """
    if not items:
        return ""
    return separator.join(str(item) for item in items)


def serialize_to_json(data: Any) -> str:
    """
    Serialize data to JSON string.

    Args:
        data: Data to serialize

    Returns:
        JSON string
    """
    try:
        return json.dumps(data)
    except (TypeError, ValueError):
        return ""


def extract_post_fields(post: Dict[str, Any], strip_html: bool = True) -> Dict[str, Any]:
    """
    Extract and transform post fields from WordPress API response.

    Args:
        post: Raw post data from API
        strip_html: Whether to strip HTML tags from content fields

    Returns:
        Dictionary with extracted and transformed fields
    """
    # Extract basic fields
    post_id = post.get('id')
    date = post.get('date')
    date_gmt = post.get('date_gmt')
    guid = extract_rendered_field(post.get('guid'))
    modified = post.get('modified')
    modified_gmt = post.get('modified_gmt')
    slug = post.get('slug')
    status = post.get('status')
    type_ = post.get('type')
    link = post.get('link')

    # Extract rendered fields
    title = extract_rendered_field(post.get('title'))
    content = extract_rendered_field(post.get('content'))
    excerpt = extract_rendered_field(post.get('excerpt'))

    # Strip HTML if requested
    if strip_html:
        content = strip_html_tags(content)
        excerpt = strip_html_tags(excerpt)

    # Extract meta fields
    meta = post.get('meta', {})
    meta_source = meta.get('source') if isinstance(meta, dict) else None
    meta_author = meta.get('author') if isinstance(meta, dict) else None

    # Extract other fields
    author = post.get('author')
    featured_media = post.get('featured_media')
    comment_status = post.get('comment_status')
    ping_status = post.get('ping_status')
    sticky = int(post.get('sticky', False))
    template = post.get('template')
    format_ = post.get('format')

    # Serialize complex fields
    meta_json = serialize_to_json(post.get('meta'))
    categories = safe_join(post.get('categories', []))
    tags = safe_join(post.get('tags', []))
    area = safe_join(post.get('area', []))
    alerts = safe_join(post.get('alerts', []))
    countries = safe_join(post.get('countries', []))
    class_list = safe_join(post.get('class_list', []))

    return {
        'id': post_id,
        'date': date,
        'date_gmt': date_gmt,
        'guid': guid,
        'modified': modified,
        'modified_gmt': modified_gmt,
        'slug': slug,
        'status': status,
        'type': type_,
        'link': link,
        'title': title,
        'content': content,
        'excerpt': excerpt,
        'author': author,
        'meta_source': meta_source,
        'meta_author': meta_author,
        'featured_media': featured_media,
        'comment_status': comment_status,
        'ping_status': ping_status,
        'sticky': sticky,
        'template': template,
        'format': format_,
        'meta': meta_json,
        'categories': categories,
        'tags': tags,
        'area': area,
        'alerts': alerts,
        'countries': countries,
        'class_list': class_list
    }
