"""
Enhanced PDF extraction using PyMuPDF with image support.
Extracts text, images, and coordinates losslessly.
"""
import logging
import base64
import re
from typing import List, Dict, Any, Tuple, Optional
from pathlib import Path
import io

logger = logging.getLogger(__name__)


class PyMuPDFExtractor:
    """
    Enhanced PDF extractor using PyMuPDF (fitz) for lossless extraction.
    Extracts text, images, coordinates, and page numbers.
    """
    
    def __init__(self):
        self.fitz = None
        self._load_library()
    
    def _load_library(self):
        """Lazy load PyMuPDF."""
        try:
            import fitz  # PyMuPDF
            self.fitz = fitz
            logger.info("PyMuPDF loaded successfully")
        except ImportError:
            logger.error("PyMuPDF not available - install with: pip install PyMuPDF")
            raise
    
    def extract_text_with_coordinates(self, pdf_path: str) -> List[Dict[str, Any]]:
        """
        Extract text with bounding box coordinates.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            List of text blocks with coordinates
        """
        if not self.fitz:
            raise RuntimeError("PyMuPDF not available")
        
        text_blocks = []
        
        try:
            doc = self.fitz.open(pdf_path)
            
            for page_num, page in enumerate(doc, start=1):
                blocks = page.get_text("dict")["blocks"]
                
                for block in blocks:
                    if block["type"] == 0:  # Text block
                        bbox = block["bbox"]  # (x0, y0, x1, y1)
                        
                        # Extract text from lines
                        text_parts = []
                        for line in block.get("lines", []):
                            for span in line.get("spans", []):
                                text_parts.append(span["text"])
                        
                        text = " ".join(text_parts).strip()
                        
                        if text:
                            text_blocks.append({
                                "text": text,
                                "bbox": bbox,
                                "page": page_num,
                                "type": "text"
                            })
            
            doc.close()
            logger.info(f"Extracted {len(text_blocks)} text blocks from {pdf_path}")
            
        except Exception as e:
            logger.error(f"Text extraction failed: {e}")
            raise
        
        return text_blocks
    
    def extract_images(self, pdf_path: str) -> List[Dict[str, Any]]:
        """
        Extract all images from PDF with coordinates and base64 encoding.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            List of images with metadata
        """
        if not self.fitz:
            raise RuntimeError("PyMuPDF not available")
        
        images = []
        
        try:
            doc = self.fitz.open(pdf_path)
            
            for page_num, page in enumerate(doc, start=1):
                # Get images from page
                image_list = page.get_images(full=True)
                
                for img_index, img in enumerate(image_list):
                    xref = img[0]
                    
                    # Extract image
                    base_image = doc.extract_image(xref)
                    image_bytes = base_image["image"]
                    image_ext = base_image["ext"]
                    
                    # Get image bounding box
                    img_rects = page.get_image_rects(xref)
                    bbox = img_rects[0] if img_rects else None
                    
                    # Encode to base64
                    image_base64 = base64.b64encode(image_bytes).decode('utf-8')
                    
                    images.append({
                        "image_data": image_base64,
                        "format": image_ext,
                        "bbox": list(bbox) if bbox else None,
                        "page": page_num,
                        "index": img_index,
                        "type": "image"
                    })
            
            doc.close()
            logger.info(f"Extracted {len(images)} images from {pdf_path}")
            
        except Exception as e:
            logger.error(f"Image extraction failed: {e}")
            # Don't fail if images can't be extracted
            pass
        
        return images
    
    def extract_text(self, pdf_path: str) -> str:
        """
        Extract all text from PDF (simple version).
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Extracted text
        """
        if not self.fitz:
            raise RuntimeError("PyMuPDF not available")
        
        text_parts = []
        
        try:
            doc = self.fitz.open(pdf_path)
            
            for page in doc:
                text_parts.append(page.get_text())
            
            doc.close()
            
        except Exception as e:
            logger.error(f"Text extraction failed: {e}")
            raise
        
        return '\n'.join(text_parts)
    
    def get_page_count(self, pdf_path: str) -> int:
        """Get number of pages in PDF."""
        if not self.fitz:
            raise RuntimeError("PyMuPDF not available")
        
        try:
            doc = self.fitz.open(pdf_path)
            count = len(doc)
            doc.close()
            return count
        except Exception as e:
            logger.error(f"Failed to get page count: {e}")
            return 0
    
    def extract_questions_with_images(
        self, 
        pdf_path: str
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Extract both questions and images from PDF.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Tuple of (questions, images)
        """
        # Extract text with coordinates
        text_blocks = self.extract_text_with_coordinates(pdf_path)
        
        # Extract images
        images = self.extract_images(pdf_path)
        
        # Combine text into full content
        full_text = "\n".join([block["text"] for block in text_blocks])
        
        # Parse questions from text
        questions = self._parse_questions(full_text, text_blocks, images)
        
        return questions, images
    
    def _parse_questions(
        self,
        text: str,
        text_blocks: List[Dict[str, Any]],
        images: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Parse questions from extracted text and associate with images.
        
        Args:
            text: Full extracted text
            text_blocks: Text blocks with coordinates
            images: Extracted images with coordinates
            
        Returns:
            List of parsed questions
        """
        questions = []
        
        # Clean text
        cleaned_text = self._clean_text(text)
        
        # Extract Part A questions
        part_a = self._extract_part_a(cleaned_text)
        
        # Extract Part B questions
        part_b = self._extract_part_b(cleaned_text)
        
        # Combine
        all_questions = part_a + part_b
        
        # Associate images with questions based on proximity
        for question in all_questions:
            question['images'] = self._find_nearby_images(
                question, text_blocks, images
            )
        
        return all_questions
    
    def _find_nearby_images(
        self,
        question: Dict[str, Any],
        text_blocks: List[Dict[str, Any]],
        images: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Find images that are near this question based on spatial proximity.
        """
        # Simple implementation: return images on same page
        # In production, use bbox proximity
        question_page = question.get('page', 1)
        
        nearby = [
            img for img in images 
            if img.get('page') == question_page
        ]
        
        return nearby
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize text."""
        lines = text.split('\n')
        cleaned = []
        
        for line in lines:
            line = line.strip()
            if line:
                cleaned.append(line)
        
        return '\n'.join(cleaned)
    
    def _extract_part_a(self, text: str) -> List[Dict[str, Any]]:
        """Extract Part A questions (Q1-10)."""
        questions = []
        
        # Pattern: Question number followed by text and marks
        pattern = r'(?:^|\n)\s*(\d+)\s*[.)]\s*([^\n]+?)(?:\s*\((\d+)\s*marks?\))?'
        
        matches = re.finditer(pattern, text, re.MULTILINE | re.IGNORECASE)
        
        for match in matches:
            q_num = match.group(1)
            q_text = match.group(2).strip()
            marks = match.group(3)
            
            # Part A is typically Q1-10
            if q_num.isdigit() and 1 <= int(q_num) <= 10:
                questions.append({
                    'question_number': q_num,
                    'text': q_text,
                    'marks': int(marks) if marks else 3,  # Default 3 for Part A
                    'part': 'A'
                })
        
        return questions
    
    def _extract_part_b(self, text: str) -> List[Dict[str, Any]]:
        """Extract Part B questions (Q11-20, may have sub-parts)."""
        questions = []
        
        # Pattern for main questions
        pattern = r'(?:^|\n)\s*(\d+)\s*[.)]\s*([^\n]+?)(?:\s*\((\d+)\s*marks?\))?'
        
        # Pattern for sub-questions (11a, 11b, etc.)
        sub_pattern = r'(?:^|\n)\s*(\d+)\s*([a-z])\s*[.)]\s*([^\n]+?)(?:\s*\((\d+)\s*marks?\))?'
        
        matches = re.finditer(pattern, text, re.MULTILINE | re.IGNORECASE)
        
        for match in matches:
            q_num = match.group(1)
            q_text = match.group(2).strip()
            marks = match.group(3)
            
            # Part B is typically Q11-20
            if q_num.isdigit() and 11 <= int(q_num) <= 20:
                questions.append({
                    'question_number': q_num,
                    'text': q_text,
                    'marks': int(marks) if marks else 14,  # Default 14 for Part B
                    'part': 'B',
                    'sub_questions': []
                })
        
        # Extract sub-questions
        sub_matches = re.finditer(sub_pattern, text, re.MULTILINE | re.IGNORECASE)
        
        for match in sub_matches:
            q_num = match.group(1)
            sub_letter = match.group(2)
            q_text = match.group(3).strip()
            marks = match.group(4)
            
            if q_num.isdigit() and 11 <= int(q_num) <= 20:
                # Find parent question and add sub-question
                for q in questions:
                    if q['question_number'] == q_num:
                        q['sub_questions'].append({
                            'letter': sub_letter,
                            'text': q_text,
                            'marks': int(marks) if marks else 7
                        })
                        break
        
        return questions


def extract_with_ocr(pdf_path: str) -> str:
    """
    Fallback: Extract text using OCR when PDF is scanned.
    Uses Tesseract OCR with OpenCV preprocessing.
    """
    try:
        import pytesseract
        from PIL import Image
        import fitz
        
        text_parts = []
        
        doc = fitz.open(pdf_path)
        
        for page_num, page in enumerate(doc):
            # Convert page to image
            pix = page.get_pixmap(dpi=300)
            
            # Convert to PIL Image
            img_data = pix.tobytes("png")
            img = Image.open(io.BytesIO(img_data))
            
            # OCR
            text = pytesseract.image_to_string(img)
            text_parts.append(text)
        
        doc.close()
        
        logger.info(f"OCR extraction completed for {pdf_path}")
        return '\n'.join(text_parts)
        
    except Exception as e:
        logger.error(f"OCR extraction failed: {e}")
        return ""
