"""Configuration management for WordPress scraper."""

import os
import json
import yaml
from dataclasses import dataclass, field, asdict
from typing import Optional, List
from pathlib import Path


@dataclass
class ScraperConfig:
    """Configuration for WordPress scraper."""

    # Required
    wordpress_url: str

    # Output settings
    output_dir: str = "./data"
    output_name: str = "wordpress_posts"
    export_formats: List[str] = field(default_factory=list)  # Optional exports: json, xlsx

    # Scraping settings
    per_page: int = 100
    max_pages: Optional[int] = None  # None means all pages
    start_page: int = 1
    delay: float = 1.0  # Delay between requests in seconds
    strip_html: bool = True
    search: Optional[str] = None  # Search keyword/phrase to filter posts

    # Update/Resume settings
    update: bool = False  # Fetch only new/modified posts
    resume: bool = False  # Resume from last page scraped

    # Database settings
    table_name: str = "posts"

    def __post_init__(self):
        """Validate and normalize configuration."""
        # Ensure URL ends with proper format
        if not self.wordpress_url.endswith('/'):
            self.wordpress_url += '/'

        # Ensure output directory exists
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)

        # Validate export formats
        valid_formats = {"json", "xlsx"}
        for fmt in self.export_formats:
            if fmt not in valid_formats:
                raise ValueError(f"Invalid export format: {fmt}. Valid: {valid_formats}")

    @classmethod
    def from_dict(cls, config_dict: dict) -> 'ScraperConfig':
        """Create config from dictionary."""
        return cls(**config_dict)

    @classmethod
    def from_yaml(cls, yaml_path: str) -> 'ScraperConfig':
        """Load configuration from YAML file."""
        with open(yaml_path, 'r') as f:
            config_dict = yaml.safe_load(f)
        return cls.from_dict(config_dict)

    @classmethod
    def from_json(cls, json_path: str) -> 'ScraperConfig':
        """Load configuration from JSON file."""
        with open(json_path, 'r') as f:
            config_dict = json.load(f)
        return cls.from_dict(config_dict)

    def to_dict(self) -> dict:
        """Convert config to dictionary."""
        return asdict(self)

    def to_yaml(self, output_path: str):
        """Save configuration to YAML file."""
        with open(output_path, 'w') as f:
            yaml.dump(self.to_dict(), f, default_flow_style=False)

    def to_json(self, output_path: str):
        """Save configuration to JSON file."""
        with open(output_path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)

    def get_db_path(self) -> str:
        """Get full path for database file."""
        return os.path.join(self.output_dir, f"{self.output_name}.db")

    def get_json_path(self) -> str:
        """Get full path for JSON file."""
        return os.path.join(self.output_dir, f"{self.output_name}.json")

    def get_excel_path(self) -> str:
        """Get full path for Excel file."""
        return os.path.join(self.output_dir, f"{self.output_name}.xlsx")

    def get_metadata_path(self) -> str:
        """Get full path for metadata database file."""
        return os.path.join(self.output_dir, f"{self.output_name}.metadata.db")

    def get_api_url(self) -> str:
        """Get full WordPress API URL for posts endpoint."""
        base = self.wordpress_url.rstrip('/')
        return f"{base}/wp-json/wp/v2/posts/"
