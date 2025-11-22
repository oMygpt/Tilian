"""
EPUB Parser module
Parses EPUB files using standard Python libraries (zipfile, xml, html.parser)
Converts EPUB content to Markdown for further processing
"""

import zipfile
import xml.etree.ElementTree as ET
import html.parser
import re
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import urllib.parse

class HTMLToMarkdown(html.parser.HTMLParser):
    """Simple HTML to Markdown converter"""
    
    def __init__(self):
        super().__init__()
        self.markdown = []
        self.in_heading = False
        self.heading_level = 0
        self.in_link = False
        self.link_url = ""
        self.link_text = ""
        self.list_depth = 0
        self.in_list_item = False
        self.in_code = False
        self.in_pre = False
        self.in_p = False
        
    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        
        if tag in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            self.in_heading = True
            self.heading_level = int(tag[1])
            self.markdown.append('\n\n' + '#' * self.heading_level + ' ')
            
        elif tag == 'p':
            self.in_p = True
            self.markdown.append('\n\n')
            
        elif tag == 'br':
            self.markdown.append('\n')
            
        elif tag == 'strong' or tag == 'b':
            self.markdown.append('**')
            
        elif tag == 'em' or tag == 'i':
            self.markdown.append('*')
            
        elif tag == 'code':
            if not self.in_pre:
                self.markdown.append('`')
            self.in_code = True
            
        elif tag == 'pre':
            self.in_pre = True
            self.markdown.append('\n\n```\n')
            
        elif tag == 'a':
            self.in_link = True
            self.link_url = attrs_dict.get('href', '')
            self.link_text = ""
            self.markdown.append('[')
            
        elif tag == 'img':
            alt = attrs_dict.get('alt', 'image')
            # We skip image URLs for now as we're focusing on text content
            self.markdown.append(f'![{alt}](image)')
            
        elif tag == 'ul' or tag == 'ol':
            self.list_depth += 1
            self.markdown.append('\n')
            
        elif tag == 'li':
            self.in_list_item = True
            indent = '  ' * (self.list_depth - 1)
            self.markdown.append(f'\n{indent}- ')
            
        elif tag == 'blockquote':
            self.markdown.append('\n\n> ')
            
        elif tag == 'hr':
            self.markdown.append('\n\n---\n\n')

    def handle_endtag(self, tag):
        if tag in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            self.in_heading = False
            self.markdown.append('\n\n')
            
        elif tag == 'p':
            self.in_p = False
            self.markdown.append('\n\n')
            
        elif tag == 'strong' or tag == 'b':
            self.markdown.append('**')
            
        elif tag == 'em' or tag == 'i':
            self.markdown.append('*')
            
        elif tag == 'code':
            if not self.in_pre:
                self.markdown.append('`')
            self.in_code = False
            
        elif tag == 'pre':
            self.in_pre = False
            self.markdown.append('\n```\n\n')
            
        elif tag == 'a':
            self.in_link = False
            self.markdown.append(f']({self.link_url})')
            
        elif tag == 'ul' or tag == 'ol':
            self.list_depth -= 1
            self.markdown.append('\n')
            
        elif tag == 'li':
            self.in_list_item = False

    def handle_data(self, data):
        if self.in_pre:
            self.markdown.append(data)
        else:
            # Normalize whitespace but keep single spaces
            text = re.sub(r'\s+', ' ', data)
            if text:
                self.markdown.append(text)

    def get_markdown(self):
        # Join and clean up multiple newlines
        text = "".join(self.markdown)
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()


