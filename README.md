# WordPress Scraper

A command-line tool for scraping WordPress sites via the WordPress REST API. Always creates a SQLite database for tracking and storage, with optional exports to JSON and Excel formats.

## Installation

### From Source

```bash
# Clone or navigate to the repository
cd wordpress-scraper

# Install in editable mode (recommended for development)
pip install -e .

# Or install normally
pip install .
```

### Requirements

- Python 3.7+
- Dependencies (automatically installed):
  - requests
  - pandas
  - openpyxl
  - PyYAML
  - urllib3

## Usage

### Basic Usage

Scrape a WordPress site (creates database in `./data`):

```bash
wordpress-scraper --url https://example.com
```

This creates:
- `./data/wordpress_posts.db` - SQLite database with all posts
- `./data/wordpress_posts.metadata.db` - Scrape state tracking

### Common Examples

#### With exports to JSON and Excel

```bash
wordpress-scraper --url https://example.com --export json xlsx
```

This creates database + JSON + Excel files.

#### Specify output directory and name

```bash
wordpress-scraper --url https://example.com \
  --output-dir ./my_data \
  --output-name example_posts
```

#### Limit number of pages

```bash
# Fetch only first 10 pages
wordpress-scraper --url https://example.com --max-pages 10
```

#### Start from a specific page

```bash
# Start from page 5
wordpress-scraper --url https://example.com --start-page 5
```

#### Adjust request delay

```bash
# Wait 2 seconds between requests
wordpress-scraper --url https://example.com --delay 2.0
```

#### Keep HTML in content

```bash
# Don't strip HTML tags from content and excerpts
wordpress-scraper --url https://example.com --no-strip-html
```

#### Dry run (validate endpoint)

```bash
# Check if endpoint is accessible without scraping
wordpress-scraper --url https://example.com --dry-run
```

#### Enable verbose logging

```bash
wordpress-scraper --url https://example.com --verbose
```

#### Search for specific keywords

```bash
# Search for posts containing "Ukraine"
wordpress-scraper --url https://example.com --search "Ukraine" --output-name ukraine_posts

# Search with phrase
wordpress-scraper --url https://example.com --search "climate change" --output-name climate_posts
```

**Important - Search Limitations:**

The `--search` parameter uses WordPress's built-in REST API search, which has limitations:
- **Multiple fields**: Searches across title, content, excerpt, and URLs within content
- **No exact phrase control**: Cannot force exact phrase matching from the API; Matches partial words; It is case-insensitive.

If you need more precise filtering, consider post-processing the exported JSON/Excel results to filter false positives manually.

### Updating Existing Scrapes

The tool provides two modes for working with existing scrapes: `--update` and `--resume`.

#### Update Mode: Fetch New/Modified Posts

Use `--update` to fetch only new or modified posts since your last scrape:

```bash
# Initial full scrape
wordpress-scraper --url https://example.com --export json

# Later, fetch only new/modified posts
wordpress-scraper --url https://example.com --export json --update
```

**How it works:**
- Checks metadata database for latest `modified_gmt` timestamp
- Uses WordPress API's `modified_after` filter
- Fetches only posts newer than that timestamp
- Updates database with new/modified posts
- If no previous scrape exists, runs full scrape automatically

**Example workflow:**
```bash
# Monday: Full scrape (1000 posts)
wordpress-scraper --url https://news.com --output-dir ./news_data --output-name news_posts

# Wednesday: Update (fetches ~20 new posts)
wordpress-scraper --url https://news.com --output-dir ./news_data --output-name news_posts --update

# Friday: Update again (fetches ~15 new posts)
wordpress-scraper --url https://news.com --output-dir ./news_data --output-name news_posts --update
```

**Note:** When using `--update` or `--resume`, you must use the same `--output-dir` and `--output-name` as the original scrape so the tool can locate the metadata database.

#### Resume Mode: Continue Incomplete Scrapes

Use `--resume` to continue a scrape that was interrupted or intentionally limited:

```bash
# Initial scrape interrupted at page 23
wordpress-scraper --url https://example.com

# Resume from page 24
wordpress-scraper --url https://example.com --resume
```

**How it works:**
- Checks metadata database for `last_page_scraped`
- Continues pagination from the next page
- Useful for network interruptions, intentional partial scrapes, or when site grows
- If no previous scrape exists, starts from page 1

**Use cases:**
```bash
# Use case 1: Network interruption (stopped at page 23)
wordpress-scraper --url https://example.com --output-dir ./data --output-name my_posts --resume

# Use case 2: Initially scraped only 10 pages, now want more
wordpress-scraper --url https://example.com --output-dir ./data --output-name my_posts --max-pages 10
# Later...
wordpress-scraper --url https://example.com --output-dir ./data --output-name my_posts --resume  # Continues from page 11

# Use case 3: Site grew from 50 to 100 pages
wordpress-scraper --url https://example.com --output-dir ./data --output-name my_posts --resume  # Fetches pages 51-100
```

**Note:** Always use the same `--output-dir` and `--output-name` when resuming to ensure the tool finds the correct metadata.

**Update vs Resume:**
- **--update**: Fetches posts modified AFTER your last scrape (gets newer content)
- **--resume**: Continues from last page scraped (completes incomplete scrapes)

#### Search Consistency with Update/Resume

When using `--search`, you **must provide the same search query** for `--update` and `--resume`:

