"""
DOCX Parser (Dependency Free)
Parses .docx files using standard python libraries (zipfile, xml.etree.ElementTree)
Converts DOCX content to Markdown for chapter segmentation.
"""

import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional, Dict, List
import re

class DocxParser:
    """
    Parses .docx files without external dependencies (like python-docx).
    Extracts text and basic structure (headings) to Markdown.
    """
    
    # XML Namespaces
    NS = {
        'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
    }
    
    def __init__(self):
        pass
        
    def parse(self, file_path: Path) -> Optional[str]:
        """
        Parse DOCX file and return Markdown content
        """
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
            
        try:
            with zipfile.ZipFile(file_path, 'r') as docx:
                # Read document.xml
                xml_content = docx.read('word/document.xml')
                tree = ET.fromstring(xml_content)
                
                # Extract paragraphs
                markdown_lines = []
                
                for p in tree.findall('.//w:p', self.NS):
                    text = self._get_paragraph_text(p)
                    if not text.strip():
                        continue
                        
                    style = self._get_paragraph_style(p)
                    
                    # Convert to Markdown based on style
                    if style and style.startswith('Heading'):
                        try:
                            level = int(style.replace('Heading', ''))
                            prefix = '#' * min(level, 6)
                            markdown_lines.append(f"\n{prefix} {text}\n")
                        except ValueError:
                            markdown_lines.append(f"{text}\n")
                    else:
                        markdown_lines.append(f"{text}\n")
                        
                return '\n'.join(markdown_lines)
                
        except Exception as e:
            print(f"Error parsing DOCX: {e}")
            return None

    def _get_paragraph_text(self, paragraph: ET.Element) -> str:
        """Extract text from a paragraph element"""
        texts = []
        for t in paragraph.findall('.//w:t', self.NS):
            if t.text:
                texts.append(t.text)
        return ''.join(texts)

    def _get_paragraph_style(self, paragraph: ET.Element) -> Optional[str]:
        """Get the style ID of the paragraph (e.g., 'Heading1')"""
        pPr = paragraph.find('w:pPr', self.NS)
        if pPr is not None:
            pStyle = pPr.find('w:pStyle', self.NS)
            if pStyle is not None:
                return pStyle.get(f"{{{self.NS['w']}}}val")
        return None

# Singleton instance
docx_parser = DocxParser()