class EpubParser:
    """Parses EPUB files and extracts content as Markdown"""
    
    def __init__(self):
        self.ns = {
            'u': 'urn:oasis:names:tc:opendocument:xmlns:container',
            'opf': 'http://www.idpf.org/2007/opf',
            'dc': 'http://purl.org/dc/elements/1.1/',
            'ncx': 'http://www.daisy.org/z3986/2005/ncx/'
        }
        
    def parse(self, epub_path: Path) -> Tuple[str, List[Dict]]:
        """
        Parse EPUB file
        
        Args:
            epub_path: Path to EPUB file
            
        Returns:
            Tuple of (full_markdown_content, metadata_dict)
        """
        if not zipfile.is_zipfile(epub_path):
            raise ValueError("Not a valid ZIP/EPUB file")
            
        with zipfile.ZipFile(epub_path, 'r') as zf:
            # 1. Find OPF file path from container.xml
            try:
                container_xml = zf.read('META-INF/container.xml')
                root = ET.fromstring(container_xml)
                root_files = root.findall('.//u:rootfile', self.ns)
                if not root_files:
                    raise ValueError("No rootfile found in container.xml")
                opf_path = root_files[0].get('full-path')
            except Exception as e:
                raise ValueError(f"Failed to parse container.xml: {e}")
                
            # 2. Parse OPF file
            opf_dir = Path(opf_path).parent
            opf_content = zf.read(opf_path)
            
            # Remove namespaces for easier parsing if needed, but we use dict
            # For XML parsing with namespaces, we need to register them or handle them
            # Let's try to handle them properly
            
            # We need to handle the default namespace issue in ElementTree
            # A simple hack is to remove the xmlns declarations for simple parsing
            # or use the namespaces map
            
            # Let's use a more robust way: regex to strip namespaces for simplicity
            # since EPUB versions vary
            opf_str = opf_content.decode('utf-8')
            opf_str_clean = re.sub(r' xmlns="[^"]+"', '', opf_str, count=1)
            opf_str_clean = re.sub(r' xmlns:opf="[^"]+"', '', opf_str_clean, count=1)
            opf_str_clean = re.sub(r' xmlns:dc="[^"]+"', '', opf_str_clean, count=1)
            
            try:
                opf_root = ET.fromstring(opf_str_clean)
            except:
                # Fallback to original content if cleaning failed
                opf_root = ET.fromstring(opf_content)
            
            # 3. Extract Metadata
            metadata = self._extract_metadata(opf_root)
            
            # 4. Get Manifest (id -> href)
            manifest = {}
            for item in opf_root.findall('.//manifest/item'):
                item_id = item.get('id')
                href = item.get('href')
                manifest[item_id] = href
                
            # 5. Get Spine (reading order)
            spine = []
            for itemref in opf_root.findall('.//spine/itemref'):
                idref = itemref.get('idref')
                if idref in manifest:
                    spine.append(manifest[idref])
            
            # 6. Extract Content
            full_content = []
            
            for href in spine:
                # Resolve path relative to OPF file
                # href might be URL encoded
                href_decoded = urllib.parse.unquote(href)
                
                # Construct full path in zip
                if str(opf_dir) == '.':
                    file_path = href_decoded
                else:
                    file_path = str(opf_dir / href_decoded).replace('\\', '/')
                
                try:
                    html_content = zf.read(file_path).decode('utf-8')
                    
                    # Convert HTML to Markdown
                    converter = HTMLToMarkdown()
                    converter.feed(html_content)
                    markdown = converter.get_markdown()
                    
                    if markdown.strip():
                        full_content.append(markdown)
                        full_content.append("\n\n---\n\n") # Separator
                        
                except KeyError:
                    print(f"Warning: File {file_path} not found in archive")
                except Exception as e:
                    print(f"Error parsing {file_path}: {e}")
            
            return "".join(full_content), metadata
            
    def _extract_metadata(self, opf_root) -> Dict:
        """Extract metadata from OPF root"""
        metadata = {}
        
        # Find metadata element
        meta_elem = opf_root.find('.//metadata')
        if meta_elem is None:
            return metadata
            
        # Helper to get text safely
        def get_text(tag_name):
            # Try with dc: prefix and without
            elem = meta_elem.find(f'.//dc:{tag_name}', self.ns)
            if elem is None:
                elem = meta_elem.find(f'.//{tag_name}')
            return elem.text if elem is not None else None
            
        metadata['title'] = get_text('title') or 'Untitled'
        metadata['author'] = get_text('creator') or 'Unknown'
        metadata['language'] = get_text('language') or 'en'
        metadata['publisher'] = get_text('publisher')
        metadata['date'] = get_text('date')
        
        return metadata

# Global instance
epub_parser = EpubParser()
