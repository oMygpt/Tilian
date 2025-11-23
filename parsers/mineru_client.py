"""
MinerU API Client
Handles PDF parsing via MinerU service
Based on official API documentation: https://mineru.net/apiManage/docs
"""

import os
import time
import uuid
import requests
import zipfile
import json
from pathlib import Path
import shutil
import PyPDF2
from typing import Dict, Optional, Tuple, List
import config

class MinerUClient:
    """Client for MinerU PDF parsing API"""
    
    def __init__(self, api_key: str = None, api_url: str = None):
        self.api_key = api_key or config.MINERU_API_KEY
        self.api_url = (api_url or config.MINERU_API_URL).rstrip('/')
        
        if not self.api_key:
            raise ValueError("MinerU API key not configured")
        
        self.headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
            'Accept': '*/*'
        }
    
    def check_file_size(self, file_path: Path) -> bool:
        """
        Check if file size is within limits
        MinerU limit: 200MB, max 600 pages
        
        Args:
            file_path: Path to PDF file
        
        Returns:
            True if file size is acceptable, False otherwise
        """
        file_size_mb = file_path.stat().st_size / (1024 * 1024)
        return file_size_mb <= 200  # MinerU limit is 200MB

    def split_pdf(self, file_path: Path, max_size_mb: int = 180) -> List[Path]:
        """
        Split a large PDF into smaller chunks
        
        Args:
            file_path: Path to the large PDF file
            max_size_mb: Maximum size for each chunk in MB
            
        Returns:
            List of paths to the split PDF files
        """
        print(f"Splitting large PDF: {file_path}")
        output_files = []
        
        try:
            reader = PyPDF2.PdfReader(file_path)
            total_pages = len(reader.pages)
            
            # Estimate pages per chunk based on file size
            # This is a rough estimate, assuming uniform page size
            file_size_mb = file_path.stat().st_size / (1024 * 1024)
            avg_page_size_mb = file_size_mb / total_pages
            pages_per_chunk = int(max_size_mb / avg_page_size_mb)
            
            # Safety margin
            pages_per_chunk = max(1, int(pages_per_chunk * 0.9))
            
            # Enforce hard page limit (MinerU limit is 600, use 500 for safety)
            pages_per_chunk = min(pages_per_chunk, 500)
            
            print(f"Total pages: {total_pages}, Estimated pages per chunk: {pages_per_chunk}")
            
            current_page = 0
            chunk_index = 1
            
            temp_dir = file_path.parent / "chunks" / file_path.stem
            temp_dir.mkdir(parents=True, exist_ok=True)
            
            while current_page < total_pages:
                writer = PyPDF2.PdfWriter()
                end_page = min(current_page + pages_per_chunk, total_pages)
                
                for i in range(current_page, end_page):
                    writer.add_page(reader.pages[i])
                
                chunk_filename = f"{file_path.stem}_part{chunk_index}.pdf"
                chunk_path = temp_dir / chunk_filename
                
                with open(chunk_path, "wb") as f:
                    writer.write(f)
                
                # Verify size, if too big, we might need to be smarter, but for now this is a good heuristic
                chunk_size_mb = chunk_path.stat().st_size / (1024 * 1024)
                print(f"Created chunk {chunk_index}: {chunk_filename} ({chunk_size_mb:.2f} MB)")
                
                output_files.append(chunk_path)
                current_page = end_page
                chunk_index += 1
                
            return output_files
            
        except Exception as e:
            print(f"Error splitting PDF: {e}")
            # Clean up if failed
            if 'temp_dir' in locals() and temp_dir.exists():
                shutil.rmtree(temp_dir)
            raise
    
    def upload_files(self, file_paths: List[Path]) -> str:
        """
        Upload one or more PDF files to MinerU using batch upload API
        
        Args:
            file_paths: List of paths to PDF files
        
        Returns:
            batch_id for tracking the parsing job
        """
        # Step 1: Request upload URL
        url = f"{self.api_url}/file-urls/batch"
        
        files_data = []
        for fp in file_paths:
            files_data.append({
                "name": fp.name,
                "data_id": str(uuid.uuid4())[:32]
            })
            
        data = {
            "files": files_data,
            "model_version": "vlm",
            "enable_formula": True,
            "enable_table": True
        }
        
        try:
            # Request upload URL
            response = requests.post(
                url,
                headers=self.headers,
                json=data,
                timeout=30
            )
            response.raise_for_status()
            
            result = response.json()
            
            if result.get('code') != 0:
                raise Exception(f"Failed to get upload URL: {result.get('msg', 'Unknown error')}")
            
            batch_id = result['data']['batch_id']
            file_urls = result['data']['file_urls']
            
            if len(file_urls) != len(file_paths):
                 raise Exception("Mismatch in number of upload URLs received")

            # Step 2: Upload files to the provided URLs
            for i, fp in enumerate(file_paths):
                upload_url = file_urls[i]
                print(f"Uploading {fp.name}...")
                with open(fp, 'rb') as f:
                    upload_response = requests.put(
                        upload_url,
                        data=f,
                        timeout=300  # 5 minutes per file
                    )
                    upload_response.raise_for_status()
            
            print(f"All files uploaded successfully. Batch ID: {batch_id}")
            
            return batch_id
        
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to upload files to MinerU: {str(e)}")
    
    def get_parse_status(self, batch_id: str) -> Dict:
        """
        Check parsing status for batch
        
        Args:
            batch_id: Batch ID from upload
        
        Returns:
            Status dict with state, progress, and results
        """
        try:
            url = f"{self.api_url}/extract-results/batch/{batch_id}"
            
            response = requests.get(
                url,
                headers=self.headers,
                timeout=10
            )
            response.raise_for_status()
            
            result = response.json()
            
            if result.get('code') != 0:
                return {
                    'status': 'error',
                    'progress': 0,
                    'message': result.get('msg', 'Unknown error')
                }
            
            # Get first file's status
            extract_results = result['data'].get('extract_result', [])
            
            if not extract_results:
                return {
                    'status': 'waiting-file',
                    'progress': 0,
                    'message': 'Waiting for file processing'
                }
            
            file_result = extract_results[0]
            state = file_result['state']
            
            # Map MinerU states to our states
            status_map = {
                'done': 'completed',
                'running': 'processing',
                'pending': 'processing',
                'waiting-file': 'processing',
                'converting': 'processing',
                'failed': 'error'
            }
            
            error_message = file_result.get('err_msg', '')
            if "number of pages exceeds limit" in error_message:
                error_message = "MinerU API Limit: Daily page limit reached or file too large"
            
            status_dict = {
                'status': status_map.get(state, 'processing'),
                'state': state,
                'message': error_message,
                'progress': 50  # Default progress
            }
            
            # Calculate progress for running tasks
            if state == 'running' and 'extract_progress' in file_result:
                progress_info = file_result['extract_progress']
                extracted = progress_info.get('extracted_pages', 0)
                total = progress_info.get('total_pages', 1)
                status_dict['progress'] = int((extracted / total) * 100)
            elif state == 'done':
                status_dict['progress'] = 100
                status_dict['full_zip_url'] = file_result.get('full_zip_url')
            
            return status_dict
        
        except requests.exceptions.RequestException as e:
            return {
                'status': 'error',
                'progress': 0,
                'message': str(e)
            }
    
    def wait_for_completion(self, batch_id: str, timeout: int = None, poll_interval: int = 5) -> bool:
        """
        Wait for parsing to complete
        
        Args:
            batch_id: Batch ID
            timeout: Max wait time in seconds (default from config)
            poll_interval: Seconds between status checks
        
        Returns:
            True if completed successfully, False otherwise
        """
        timeout = timeout or config.PARSE_TASK_TIMEOUT
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            status = self.get_parse_status(batch_id)
            
            if status['status'] == 'completed':
                return True
            elif status['status'] == 'error':
                print(f"Parsing failed: {status['message']}")
                return False
            
            time.sleep(poll_interval)
        
        print("Parsing timeout")
        return False
    
    def merge_results(self, output_dir: Path, json_files: List[Path], md_files: List[Path]) -> Tuple[Path, Path]:
        """
        Merge multiple JSON and Markdown files from split PDF parsing
        
        Args:
            output_dir: Directory where files are located
            json_files: List of JSON files
            md_files: List of Markdown files
            
        Returns:
            Tuple of (merged_json_path, merged_md_path)
        """
        # Sort files to ensure correct order (part1, part2, ...)
        json_files.sort(key=lambda p: p.name)
        md_files.sort(key=lambda p: p.name)
        
        # 1. Merge Markdown
        merged_md_path = output_dir / "merged.md"
        with open(merged_md_path, 'w', encoding='utf-8') as outfile:
            for i, md_file in enumerate(md_files):
                if i > 0:
                    outfile.write("\n\n") # Add separation
                with open(md_file, 'r', encoding='utf-8') as infile:
                    outfile.write(infile.read())
        
        # 2. Merge JSON
        # This is more complex as we need to adjust page numbers
        merged_json_path = output_dir / "merged.json"
        
        try:
            merged_data = []
            total_pages_offset = 0
            
            for json_file in json_files:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                # Handle different JSON structures
                # Case 1: List of page objects
                if isinstance(data, list):
                    for item in data:
                        if 'page_idx' in item:
                            item['page_idx'] += total_pages_offset
                    merged_data.extend(data)
                    
                    # Update offset for next file
                    if data:
                        max_page = max((item.get('page_idx', 0) for item in data), default=0)
                        total_pages_offset = max_page + 1
                
                # Case 2: Dict with content list
                elif isinstance(data, dict):
                    # If it's a dict, we might need to merge specific keys
                    if not merged_data:
                        merged_data = data # Initialize with first
                    else:
                        # Try to merge known list fields
                        current_max_page = 0
                        for key in ['content_list', 'layout_items']:
                            if key in data and isinstance(data[key], list):
                                if key not in merged_data:
                                    merged_data[key] = []
                                # Adjust page numbers in the list
                                items = data[key]
                                for item in items:
                                    if 'page_idx' in item:
                                        item['page_idx'] += total_pages_offset
                                        current_max_page = max(current_max_page, item['page_idx'])
                                merged_data[key].extend(items)
                        
                        # Update offset
                        if current_max_page > 0:
                            total_pages_offset = current_max_page + 1
            
            with open(merged_json_path, 'w', encoding='utf-8') as f:
                json.dump(merged_data, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            print(f"Error merging JSON: {e}")
            # If merge fails, just return the first one or None
            merged_json_path = json_files[0] if json_files else None

        return merged_json_path, merged_md_path

    def download_results(self, batch_id: str, output_dir: Path) -> Tuple[Optional[Path], Optional[Path]]:
        """
        Download and extract parsing results (JSON and MD files)
        
        Args:
            batch_id: Batch ID
            output_dir: Directory to save results
        
        Returns:
            Tuple of (json_path, md_path)
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Get download URL
        status = self.get_parse_status(batch_id)
        
        if status['status'] != 'completed':
            print(f"Task not completed yet. Status: {status['status']}")
            return None, None
        
        full_zip_url = status.get('full_zip_url')
        if not full_zip_url:
            print("No download URL available")
            return None, None
        
        try:
            # Download ZIP file
            print(f"Downloading results from {full_zip_url}")
            response = requests.get(full_zip_url, timeout=120)
            response.raise_for_status()
            
            # Save ZIP file
            zip_path = output_dir / f"{batch_id}.zip"
            with open(zip_path, 'wb') as f:
                f.write(response.content)
            
            # Extract ZIP file
            print(f"Extracting ZIP file...")
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(output_dir)
            
            # Find JSON and MD files
            json_files = list(output_dir.glob('**/*.json'))
            md_files = list(output_dir.glob('**/*.md'))
            
            # Clean up ZIP file
            zip_path.unlink()
            
            print(f"Extracted files: {len(json_files)} JSON, {len(md_files)} MD")
            
            if len(md_files) > 1:
                print("Multiple files detected, merging...")
                return self.merge_results(output_dir, json_files, md_files)
            
            json_path = json_files[0] if json_files else None
            md_path = md_files[0] if md_files else None
            
            return json_path, md_path
        
        except requests.exceptions.RequestException as e:
            print(f"Error downloading results: {e}")
            return None, None
        except zipfile.BadZipFile as e:
            print(f"Error extracting ZIP: {e}")
            return None, None
    
    def parse_pdf(self, file_path: Path, output_dir: Path = None) -> Tuple[str, Optional[Path], Optional[Path]]:
        """
        Complete PDF parsing workflow
        
        Args:
            file_path: Path to PDF file
            output_dir: Output directory (default: config.PARSED_DIR)
        
        Returns:
            Tuple of (batch_id, json_path, md_path)
        """
        output_dir = output_dir or config.PARSED_DIR
        
        files_to_upload = [file_path]
        
        # Check if splitting is needed
        if not self.check_file_size(file_path):
            print(f"File {file_path.name} is too large, splitting...")
            files_to_upload = self.split_pdf(file_path, max_size_mb=config.PDF_SPLIT_SIZE)
        
        # Upload files
        batch_id = self.upload_files(files_to_upload)
        
        # For now, return batch_id immediately for async processing
        # The actual waiting and downloading will be handled by background task
        return batch_id, None, None


# Global client instance
mineru_client = MinerUClient()
