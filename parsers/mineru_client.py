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
from typing import Dict, Optional, Tuple
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
    
    def upload_file(self, file_path: Path) -> str:
        """
        Upload PDF file to MinerU using batch upload API
        
        Args:
            file_path: Path to PDF file
        
        Returns:
            batch_id for tracking the parsing job
        
        Raises:
            ValueError: If file is too large
            Exception: If upload fails
        """
        if not self.check_file_size(file_path):
            file_size_mb = file_path.stat().st_size / (1024 * 1024)
            raise ValueError(
                f"File size ({file_size_mb:.2f} MB) exceeds limit (200 MB). "
                "Please split the PDF into smaller files."
            )
        
        # Step 1: Request upload URL
        url = f"{self.api_url}/file-urls/batch"
        
        data = {
            "files": [
                {
                    "name": file_path.name,
                    "data_id": str(uuid.uuid4())[:32]  # Generate unique data_id
                }
            ],
            "model_version": "vlm",  # Use VLM model for better accuracy
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
            upload_url = result['data']['file_urls'][0]
            
            # Step 2: Upload file to the provided URL
            with open(file_path, 'rb') as f:
                upload_response = requests.put(
                    upload_url,
                    data=f,
                    timeout=300  # 5 minutes for large files
                )
                upload_response.raise_for_status()
            
            print(f"File uploaded successfully. Batch ID: {batch_id}")
            
            return batch_id
        
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to upload file to MinerU: {str(e)}")
    
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
            
            status_dict = {
                'status': status_map.get(state, 'processing'),
                'state': state,
                'message': file_result.get('err_msg', ''),
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
            
            json_path = json_files[0] if json_files else None
            md_path = md_files[0] if md_files else None
            
            # Clean up ZIP file
            zip_path.unlink()
            
            print(f"Extracted files:")
            if json_path:
                print(f"  JSON: {json_path}")
            if md_path:
                print(f"  MD: {md_path}")
            
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
        
        # Upload file
        batch_id = self.upload_file(file_path)
        
        # For now, return batch_id immediately for async processing
        # The actual waiting and downloading will be handled by background task
        return batch_id, None, None


# Global client instance
mineru_client = MinerUClient()
