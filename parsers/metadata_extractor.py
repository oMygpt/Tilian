"""
Metadata extraction from parsed PDF results
"""

import json
import re
from pathlib import Path
from typing import Dict, Optional


def extract_metadata_from_json(json_path: Path) -> Dict[str, Optional[str]]:
    """
    Extract book metadata from MinerU JSON output
    
    Args:
        json_path: Path to parsed JSON file
    
    Returns:
        Dict with keys: title, author, isbn, publisher, publish_year
    """
    metadata = {
        'title': None,
        'author': None,
        'isbn': None,
        'publisher': None,
        'publish_year': None
    }
    
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Try to extract from document metadata if available
        if isinstance(data, dict):
            # Check for metadata field
            if 'metadata' in data:
                meta = data['metadata']
                metadata['title'] = meta.get('title')
                metadata['author'] = meta.get('author')
            
            # Try to extract from first few pages
            if 'pages' in data and isinstance(data['pages'], list):
                first_page_text = ''
                for page in data['pages'][:3]:  # Check first 3 pages
                    if 'text' in page:
                        first_page_text += page['text'] + '\n'
                
                # Extract patterns
                metadata.update(_extract_patterns_from_text(first_page_text))
        
    except Exception as e:
        print(f"Error extracting metadata from JSON: {e}")
    
    return metadata


def extract_metadata_from_md(md_path: Path) -> Dict[str, Optional[str]]:
    """
    Extract book metadata from MinerU Markdown output
    
    Args:
        md_path: Path to parsed MD file
    
    Returns:
        Dict with keys: title, author, isbn, publisher, publish_year
    """
    metadata = {
        'title': None,
        'author': None,
        'isbn': None,
        'publisher': None,
        'publish_year': None
    }
    
    try:
        with open(md_path, 'r', encoding='utf-8') as f:
            # Read first few lines (usually metadata is at the beginning)
            text = '\n'.join([f.readline() for _ in range(50)])
        
        metadata.update(_extract_patterns_from_text(text))
    
    except Exception as e:
        print(f"Error extracting metadata from MD: {e}")
    
    return metadata


def _extract_patterns_from_text(text: str) -> Dict[str, Optional[str]]:
    """Extract metadata patterns from text"""
    metadata = {}
    
    # Extract ISBN (ISBN-10 or ISBN-13)
    isbn_pattern = r'ISBN[:\s-]*(\d{1,5}[-\s]?\d{1,7}[-\s]?\d{1,7}[-\s]?[\dX]|\d{13})'
    isbn_match = re.search(isbn_pattern, text, re.IGNORECASE)
    if isbn_match:
        metadata['isbn'] = isbn_match.group(1).replace(' ', '').replace('-', '')
    
    # Extract year (4-digit number, likely in range 1900-2099)
    year_pattern = r'\b(19\d{2}|20\d{2})\b'
    year_matches = re.findall(year_pattern, text)
    if year_matches:
        # Take the most common year or the first one
        metadata['publish_year'] = int(year_matches[0])
    
    # Try to extract title (usually first heading)
    title_pattern = r'^#\s+(.+)$'
    title_match = re.search(title_pattern, text, re.MULTILINE)
    if title_match:
        metadata['title'] = title_match.group(1).strip()
    else:
        # Try first line if it looks like a title (not too long)
        first_line = text.split('\n')[0].strip()
        if first_line and len(first_line) < 100 and not first_line.startswith('Page'):
            metadata['title'] = first_line
    
    # Publisher patterns (common Chinese publishers)
    publisher_patterns = [
        r'([\u4e00-\u9fa5]+出版社)',
        r'出版[：:]\s*([\u4e00-\u9fa5]+)',
    ]
    for pattern in publisher_patterns:
        publisher_match = re.search(pattern, text)
        if publisher_match:
            metadata['publisher'] = publisher_match.group(1)
            break
    
    # Author patterns
    author_patterns = [
        r'作者[：:]\s*([\u4e00-\u9fa5·]+)',
        r'著[：:]\s*([\u4e00-\u9fa5·]+)',
        r'编著[：:]\s*([\u4e00-\u9fa5·]+)',
    ]
    for pattern in author_patterns:
        author_match = re.search(pattern, text)
        if author_match:
            metadata['author'] = author_match.group(1).strip()
            break
    
    return metadata


def merge_metadata(json_metadata: Dict, md_metadata: Dict, filename: str = None) -> Dict:
    """
    Merge metadata from multiple sources, prioritizing non-None values
    
    Args:
        json_metadata: Metadata from JSON
        md_metadata: Metadata from MD
        filename: Original filename for fallback title
    
    Returns:
        Merged metadata dict
    """
    merged = {}
    
    for key in ['title', 'author', 'isbn', 'publisher', 'publish_year']:
        # Prefer JSON metadata, fall back to MD metadata
        merged[key] = json_metadata.get(key) or md_metadata.get(key)
    
    # If still no title, use filename
    if not merged['title'] and filename:
        merged['title'] = Path(filename).stem
    
    return merged