```bash
# Initial search scrape
wordpress-scraper --url https://news.com --search "Ukraine" --output-name ukraine_posts

# Later: Resume (must include same search)
wordpress-scraper --url https://news.com --search "Ukraine" --output-name ukraine_posts --resume

# Later: Update (must include same search)
wordpress-scraper --url https://news.com --search "Ukraine" --output-name ukraine_posts --update
```

**Important:** The tool enforces search consistency to prevent mixing incompatible datasets:
- If original scrape used search → You **must** provide the same search for update/resume
- If original scrape had no search → You **cannot** add search for update/resume
- Search query must match exactly (case-sensitive)

### Using Configuration Files

Create a config file to avoid typing long commands:

**config.yaml:**
```yaml
wordpress_url: https://www.dfrlab.org
output_dir: ./data
output_name: dfrlab_posts
export_formats:
  - json
  - xlsx
per_page: 100
max_pages: null  # null means all pages
start_page: 1
delay: 1.0
strip_html: true
search: null  # Set to keyword/phrase to filter posts (e.g., "Ukraine")
update: false  # Set to true to fetch only new/modified posts
resume: false  # Set to true to resume from last page
```

**config.json:**
```json
{
  "wordpress_url": "https://www.dfrlab.org",
  "output_dir": "./data",
  "output_name": "dfrlab_posts",
  "export_formats": ["json", "xlsx"],
  "per_page": 100,
  "max_pages": null,
  "start_page": 1,
  "delay": 1.0,
  "strip_html": true,
  "search": null,
  "update": false,
  "resume": false
}
```

**Example workflows with config files:**

```bash
# Initial full scrape
wordpress-scraper --config config.yaml

# Later, update only (edit config.yaml and set update: true)
wordpress-scraper --config config.yaml

# Or override config file with CLI flag
wordpress-scraper --config config.yaml --update
```


## Command-Line Options

```
Required (unless using --config):
  --url URL                WordPress site URL

Configuration:
  --config FILE            Path to config file (YAML or JSON)

Output Options:
  --output-dir DIR         Output directory (default: ./data)
  --output-name NAME       Base name for output files (default: wordpress_posts)
  --export {json,xlsx}     Optional export formats (database always created)

Scraping Options:
  --per-page N             Posts per page, max 100 (default: 100)
  --max-pages N            Maximum pages to fetch (default: all)
  --start-page N           Starting page number (default: 1)
  --delay SECONDS          Delay between requests (default: 1.0)
  --no-strip-html          Keep HTML tags in content
  --search KEYWORD         Search keyword/phrase to filter posts

Update Options:
  --update                 Fetch only new/modified posts since last scrape
  --resume                 Resume incomplete scrape from last page

Other:
  --dry-run                Validate endpoint only
  --verbose                Enable debug logging
  --version                Show version
  --help                   Show help message
```

## Output Files

All output files are saved to the specified `--output-dir` with the `--output-name` prefix:

- **Database** (always created): `{output_name}.db` - SQLite database with `posts` table
- **Metadata** (always created): `{output_name}.metadata.db` - Scrape state tracking
- **JSON** (optional): `{output_name}.json` - Raw JSON data from WordPress API
- **Excel** (optional): `{output_name}.xlsx` - Spreadsheet with cleaned data

### Database Schema

The SQLite database contains a `posts` table with the following fields:

- `id` (PRIMARY KEY)
- `date`, `date_gmt`
- `guid`, `modified`, `modified_gmt`
- `slug`, `status`, `type`, `link`
- `title`, `content`, `excerpt`
- `author`, `featured_media`
- `comment_status`, `ping_status`
- `sticky`, `template`, `format`
- `meta`, `categories`, `tags`
- `area`, `alerts`, `countries`, `class_list`

## Project Structure

```
wordpress-scraper/
├── src/
│   └── wordpress_scraper/
│       ├── __init__.py
│       ├── cli.py              # Command-line interface
│       ├── config.py           # Configuration management
│       ├── api_client.py       # WordPress API client
│       ├── database.py         # SQLite operations
│       ├── exporters.py        # Export to JSON/Excel/CSV
│       └── utils.py            # Helper functions
├── setup.py                    # Package setup
├── requirements.txt            # Dependencies
└── README.md                   # This file
```

## Using as a Python Library

You can also import and use the modules in your own Python scripts:

```python
from wordpress_scraper.config import ScraperConfig
from wordpress_scraper.api_client import WordPressClient
from wordpress_scraper.database import DatabaseManager

# Create config
config = ScraperConfig(
    wordpress_url="https://example.com",
    output_dir="./data",
    output_name="my_posts"
)

# Fetch posts
with WordPressClient(config.get_api_url()) as client:
    posts = client.fetch_all_posts_list(max_pages=5)
    print(f"Fetched {len(posts)} posts")

# Save to database
with DatabaseManager(config.get_db_path()) as db:
    db.create_table()
    # ... process and insert posts
```

## Troubleshooting

### "Failed to validate WordPress API endpoint"

- Verify the URL is correct and publicly accessible
- Ensure the WordPress site has the REST API enabled
- Check if the site requires authentication (this tool currently supports public APIs only)

### "HTTP Error 429: Too Many Requests"

- Increase the `--delay` value (e.g., `--delay 2.0`)
- The tool has automatic retries, but you may need to reduce request frequency

## License

MIT License

## Author

estebanpdl / DFRLab
