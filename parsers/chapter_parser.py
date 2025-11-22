"""
Chapter parsing and segmentation from MinerU output
Enhanced with intelligent chapter detection similar to md_chapter_segment.py
"""

import json
import re
import tiktoken
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import config


class ChapterParser:
    """Parse chapters from MinerU JSON structure with intelligent detection"""
    
    def __init__(self, encoding_name: str = 'cl100k_base'):
        """
        Initialize parser with tiktoken encoding
        
        Args:
            encoding_name: Tiktoken encoding to use for token counting
        """
        self.encoding = tiktoken.get_encoding(encoding_name)
    
    def count_tokens(self, text: str) -> int:
        """Count tokens in text"""
        return len(self.encoding.encode(text))
    
    def chinese_numeral_to_int(self, s: str) -> Optional[int]:
        """Convert Chinese numerals to integers"""
        units = {"零":0,"〇":0,"一":1,"二":2,"三":3,"四":4,"五":5,"六":6,"七":7,"八":8,"九":9}
        ten = "十"
        
        if not any(ch in s for ch in units) and ten not in s:
            return None
        
        if s == ten:
            return 10
        
        total = 0
        if ten in s:
            parts = s.split(ten)
            left = parts[0]
            right = parts[1] if len(parts) > 1 else ""
            l = units.get(left, 1) if left != "" else 1
            r = units.get(right, 0) if right != "" else 0
            total = l * 10 + r
        else:
            total = sum(units.get(ch, 0) for ch in s)
        
        return total if total > 0 else None
    
    def extract_chapter_number(self, title: str) -> Optional[int]:
        """Extract chapter number from title"""
        # Try Arabic numerals first
        m = re.search(r"第(\d+)章", title)
        if m:
            return int(m.group(1))
        
        # Try Chinese numerals
        m2 = re.search(r"第([一二三四五六七八九十零〇]+)章", title)
        if m2:
            return self.chinese_numeral_to_int(m2.group(1))
        
        # Try Chapter X format
        m3 = re.search(r"Chapter\s+(\d+)", title, re.IGNORECASE)
        if m3:
            return int(m3.group(1))
        
        # Try standalone numbers at the beginning
        m4 = re.match(r"^(\d+)\b", title)
        if m4:
            return int(m4.group(1))
        
        return None
    
    def is_chapter_header(self, title: str) -> bool:
        """Check if title looks like a chapter header"""
        # Strong chapter patterns
        patterns = [
            r"^第[一二三四五六七八九十零〇0-9]+章",  # 第X章
            r"^Chapter\s+\d+",  # Chapter X
            r"^CHAPTER\s+\d+",  # CHAPTER X
            r"^附录\s*[A-Za-z0-9一二三四五六七八九十零〇]?",  # 附录
        ]
        
        for pattern in patterns:
            if re.match(pattern, title):
                return True
        
        return False
    
    def parse_chapters_from_json(self, json_path: Path) -> List[Dict]:
        """
        Parse chapter structure from MinerU JSON using intelligent detection
        
        Args:
            json_path: Path to MinerU JSON output
        
        Returns:
            List of chapter dicts with structure:
            {
                'title': str,
                'content': str,
                'level': int,
                'order': int,
                'token_count': int,
                'chapter_num': Optional[int],
                'needs_split': bool
            }
        """
        chapters = []
        
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Try to parse from structured data
            if isinstance(data, dict) and 'chapters' in data:
                # If MinerU provides chapter structure
                chapters = self._parse_structured_chapters(data['chapters'])
            else:
                # Fall back to parsing from markdown
                # MinerU saves full.md in the same directory
                md_path = json_path.parent / 'full.md'
                if not md_path.exists():
                    # Try with .md suffix of json file
                    md_path = json_path.with_suffix('.md')
                
                if md_path.exists():
                    print(f"Parsing chapters from MD: {md_path}")
                    chapters = self.parse_chapters_from_md(md_path)
                else:
                    print(f"Warning: No MD file found. Tried: {md_path}")
        
        except Exception as e:
            print(f"Error parsing chapters from JSON: {e}")
            import traceback
            traceback.print_exc()
        
        # Calculate token counts - splitting decision is now up to the user
        for chapter in chapters:
            chapter['token_count'] = self.count_tokens(chapter.get('content', ''))
            # Don't automatically mark for splitting - user will decide
            chapter['needs_split'] = False
        
        return chapters
    
    def parse_chapters_from_md(self, md_path: Path) -> List[Dict]:
        """
        Parse chapters from Markdown file using intelligent heading detection
        
        Args:
            md_path: Path to Markdown file
        
        Returns:
            List of chapter dicts
        """
        # Use the new regex-based parser for better handling of flattened headers
        return self.parse_chapters_by_regex(md_path)

    def parse_chapters_by_regex(self, md_path: Path) -> List[Dict]:
        """
        Parse chapters using strict regex patterns to identify top-level chapters.
        Merges subsections (e.g., 1.1, 1.1.1) into the parent chapter.
        
        Args:
            md_path: Path to Markdown file
            
        Returns:
            List of chapter dicts
        """
        chapters = []
        
        try:
            with open(md_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            lines = content.split('\n')
            
            # Regex patterns for top-level chapters
            # 1. "第X章" or "第X篇" or "第X部分"
            # 2. "Chapter X"
            # 3. "X. Title" (but NOT "X.Y Title")
            # 4. Specific keywords: 序言, 前言, 目录, 参考文献, 附录, 致谢
            
            chapter_patterns = [
                r"^#+\s*第[一二三四五六七八九十零〇\d]+[章篇部分]",  # 第X章
                r"^#+\s*Chapter\s+\d+",  # Chapter X
                r"^#+\s*\d+\s+[^\.\d]",  # 1 Title (but not 1.1)
                # Common Front Matter & Back Matter keywords
                r"^#+\s*(序言|前言|目录|参考文献|附录|致谢|后记|结语|摘要|索引|术语表|版权|作者|推荐语|Introduction|Preface|Contents|References|Appendix|Acknowledgement|Conclusion|Abstract|Index|Glossary|Copyright|About|Praise)", 
            ]
            
            # Compile regex for performance
            combined_pattern = re.compile('|'.join(chapter_patterns), re.IGNORECASE)
            
            # TOC detection patterns
            toc_header_pattern = re.compile(r'^\s*(目录|Contents|Table of Contents)\s*$', re.IGNORECASE)
            # Matches lines ending with page numbers (digits or roman numerals)
            # e.g. "Chapter 1 ... 10", "Section 1 5", "Preface i"
            toc_entry_pattern = re.compile(r'.*(\s+|…|\.+)(\d+|[IVXivx]+)\s*$', re.IGNORECASE)
            
            current_chapter = None
            current_content = []
            chapter_order = 0
            in_toc = False  # Flag to track if we are inside the Table of Contents
            
            for line in lines:
                line_stripped = line.strip()
                
                # Check if line matches a chapter header
                if combined_pattern.match(line_stripped):
                    title = re.sub(r'^#+\s*', '', line_stripped) # Remove #
                    
                    # Check if this is a TOC header
                    is_toc_header = toc_header_pattern.match(title)
                    
                    # Check if this looks like a TOC entry (ends with number)
                    # Only relevant if we are currently inside a TOC or just hit the TOC header
                    is_toc_entry = False
                    if in_toc and not is_toc_header:
                         if toc_entry_pattern.match(title):
                             is_toc_entry = True
                    
                    if is_toc_entry:
                        # It's a fake chapter header (TOC entry), treat as content of the current chapter (TOC)
                        if current_chapter:
                            current_content.append(line)
                    else:
                        # Real new chapter
                        # Save previous chapter if exists
                        if current_chapter:
                            current_chapter['content'] = '\n'.join(current_content).strip()
                            current_chapter['token_count'] = self.count_tokens(current_chapter['content'])
                            chapters.append(current_chapter)
                        
                        # Start new chapter
                        current_chapter = {
                            'title': title,
                            'content': '', # Will be filled later
                            'level': 1,
                            'order': chapter_order,
                            'chapter_num': self.extract_chapter_number(title),
                            'token_count': 0
                        }
                        current_content = [] # Reset content buffer
                        chapter_order += 1
                        
                        # Update TOC state
                        # If we hit a TOC header, we enter TOC mode
                        # If we hit any other REAL chapter header, we exit TOC mode
                        if is_toc_header:
                            in_toc = True
                        else:
                            in_toc = False
                    
                else:
                    # Not a chapter header, append to current content
                    # This handles subsections (e.g., # 1.1) by treating them as normal text
                    if current_chapter:
                        current_content.append(line)
                    else:
                        # Content before the first chapter (e.g., title, author)
                        if line_stripped:
                            if not chapters and not current_chapter:
                                # Create a default first chapter for front matter
                                current_chapter = {
                                    'title': '前言/说明',
                                    'content': '',
                                    'level': 1,
                                    'order': chapter_order,
                                    'chapter_num': None,
                                    'token_count': 0
                                }
                                chapter_order += 1
                            current_content.append(line)
            
            # Save the last chapter
            if current_chapter:
                current_chapter['content'] = '\n'.join(current_content).strip()
                current_chapter['token_count'] = self.count_tokens(current_chapter['content'])
                chapters.append(current_chapter)
                
            print(f"Parsed {len(chapters)} chapters using regex segmentation")
            
        except Exception as e:
            print(f"Error parsing chapters by regex: {e}")
            import traceback
            traceback.print_exc()
            
        return chapters
    
    def _parse_structured_chapters(self, chapters_data: List) -> List[Dict]:
        """Parse from structured chapter data"""
        chapters = []
        
        for idx, chapter_data in enumerate(chapters_data):
            title = chapter_data.get('title', f'Chapter {idx + 1}')
            chapters.append({
                'title': title,
                'content': chapter_data.get('content', ''),
                'level': chapter_data.get('level', 1),
                'order': idx,
                'chapter_num': self.extract_chapter_number(title),
                'token_count': 0  # Will be calculated later
            })
        
        return chapters
    
    def check_token_limit(self, chapter: Dict, model_id: str = 'chatgpt') -> Tuple[bool, int]:
        """
        Check if chapter exceeds token limit for a model
        
        Args:
            chapter: Chapter dict with token_count
            model_id: Model identifier
        
        Returns:
            Tuple of (exceeds_limit, threshold_tokens)
        """
        max_tokens = config.LLM_MODELS.get(model_id, {}).get('max_tokens', 32768)
        threshold = max_tokens * config.TOKEN_THRESHOLD_PERCENTAGE
        
        exceeds = chapter['token_count'] > threshold
        return exceeds, int(threshold)
    
    def split_large_chapter(self, chapter: Dict, max_tokens: int) -> List[Dict]:
        """
        Split a large chapter into smaller chunks
        
        Args:
            chapter: Chapter dict with content
            max_tokens: Maximum tokens per chunk
        
        Returns:
            List of chapter chunks
        """
        content = chapter['content']
        title = chapter['title']
        
        # Split by paragraphs
        paragraphs = content.split('\n\n')
        
        chunks = []
        current_chunk = []
        current_tokens = 0
        chunk_idx = 1
        
        for para in paragraphs:
            para_tokens = self.count_tokens(para)
            
            if current_tokens + para_tokens > max_tokens:
                # Save current chunk
                if current_chunk:
                    chunks.append({
                        'title': f"{title} (Part {chunk_idx})",
                        'content': '\n\n'.join(current_chunk),
                        'level': chapter['level'],
                        'order': chapter['order'] + (chunk_idx - 1) * 0.1,
                        'chapter_num': chapter.get('chapter_num'),
                        'token_count': current_tokens,
                        'needs_split': False,
                        'is_split_part': True,
                        'part_number': chunk_idx
                    })
                    chunk_idx += 1
                
                # Start new chunk
                current_chunk = [para]
                current_tokens = para_tokens
            else:
                current_chunk.append(para)
                current_tokens += para_tokens
        
        # Don't forget the last chunk
        if current_chunk:
            chunks.append({
                'title': f"{title} (Part {chunk_idx})" if chunk_idx > 1 else title,
                'content': '\n\n'.join(current_chunk),
                'level': chapter['level'],
                'order': chapter['order'] + (chunk_idx - 1) * 0.1,
                'chapter_num': chapter.get('chapter_num'),
                'token_count': current_tokens,
                'needs_split': False,
                'is_split_part': chunk_idx > 1,
                'part_number': chunk_idx if chunk_idx > 1 else None
            })
        
        return chunks if chunks else [chapter]


# Global parser instance
chapter_parser = ChapterParser()
