"""WordPress API client for fetching posts."""

import logging
import time
from typing import List, Dict, Any, Optional, Generator
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


logger = logging.getLogger(__name__)


class WordPressAPIError(Exception):
    """Custom exception for WordPress API errors."""
    pass


class WordPressClient:
    """Client for interacting with WordPress REST API."""

    def __init__(self, base_url: str, per_page: int = 100, delay: float = 1.0):
        """
        Initialize WordPress API client.

        Args:
            base_url: Base URL for WordPress API (e.g., https://example.com/wp-json/wp/v2/posts/)
            per_page: Number of posts to fetch per page (max 100)
            delay: Delay between requests in seconds
        """
        self.base_url = base_url.rstrip('/')
        self.per_page = min(per_page, 100)  # WordPress API max is 100
        self.delay = delay
        self.session = self._create_session()

    def _create_session(self) -> requests.Session:
        """
        Create a requests session with retry logic.

        Returns:
            Configured requests session
        """
        session = requests.Session()

        # Configure retry strategy
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"]
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        return session

    def validate_endpoint(self) -> bool:
        """
        Validate that the WordPress API endpoint is accessible.

        Returns:
            True if endpoint is valid, False otherwise
        """
        try:
            response = self.session.get(self.base_url, params={'per_page': 1}, timeout=10)
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to validate endpoint: {e}")
            return False

    def fetch_page(self, page: int, additional_params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Fetch a single page of posts from WordPress API.

        Args:
            page: Page number to fetch (1-indexed)
            additional_params: Additional query parameters for the API request

        Returns:
            List of post dictionaries

        Raises:
            WordPressAPIError: If the request fails
        """
        params = {
            'per_page': self.per_page,
            'page': page
        }

        # Add any additional parameters
        if additional_params:
            params.update(additional_params)

        try:
            logger.debug(f"Fetching page {page} with {self.per_page} posts per page")
            response = self.session.get(self.base_url, params=params, timeout=30)
            response.raise_for_status()

            posts = response.json()

            # Get total pages from headers if available
            total_pages = response.headers.get('X-WP-TotalPages')
            total_posts = response.headers.get('X-WP-Total')

            if total_pages:
                logger.debug(f"Page {page}/{total_pages} (Total posts: {total_posts})")

            return posts

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 400:
                # Page out of range - no more posts
                logger.debug(f"Page {page} is out of range (no more posts)")
                return []
            else:
                raise WordPressAPIError(f"HTTP error on page {page}: {e}")

        except requests.exceptions.RequestException as e:
            raise WordPressAPIError(f"Request error on page {page}: {e}")

        except ValueError as e:
            raise WordPressAPIError(f"Invalid JSON response on page {page}: {e}")

    def fetch_all(
        self,
        start_page: int = 1,
        max_pages: Optional[int] = None,
        callback: Optional[callable] = None,
        additional_params: Optional[Dict[str, Any]] = None
    ) -> Generator[List[Dict[str, Any]], None, None]:
        """
        Fetch all posts from WordPress API, yielding pages.

        Args:
            start_page: Starting page number (1-indexed)
            max_pages: Maximum number of pages to fetch (None = all)
            callback: Optional callback function called after each page with (page, posts)
            additional_params: Additional query parameters for the API request

        Yields:
            Lists of post dictionaries for each page

        Raises:
            WordPressAPIError: If a request fails
        """
        page = start_page
        pages_fetched = 0

        while True:
            # Check if we've reached max_pages
            if max_pages and pages_fetched >= max_pages:
                logger.info(f"Reached maximum pages limit: {max_pages}")
                break

            # Fetch page
            posts = self.fetch_page(page, additional_params=additional_params)

            # Stop if no more posts
            if not posts:
                logger.info(f"No more posts found at page {page}")
                break

            # Yield posts
            yield posts

            # Call callback if provided
            if callback:
                callback(page, posts)

            pages_fetched += 1
            page += 1

            # Delay to avoid overwhelming server
            if self.delay > 0:
                time.sleep(self.delay)

    def fetch_all_posts_list(
        self,
        start_page: int = 1,
        max_pages: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch all posts and return as a single list.

        Args:
            start_page: Starting page number (1-indexed)
            max_pages: Maximum number of pages to fetch (None = all)

        Returns:
            List of all post dictionaries

        Raises:
            WordPressAPIError: If a request fails
        """
        all_posts = []

        for posts in self.fetch_all(start_page=start_page, max_pages=max_pages):
            all_posts.extend(posts)

        logger.info(f"Fetched total of {len(all_posts)} posts")
        return all_posts

    def get_total_posts_count(self) -> Optional[int]:
        """
        Get the total number of posts available.

        Returns:
            Total number of posts, or None if unable to determine
        """
        try:
            response = self.session.get(self.base_url, params={'per_page': 1}, timeout=10)
            response.raise_for_status()
            total = response.headers.get('X-WP-Total')
            return int(total) if total else None
        except Exception as e:
            logger.warning(f"Could not get total posts count: {e}")
            return None

    def fetch_modified_since(self, modified_after: str, search: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Fetch all posts modified after a specific date.

        Args:
            modified_after: ISO 8601 date string (e.g., '2023-01-01T00:00:00')
            search: Optional search keyword/phrase to filter posts

        Returns:
            List of all post dictionaries modified after the given date

        Raises:
            WordPressAPIError: If a request fails
        """
        logger.info(f"Fetching posts modified after: {modified_after}")
        if search:
            logger.info(f"With search filter: '{search}'")

        # WordPress API parameter for filtering by modification date
        additional_params = {'modified_after': modified_after}
        if search:
            additional_params['search'] = search

        all_posts = []
        for posts in self.fetch_all(start_page=1, max_pages=None, additional_params=additional_params):
            all_posts.extend(posts)

        logger.info(f"Fetched {len(all_posts)} posts modified since {modified_after}")
        return all_posts

    def close(self):
        """Close the session."""
        self.session.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
