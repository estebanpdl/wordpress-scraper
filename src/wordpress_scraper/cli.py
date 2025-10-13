#!/usr/bin/env python3
"""Command-line interface for WordPress scraper."""

import argparse
import logging
import sys
from pathlib import Path
from typing import Optional

from wordpress_scraper.config import ScraperConfig
from wordpress_scraper.api_client import WordPressClient, WordPressAPIError
from wordpress_scraper.database import DatabaseManager
from wordpress_scraper.metadata import MetadataManager
from wordpress_scraper.exporters import create_exporter
from wordpress_scraper.utils import extract_post_fields


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def setup_argparse() -> argparse.ArgumentParser:
    """Setup command-line argument parser."""
    parser = argparse.ArgumentParser(
        description='WordPress Scraper - Fetch and export WordPress posts',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Basic usage (creates database only)
  wordpress-scraper --url https://example.com

  # With JSON and Excel exports
  wordpress-scraper --url https://example.com --export json xlsx

  # Update existing scrape
  wordpress-scraper --url https://example.com --update

  # Resume incomplete scrape
  wordpress-scraper --url https://example.com --resume

  # Use config file
  wordpress-scraper --config config.yaml
        '''
    )

    # Required arguments
    required = parser.add_argument_group('Required (unless using --config)')
    required.add_argument('--url', type=str, help='WordPress site URL')

    # Configuration
    config_group = parser.add_argument_group('Configuration')
    config_group.add_argument('--config', type=str, help='Path to config file (YAML or JSON)')

    # Output options
    output = parser.add_argument_group('Output Options')
    output.add_argument('--output-dir', type=str, default='./data', help='Output directory (default: ./data)')
    output.add_argument('--output-name', type=str, default='wordpress_posts', help='Base name for output files')
    output.add_argument('--export', nargs='+', choices=['json', 'xlsx'], help='Optional export formats (database always created)')

    # Scraping options
    scraping = parser.add_argument_group('Scraping Options')
    scraping.add_argument('--per-page', type=int, default=100, help='Posts per page, max 100 (default: 100)')
    scraping.add_argument('--max-pages', type=int, help='Maximum pages to fetch (default: all)')
    scraping.add_argument('--start-page', type=int, default=1, help='Starting page number (default: 1)')
    scraping.add_argument('--delay', type=float, default=1.0, help='Delay between requests in seconds (default: 1.0)')
    scraping.add_argument('--no-strip-html', action='store_true', help='Keep HTML tags in content')
    scraping.add_argument('--search', type=str, help='Search keyword/phrase to filter posts')

    # Update options
    update_group = parser.add_argument_group('Update Options')
    update_group.add_argument('--update', action='store_true', help='Fetch only new/modified posts since last scrape')
    update_group.add_argument('--resume', action='store_true', help='Resume incomplete scrape from last page')

    # Other options
    other = parser.add_argument_group('Other')
    other.add_argument('--dry-run', action='store_true', help='Validate endpoint only')
    other.add_argument('--verbose', action='store_true', help='Enable debug logging')
    other.add_argument('--version', action='version', version='%(prog)s 1.0.0')

    return parser


def load_config_from_args(args: argparse.Namespace) -> ScraperConfig:
    """Load configuration from command-line arguments."""
    if args.config:
        config_path = Path(args.config)
        if not config_path.exists():
            raise ValueError(f"Config file not found: {args.config}")

        if config_path.suffix in ['.yaml', '.yml']:
            return ScraperConfig.from_yaml(args.config)
        elif config_path.suffix == '.json':
            return ScraperConfig.from_json(args.config)
        else:
            raise ValueError(f"Unsupported config format: {config_path.suffix}")

    if not args.url:
        raise ValueError("--url is required (or use --config)")

    return ScraperConfig(
        wordpress_url=args.url,
        output_dir=args.output_dir,
        output_name=args.output_name,
        export_formats=args.export if args.export else [],
        per_page=args.per_page,
        max_pages=args.max_pages,
        start_page=args.start_page,
        delay=args.delay,
        strip_html=not args.no_strip_html,
        search=args.search if hasattr(args, 'search') else None,
        update=args.update,
        resume=args.resume
    )


def run_scraper(config: ScraperConfig, update: bool = False, resume: bool = False, start_page_arg: Optional[int] = None) -> bool:
    """Run the WordPress scraper."""
    try:
        api_url = config.get_api_url()
        logger.info(f"Initializing WordPress API client for: {api_url}")

        with WordPressClient(base_url=api_url, per_page=config.per_page, delay=config.delay) as client:
            # Validate endpoint
            logger.info("Validating WordPress API endpoint...")
            if not client.validate_endpoint():
                logger.error("Failed to validate WordPress API endpoint")
                return False
            logger.info("Endpoint validated successfully")

            # Initialize metadata manager
            metadata_path = config.get_metadata_path()
            metadata_mgr = MetadataManager(metadata_path)
            metadata_mgr.create_table()

            # Initialize database
            db_path = config.get_db_path()
            logger.info(f"Initializing database: {db_path}")
            db_manager = DatabaseManager(db_path, config.table_name)
            db_manager.connect()
            db_manager.create_table()

            # Storage for posts
            all_posts_raw = []
            all_posts_processed = []

            # Handle resume mode
            if resume:
                # Check for conflicting options
                if start_page_arg and start_page_arg != 1:
                    logger.warning("Both --resume and --start-page provided. --resume takes precedence.")

                logger.debug(f"Looking for metadata with URL: {config.wordpress_url}")
                next_page = metadata_mgr.get_next_page_to_fetch(config.wordpress_url)
                last_page = metadata_mgr.get_last_page_scraped(config.wordpress_url)
                stored_search = metadata_mgr.get_search_query(config.wordpress_url)

                logger.debug(f"Retrieved: next_page={next_page}, last_page={last_page}, search_query={stored_search}")

                # Validate search consistency
                if stored_search != config.search:
                    if stored_search and not config.search:
                        logger.error(f"Original scrape used search='{stored_search}', but no search provided.")
                        logger.error(f"Please add: --search \"{stored_search}\"")
                        return False
                    elif not stored_search and config.search:
                        logger.error(f"Original scrape had no search filter, but --search '{config.search}' provided.")
                        logger.error("Cannot mix filtered and unfiltered data.")
                        return False
                    elif stored_search and config.search:
                        logger.error(f"Search query mismatch. Original: '{stored_search}', Current: '{config.search}'")
                        logger.error("Cannot resume with different search query.")
                        return False

                if next_page and last_page:
                    config.start_page = next_page
                    logger.info(f"Resuming from page {next_page} (last completed: {last_page})")
                else:
                    logger.warning(f"No previous scrape found for URL: {config.wordpress_url}. Starting from page 1.")
                    logger.info(f"Metadata path: {metadata_path}")
                    resume = False

            # Handle update mode
            if update:
                latest_modified = metadata_mgr.get_latest_modified_date(config.wordpress_url)
                stored_search = metadata_mgr.get_search_query(config.wordpress_url)

                # Validate search consistency
                if stored_search != config.search:
                    if stored_search and not config.search:
                        logger.error(f"Original scrape used search='{stored_search}', but no search provided.")
                        logger.error(f"Please add: --search \"{stored_search}\"")
                        return False
                    elif not stored_search and config.search:
                        logger.error(f"Original scrape had no search filter, but --search '{config.search}' provided.")
                        logger.error("Cannot mix filtered and unfiltered data.")
                        return False
                    elif stored_search and config.search:
                        logger.error(f"Search query mismatch. Original: '{stored_search}', Current: '{config.search}'")
                        logger.error("Cannot update with different search query.")
                        return False

                if not latest_modified:
                    logger.warning("No previous scrape found. Running full scrape.")
                    update = False
                else:
                    logger.info(f"Fetching posts modified after: {latest_modified}")
                    if config.search:
                        logger.info(f"With search filter: '{config.search}'")
                    all_posts_raw = client.fetch_modified_since(latest_modified, search=config.search)

                    if not all_posts_raw:
                        logger.info("No new or modified posts found.")
                        return True

            # Standard scraping (or fallback from update)
            last_page_completed = 0
            if not update:
                if config.search:
                    logger.info(f"Starting search scrape with query: '{config.search}'")
                else:
                    logger.info("Starting full scrape...")

                total_posts = client.get_total_posts_count()
                if total_posts:
                    logger.info(f"Total posts available: {total_posts}")

                # Prepare additional parameters for search
                additional_params = {}
                if config.search:
                    additional_params['search'] = config.search

                current_page = config.start_page
                for page_posts in client.fetch_all(
                    start_page=config.start_page,
                    max_pages=config.max_pages,
                    additional_params=additional_params if additional_params else None
                ):
                    all_posts_raw.extend(page_posts)
                    logger.info(f"Fetched page {current_page} with {len(page_posts)} posts (Total: {len(all_posts_raw)})")

                    # Update progress after each page
                    metadata_mgr.update_progress(
                        wordpress_url=config.wordpress_url,
                        page=current_page,
                        posts_count=len(all_posts_raw)
                    )
                    last_page_completed = current_page
                    current_page += 1

            # Process all posts
            logger.info(f"Processing {len(all_posts_raw)} posts...")
            processed_posts = []
            latest_modified_gmt = None

            for post in all_posts_raw:
                processed = extract_post_fields(post, strip_html=config.strip_html)
                processed_posts.append(processed)

                # Track latest modification date
                if processed.get('modified_gmt'):
                    if not latest_modified_gmt or processed['modified_gmt'] > latest_modified_gmt:
                        latest_modified_gmt = processed['modified_gmt']

                # For Excel, keep a cleaner subset
                excel_post = {
                    'id': processed['id'],
                    'date': processed['date'],
                    'modified': processed['modified'],
                    'slug': processed['slug'],
                    'link': processed['link'],
                    'title': processed['title'],
                    'content': processed['content'],
                    'excerpt': processed['excerpt'],
                    'author': processed['author'],
                    'categories': processed['categories'],
                    'tags': processed['tags']
                }
                all_posts_processed.append(excel_post)

            # Insert into database
            if processed_posts:
                db_manager.insert_posts_batch(processed_posts)
                logger.info(f"Saved {len(processed_posts)} posts to database")

            # Save metadata
            metadata_mgr.save_scrape_metadata(
                wordpress_url=config.wordpress_url,
                latest_post_modified=latest_modified_gmt,
                total_posts=len(processed_posts),
                last_page=last_page_completed,
                search_query=config.search,
                status='complete'
            )

            # Close database
            db_manager.close()
            logger.info(f"Database saved: {db_path}")

            # Export to JSON if requested
            if 'json' in config.export_formats:
                json_path = config.get_json_path()
                logger.info(f"Exporting to JSON: {json_path}")
                exporter = create_exporter('json', json_path)
                exporter.export(all_posts_raw)

            # Export to Excel if requested
            if 'xlsx' in config.export_formats:
                excel_path = config.get_excel_path()
                logger.info(f"Exporting to Excel: {excel_path}")
                exporter = create_exporter('xlsx', excel_path)
                exporter.export(all_posts_processed)

            logger.info("Scraping completed successfully!")
            return True

    except WordPressAPIError as e:
        logger.error(f"WordPress API error: {e}")
        return False
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        return False


def main():
    """Main entry point for CLI."""
    parser = setup_argparse()
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        config = load_config_from_args(args)

        logger.info("WordPress Scraper starting...")
        logger.info(f"Configuration: {config.wordpress_url}")
        logger.info(f"Output directory: {config.output_dir}")
        logger.info(f"Output name: {config.output_name}")
        if config.export_formats:
            logger.info(f"Export formats: {', '.join(config.export_formats)}")

        # Dry run mode
        if args.dry_run:
            logger.info("Dry run mode - validating endpoint only")
            api_url = config.get_api_url()
            with WordPressClient(base_url=api_url, per_page=1, delay=0) as client:
                if client.validate_endpoint():
                    total = client.get_total_posts_count()
                    logger.info(f"Endpoint is valid. Total posts: {total}")
                    sys.exit(0)
                else:
                    logger.error("Endpoint validation failed")
                    sys.exit(1)

        # Run scraper (prefer config values, but allow CLI args to override for backward compatibility)
        update = args.update if hasattr(args, 'update') and args.update else config.update
        resume = args.resume if hasattr(args, 'resume') and args.resume else config.resume
        success = run_scraper(config, update=update, resume=resume, start_page_arg=args.start_page)
        sys.exit(0 if success else 1)

    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        parser.print_help()
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("\nScraping interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
