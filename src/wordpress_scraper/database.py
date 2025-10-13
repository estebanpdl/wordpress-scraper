"""Database operations for WordPress scraper."""

import sqlite3
import logging
from typing import Dict, Any, List, Optional
from contextlib import contextmanager


logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manager for SQLite database operations."""

    # SQL schema for posts table
    CREATE_TABLE_SQL = '''
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY,
            date TEXT,
            date_gmt TEXT,
            guid TEXT,
            modified TEXT,
            modified_gmt TEXT,
            slug TEXT,
            status TEXT,
            type TEXT,
            link TEXT,
            title TEXT,
            content TEXT,
            excerpt TEXT,
            author INTEGER,
            featured_media INTEGER,
            comment_status TEXT,
            ping_status TEXT,
            sticky INTEGER,
            template TEXT,
            format TEXT,
            meta TEXT,
            categories TEXT,
            tags TEXT,
            area TEXT,
            alerts TEXT,
            countries TEXT,
            class_list TEXT
        )
    '''

    INSERT_POST_SQL = '''
        INSERT OR REPLACE INTO posts (
            id, date, date_gmt, guid, modified, modified_gmt, slug, status, type, link,
            title, content, excerpt, author, featured_media, comment_status, ping_status,
            sticky, template, format, meta, categories, tags, area, alerts, countries, class_list
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    '''

    def __init__(self, db_path: str, table_name: str = "posts"):
        """
        Initialize database manager.

        Args:
            db_path: Path to SQLite database file
            table_name: Name of the table to use
        """
        self.db_path = db_path
        self.table_name = table_name
        self.connection: Optional[sqlite3.Connection] = None

    def connect(self):
        """Establish database connection."""
        if self.connection is None:
            self.connection = sqlite3.connect(self.db_path)
            logger.debug(f"Connected to database: {self.db_path}")

    def close(self):
        """Close database connection."""
        if self.connection:
            self.connection.close()
            self.connection = None
            logger.debug("Database connection closed")

    @contextmanager
    def get_cursor(self):
        """
        Context manager for getting a database cursor.

        Yields:
            Database cursor
        """
        if self.connection is None:
            self.connect()

        cursor = self.connection.cursor()
        try:
            yield cursor
            self.connection.commit()
        except Exception as e:
            self.connection.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            cursor.close()

    def create_table(self):
        """Create the posts table if it doesn't exist."""
        with self.get_cursor() as cursor:
            cursor.execute(self.CREATE_TABLE_SQL)
        logger.info("Database table created or verified")

    def insert_post(self, post_data: Dict[str, Any]):
        """
        Insert or replace a single post in the database.

        Args:
            post_data: Dictionary containing post data
        """
        with self.get_cursor() as cursor:
            cursor.execute(self.INSERT_POST_SQL, (
                post_data.get('id'),
                post_data.get('date'),
                post_data.get('date_gmt'),
                post_data.get('guid'),
                post_data.get('modified'),
                post_data.get('modified_gmt'),
                post_data.get('slug'),
                post_data.get('status'),
                post_data.get('type'),
                post_data.get('link'),
                post_data.get('title'),
                post_data.get('content'),
                post_data.get('excerpt'),
                post_data.get('author'),
                post_data.get('featured_media'),
                post_data.get('comment_status'),
                post_data.get('ping_status'),
                post_data.get('sticky'),
                post_data.get('template'),
                post_data.get('format'),
                post_data.get('meta'),
                post_data.get('categories'),
                post_data.get('tags'),
                post_data.get('area'),
                post_data.get('alerts'),
                post_data.get('countries'),
                post_data.get('class_list')
            ))

    def insert_posts_batch(self, posts_data: List[Dict[str, Any]]):
        """
        Insert or replace multiple posts in a single transaction.

        Args:
            posts_data: List of dictionaries containing post data
        """
        with self.get_cursor() as cursor:
            data_tuples = [
                (
                    post.get('id'),
                    post.get('date'),
                    post.get('date_gmt'),
                    post.get('guid'),
                    post.get('modified'),
                    post.get('modified_gmt'),
                    post.get('slug'),
                    post.get('status'),
                    post.get('type'),
                    post.get('link'),
                    post.get('title'),
                    post.get('content'),
                    post.get('excerpt'),
                    post.get('author'),
                    post.get('featured_media'),
                    post.get('comment_status'),
                    post.get('ping_status'),
                    post.get('sticky'),
                    post.get('template'),
                    post.get('format'),
                    post.get('meta'),
                    post.get('categories'),
                    post.get('tags'),
                    post.get('area'),
                    post.get('alerts'),
                    post.get('countries'),
                    post.get('class_list')
                )
                for post in posts_data
            ]
            cursor.executemany(self.INSERT_POST_SQL, data_tuples)

        logger.debug(f"Inserted {len(posts_data)} posts in batch")

    def post_exists(self, post_id: int) -> bool:
        """
        Check if a post exists in the database.

        Args:
            post_id: Post ID to check

        Returns:
            True if post exists, False otherwise
        """
        with self.get_cursor() as cursor:
            cursor.execute("SELECT 1 FROM posts WHERE id = ? LIMIT 1", (post_id,))
            return cursor.fetchone() is not None

    def get_post_count(self) -> int:
        """
        Get the total number of posts in the database.

        Returns:
            Number of posts
        """
        with self.get_cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM posts")
            result = cursor.fetchone()
            return result[0] if result else 0

    def get_all_post_ids(self) -> List[int]:
        """
        Get all post IDs from the database.

        Returns:
            List of post IDs
        """
        with self.get_cursor() as cursor:
            cursor.execute("SELECT id FROM posts ORDER BY id")
            return [row[0] for row in cursor.fetchall()]

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
