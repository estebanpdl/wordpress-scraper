"""Export functionality for WordPress scraper."""

import json
import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Any
import pandas as pd


logger = logging.getLogger(__name__)


class BaseExporter(ABC):
    """Abstract base class for exporters."""

    def __init__(self, output_path: str):
        """
        Initialize exporter.

        Args:
            output_path: Path to output file
        """
        self.output_path = output_path

    @abstractmethod
    def export(self, data: List[Dict[str, Any]]):
        """
        Export data to file.

        Args:
            data: List of dictionaries containing data to export
        """
        pass


class JSONExporter(BaseExporter):
    """Exporter for JSON format."""

    def export(self, data: List[Dict[str, Any]], indent: int = 2):
        """
        Export data to JSON file.

        Args:
            data: List of dictionaries containing data to export
            indent: Indentation level for JSON (default: 2)
        """
        try:
            with open(self.output_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=indent, ensure_ascii=False)

            logger.info(f"Exported {len(data)} items to JSON: {self.output_path}")

        except Exception as e:
            logger.error(f"Failed to export to JSON: {e}")
            raise


class ExcelExporter(BaseExporter):
    """Exporter for Excel format."""

    def __init__(self, output_path: str, sheet_name: str = "Posts"):
        """
        Initialize Excel exporter.

        Args:
            output_path: Path to output Excel file
            sheet_name: Name of the Excel sheet (default: "Posts")
        """
        super().__init__(output_path)
        self.sheet_name = sheet_name

    def export(self, data: List[Dict[str, Any]]):
        """
        Export data to Excel file.

        Args:
            data: List of dictionaries containing data to export
        """
        try:
            if not data:
                logger.warning("No data to export to Excel")
                return

            # Create DataFrame from data
            df = pd.DataFrame(data)

            # Export to Excel
            with pd.ExcelWriter(self.output_path, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name=self.sheet_name, index=False)

            logger.info(f"Exported {len(data)} items to Excel: {self.output_path}")

        except Exception as e:
            logger.error(f"Failed to export to Excel: {e}")
            raise


class CSVExporter(BaseExporter):
    """Exporter for CSV format."""

    def export(self, data: List[Dict[str, Any]]):
        """
        Export data to CSV file.

        Args:
            data: List of dictionaries containing data to export
        """
        try:
            if not data:
                logger.warning("No data to export to CSV")
                return

            # Create DataFrame from data
            df = pd.DataFrame(data)

            # Export to CSV
            df.to_csv(self.output_path, index=False, encoding='utf-8')

            logger.info(f"Exported {len(data)} items to CSV: {self.output_path}")

        except Exception as e:
            logger.error(f"Failed to export to CSV: {e}")
            raise


def create_exporter(format_type: str, output_path: str) -> BaseExporter:
    """
    Factory function to create appropriate exporter.

    Args:
        format_type: Type of export format ('json', 'xlsx', 'csv')
        output_path: Path to output file

    Returns:
        Appropriate exporter instance

    Raises:
        ValueError: If format_type is not supported
    """
    exporters = {
        'json': JSONExporter,
        'xlsx': ExcelExporter,
        'csv': CSVExporter
    }

    exporter_class = exporters.get(format_type.lower())

    if exporter_class is None:
        raise ValueError(f"Unsupported format: {format_type}. Supported: {list(exporters.keys())}")

    return exporter_class(output_path)
