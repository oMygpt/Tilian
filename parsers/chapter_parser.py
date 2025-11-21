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
        chapters = []
        
        try:
            with open(md_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            lines = content.split('\n')
            
            # Find all level-1 headings that look like chapters
            chapter_heads = []
            for i, line in enumerate(lines):
                # Check if it's a level-1 heading
                if not line.startswith('# '):
                    continue
                
                title = line[2:].strip()
                
                # Skip TOC and metadata
                skip_titles = ['目录', 'table of contents', 'contents']
                if title.lower() in skip_titles:
                    continue
                
                # Check if it looks like a chapter
                if self.is_chapter_header(title):
                    chapter_num = self.extract_chapter_number(title)
                    chapter_heads.append((i, title, chapter_num))
            
            # If no chapter headers found, fall back to all level-1 headings
            if not chapter_heads:
                print("No chapter headers found, using all level-1 headings")
                for i, line in enumerate(lines):
                    if line.startswith('# '):
                        title = line[2:].strip()
                        skip_titles = ['目录', 'table of contents', 'contents']
                        if title.lower() not in skip_titles and len(title) >= 2:
                            chapter_num = self.extract_chapter_number(title)
                            chapter_heads.append((i, title, chapter_num))
            
            # Extract content for each chapter
            for order, (line_idx, title, chapter_num) in enumerate(chapter_heads):
                # Find the end of this chapter (start of next chapter or end of file)
                next_idx = chapter_heads[order + 1][0] if order + 1 < len(chapter_heads) else len(lines)
                
                # Extract content
                chapter_lines = lines[line_idx + 1:next_idx]  # Skip the heading line itself
                content_text = '\n'.join(chapter_lines).strip()
                
                chapters.append({
                    'title': title,
                    'content': content_text,
                    'level': 1,
                    'order': order,
                    'chapter_num': chapter_num,
                    'token_count': 0  # Will be calculated later
                })
            
            print(f"Parsed {len(chapters)} chapters from markdown")
        
        except Exception as e:
            print(f"Error parsing chapters from MD: {e}")
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
