"""
Formatters module.

Contains all HTML formatting and text processing functions for reports.
"""

import re
from typing import Optional


def strip_html_tags(html_text):
    """
    Remove HTML tags from text to get plain text.

    Args:
        html_text: HTML string to clean

    Returns:
        Plain text without HTML tags
    """
    if not html_text:
        return ""

    # Remove HTML tags
    clean = re.sub('<.*?>', '', html_text)
    # Remove extra whitespace
    clean = re.sub(r'\s+', ' ', clean)
    return clean.strip()


def format_currency(amount):
    """
    Format amount as currency - CORRIGÉ pour gérer None
    """
    if amount is None or amount == 0:
        return "0 €"
    try:
        return f"{float(amount):,.0f} €".replace(",", " ")
    except (ValueError, TypeError):
        return "0 €"


def extract_text_from_html(html_content: str, max_length: int = None) -> str:
    """
    Extract readable text from HTML content.
    
    Args:
        html_content: HTML string to extract text from
        max_length: Optional maximum length of returned text
    
    Returns:
        Plain text extracted from HTML
    """
    if not html_content:
        return ""
    
    # Remove HTML tags
    text = strip_html_tags(html_content)
    
    # Truncate if needed
    if max_length and len(text) > max_length:
        text = text[:max_length] + "..."
    
    return text
