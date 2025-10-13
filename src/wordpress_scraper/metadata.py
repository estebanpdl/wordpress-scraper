"""Metadata tracking for WordPress scraper state."""

import sqlite3
import logging
from pathlib import Path
from typing import Optional
from datetime import datetime


logger = logging.getLogger(__name__)


class MetadataManager:
    """Manager for tracking scrape metadata (separate from post data)."""

    CREATE_TABLE_SQL = '''
        CREATE TABLE IF NOT EXISTS scrape_metadata (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            wordpress_url TEXT NOT NULL,
            last_scrape_date TEXT NOT NULL,
            latest_post_modified TEXT,
            total_posts_scraped INTEGER DEFAULT 0,
            last_page_scraped INTEGER DEFAULT 0,
            next_page_to_fetch INTEGER DEFAULT 1,
            search_query TEXT,
            scrape_status TEXT DEFAULT 'in_progress'
        )
    '''

    def __init__(self, metadata_path: str):
        """
        Initialize metadata manager.

        Args:
            metadata_path: Path to metadata SQLite database
        """
        self.metadata_path = metadata_path
        self.connection: Optional[sqlite3.Connection] = None

    def connect(self):
        """Establish database connection."""
        if self.connection is None:
            self.connection = sqlite3.connect(self.metadata_path)
            self.connection.row_factory = sqlite3.Row  # Allow dict-like access
            logger.debug(f"Connected to metadata database: {self.metadata_path}")

    def close(self):
        """Close database connection."""
        if self.connection:
            self.connection.close()
            self.connection = None
            logger.debug("Metadata database connection closed")

    def create_table(self):
        """Create metadata table if it doesn't exist."""
        self.connect()
        cursor = self.connection.cursor()
        cursor.execute(self.CREATE_TABLE_SQL)

        # Migration: Add missing columns if they don't exist
        cursor.execute("PRAGMA table_info(scrape_metadata)")
        columns = [row[1] for row in cursor.fetchall()]

        if 'next_page_to_fetch' not in columns:
            logger.info("Migrating metadata table: adding next_page_to_fetch column")
            cursor.execute("ALTER TABLE scrape_metadata ADD COLUMN next_page_to_fetch INTEGER DEFAULT 1")

        if 'search_query' not in columns:
            logger.info("Migrating metadata table: adding search_query column")
            cursor.execute("ALTER TABLE scrape_metadata ADD COLUMN search_query TEXT")

        self.connection.commit()
        cursor.close()
        logger.debug("Metadata table created or verified")

    def exists(self) -> bool:
        """Check if metadata database file exists."""
        return Path(self.metadata_path).exists()

    def save_scrape_metadata(
        self,
        wordpress_url: str,
        latest_post_modified: Optional[str] = None,
        total_posts: int = 0,
        last_page: int = 0,
        next_page: Optional[int] = None,
        search_query: Optional[str] = None,
        status: str = 'complete'
    ):
        """
        Save or update scrape metadata.

        Args:
            wordpress_url: WordPress site URL
            latest_post_modified: Latest modified_gmt timestamp from scraped posts
            total_posts: Total number of posts scraped
            last_page: Last page number scraped
            next_page: Next page to fetch (for resume)
            search_query: Search keyword/phrase used (None if no search)
            status: Scrape status ('complete', 'interrupted', 'updating')
        """
        self.connect()
        cursor = self.connection.cursor()

        now = datetime.utcnow().isoformat()

        # Check if entry exists for this URL
        cursor.execute(
            "SELECT id FROM scrape_metadata WHERE wordpress_url = ? ORDER BY id DESC LIMIT 1",
            (wordpress_url,)
        )
        result = cursor.fetchone()

        # Calculate next_page if not provided
        if next_page is None:
            next_page = last_page + 1 if last_page > 0 else 1

        if result:
            # Update existing
            cursor.execute('''
                UPDATE scrape_metadata
                SET last_scrape_date = ?,
                    latest_post_modified = ?,
                    total_posts_scraped = ?,
                    last_page_scraped = ?,
                    next_page_to_fetch = ?,
                    search_query = ?,
                    scrape_status = ?
                WHERE id = ?
            ''', (now, latest_post_modified, total_posts, last_page, next_page, search_query, status, result[0]))
        else:
            # Insert new
            cursor.execute('''
                INSERT INTO scrape_metadata (
                    wordpress_url,
                    last_scrape_date,
                    latest_post_modified,
                    total_posts_scraped,
                    last_page_scraped,
                    next_page_to_fetch,
                    search_query,
                    scrape_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (wordpress_url, now, latest_post_modified, total_posts, last_page, next_page, search_query, status))

        self.connection.commit()
        cursor.close()
        logger.info(f"Saved scrape metadata: {total_posts} posts, status: {status}")

    def get_latest_metadata(self, wordpress_url: str) -> Optional[dict]:
        """
        Get the most recent scrape metadata for a URL.

        Args:
            wordpress_url: WordPress site URL

        Returns:
            Dictionary with metadata fields, or None if no metadata exists
        """
        if not self.exists():
            return None

        self.connect()
        cursor = self.connection.cursor()

        cursor.execute('''
            SELECT *
            FROM scrape_metadata
            WHERE wordpress_url = ?
            ORDER BY id DESC
            LIMIT 1
        ''', (wordpress_url,))

        result = cursor.fetchone()
        cursor.close()

        if result:
            return dict(result)
        return None

    def get_latest_modified_date(self, wordpress_url: str) -> Optional[str]:
        """
        Get the latest post modification date from metadata.

        Args:
            wordpress_url: WordPress site URL

        Returns:
            Latest modified_gmt timestamp, or None
        """
        metadata = self.get_latest_metadata(wordpress_url)
        if metadata:
            return metadata.get('latest_post_modified')
        return None

    def get_last_page_scraped(self, wordpress_url: str) -> Optional[int]:
        """
        Get the last page number scraped from metadata.

        Args:
            wordpress_url: WordPress site URL

        Returns:
            Last page scraped, or None if no metadata exists
        """
        metadata = self.get_latest_metadata(wordpress_url)
        if metadata:
            return metadata.get('last_page_scraped')
        return None

    def get_next_page_to_fetch(self, wordpress_url: str) -> Optional[int]:
        """
        Get the next page number to fetch from metadata.

        Args:
            wordpress_url: WordPress site URL

        Returns:
            Next page to fetch, or None if no metadata exists
        """
        metadata = self.get_latest_metadata(wordpress_url)
        if metadata:
            next_page = metadata.get('next_page_to_fetch')
            logger.debug(f"Found metadata for {wordpress_url}: next_page_to_fetch={next_page}, last_page_scraped={metadata.get('last_page_scraped')}")
            return next_page
        logger.debug(f"No metadata found for {wordpress_url}")
        return None

    def get_search_query(self, wordpress_url: str) -> Optional[str]:
        """
        Get the search query from metadata.

        Args:
            wordpress_url: WordPress site URL

        Returns:
            Search query string, or None if no metadata exists or no search was used
        """
        metadata = self.get_latest_metadata(wordpress_url)
        if metadata:
            return metadata.get('search_query')
        return None

    def update_progress(self, wordpress_url: str, page: int, posts_count: int):
        """
        Update scrape progress (called after each page).

        Args:
            wordpress_url: WordPress site URL
            page: Page number just completed
            posts_count: Total posts scraped so far
        """
        self.connect()
        cursor = self.connection.cursor()

        now = datetime.utcnow().isoformat()
        next_page = page + 1  # Calculate next page to fetch

        # Check if entry exists
        cursor.execute(
            "SELECT id FROM scrape_metadata WHERE wordpress_url = ? ORDER BY id DESC LIMIT 1",
            (wordpress_url,)
        )
        result = cursor.fetchone()

        if result:
            # Update existing
            cursor.execute('''
                UPDATE scrape_metadata
                SET last_scrape_date = ?,
                    total_posts_scraped = ?,
                    last_page_scraped = ?,
                    next_page_to_fetch = ?,
                    scrape_status = 'in_progress'
                WHERE id = ?
            ''', (now, posts_count, page, next_page, result[0]))
        else:
            # Insert new
            cursor.execute('''
                INSERT INTO scrape_metadata (
                    wordpress_url,
                    last_scrape_date,
                    total_posts_scraped,
                    last_page_scraped,
                    next_page_to_fetch,
                    scrape_status
                ) VALUES (?, ?, ?, ?, ?, 'in_progress')
            ''', (wordpress_url, now, posts_count, page, next_page))

        self.connection.commit()
        cursor.close()

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
