"""
Universal File Parser

Handles multiple file formats:
- PDF, Word (DOCX), Excel, CSV
- Images (with OCR)
- Text, JSON, XML
- HL7, FHIR (clinical standards)
"""

import io
import json
import re
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass

from src.utils.logging import logger


@dataclass
class ParsedDocument:
    """Parsed document result."""
    content: str
    file_type: str
    metadata: Dict[str, Any]
    tables: List[Dict[str, Any]]  # Extracted tables if any
    raw_text: str
    confidence: float


class UniversalFileParser:
    """
    Parse any file type and extract text content.
    Supports clinical formats like HL7, FHIR, CDA.
    """
    
    SUPPORTED_EXTENSIONS = {
        # Documents
        '.txt': 'text',
        '.md': 'markdown',
        '.pdf': 'pdf',
        '.docx': 'word',
        '.doc': 'word',
        '.rtf': 'rtf',
        # Data
        '.csv': 'csv',
        '.xlsx': 'excel',
        '.xls': 'excel',
        '.json': 'json',
        '.xml': 'xml',
        # Clinical
        '.hl7': 'hl7',
        '.fhir': 'fhir',
        '.cda': 'cda',
        '.ccda': 'ccda',
        # Images (OCR)
        '.png': 'image',
        '.jpg': 'image',
        '.jpeg': 'image',
        '.tiff': 'image',
        '.bmp': 'image',
    }
    
    def __init__(self):
        self._check_dependencies()
    
    def _check_dependencies(self):
        """Check which parsing libraries are available."""
        self.has_pdf = self._try_import('pypdf')
        self.has_docx = self._try_import('docx')
        self.has_pandas = self._try_import('pandas')
        self.has_ocr = self._try_import('pytesseract') and self._try_import('PIL')
        self.has_openpyxl = self._try_import('openpyxl')
        
    def _try_import(self, module: str) -> bool:
        try:
            __import__(module)
            return True
        except ImportError:
            return False
    
    def parse(self, file_path: str = None, file_bytes: bytes = None, 
              filename: str = None) -> ParsedDocument:
        """
        Parse a file from path or bytes.
        
        Args:
            file_path: Path to file
            file_bytes: File content as bytes
            filename: Original filename (needed for extension detection with bytes)
        """
        if file_path:
            path = Path(file_path)
            ext = path.suffix.lower()
            with open(path, 'rb') as f:
                content = f.read()
        elif file_bytes and filename:
            ext = Path(filename).suffix.lower()
            content = file_bytes
        else:
            raise ValueError("Provide file_path or (file_bytes + filename)")
        
        file_type = self.SUPPORTED_EXTENSIONS.get(ext, 'unknown')
        
        # Parse based on type
        parser_map = {
            'text': self._parse_text,
            'markdown': self._parse_text,
            'pdf': self._parse_pdf,
            'word': self._parse_docx,
            'csv': self._parse_csv,
            'excel': self._parse_excel,
            'json': self._parse_json,
            'xml': self._parse_xml,
            'hl7': self._parse_hl7,
            'fhir': self._parse_fhir,
            'image': self._parse_image,
        }
        
        parser = parser_map.get(file_type, self._parse_text)
        
        try:
            text, tables, metadata, confidence = parser(content, ext)
        except Exception as e:
            logger.warning(f"Parser failed for {file_type}, falling back to text: {e}")
            text = content.decode('utf-8', errors='ignore')
            tables = []
            metadata = {}
            confidence = 0.3
        
        return ParsedDocument(
            content=text,
            file_type=file_type,
            metadata=metadata,
            tables=tables,
            raw_text=text,
            confidence=confidence
        )
    
    def _parse_text(self, content: bytes, ext: str) -> Tuple[str, List, Dict, float]:
        """Parse plain text files."""
        text = content.decode('utf-8', errors='ignore')
        return text, [], {'encoding': 'utf-8'}, 1.0
    
    def _parse_pdf(self, content: bytes, ext: str) -> Tuple[str, List, Dict, float]:
        """Parse PDF files."""
        if not self.has_pdf:
            raise ImportError("pypdf not installed. Run: pip install pypdf")
        
        from pypdf import PdfReader
        
        reader = PdfReader(io.BytesIO(content))
        text_parts = []
        metadata = {}
        
        # Extract metadata
        if reader.metadata:
            metadata = {
                'title': reader.metadata.get('/Title', ''),
                'author': reader.metadata.get('/Author', ''),
                'pages': len(reader.pages)
            }
        
        # Extract text from each page
        for i, page in enumerate(reader.pages):
            page_text = page.extract_text() or ''
            text_parts.append(f"--- Page {i+1} ---\n{page_text}")
        
        return '\n\n'.join(text_parts), [], metadata, 0.9
    
    def _parse_docx(self, content: bytes, ext: str) -> Tuple[str, List, Dict, float]:
        """Parse Word documents."""
        if not self.has_docx:
            raise ImportError("python-docx not installed. Run: pip install python-docx")
        
        from docx import Document
        
        doc = Document(io.BytesIO(content))
        
        text_parts = []
        tables = []
        
        # Extract paragraphs
        for para in doc.paragraphs:
            if para.text.strip():
                text_parts.append(para.text)
        
        # Extract tables
        for table in doc.tables:
            table_data = []
            for row in table.rows:
                row_data = [cell.text for cell in row.cells]
                table_data.append(row_data)
            if table_data:
                tables.append({'data': table_data})
                # Also add table as text
                text_parts.append('\n'.join(['\t'.join(row) for row in table_data]))
        
        return '\n\n'.join(text_parts), tables, {}, 0.95
    
    def _parse_csv(self, content: bytes, ext: str) -> Tuple[str, List, Dict, float]:
        """Parse CSV files."""
        if not self.has_pandas:
            # Fallback to basic parsing
            text = content.decode('utf-8', errors='ignore')
            return text, [], {}, 0.7
        
        import pandas as pd
        
        df = pd.read_csv(io.BytesIO(content))
        
        # Convert to readable text
        text_parts = [f"CSV Data with {len(df)} rows and {len(df.columns)} columns:"]
        text_parts.append(f"Columns: {', '.join(df.columns.tolist())}")
        text_parts.append("\nSample data:")
        text_parts.append(df.head(20).to_string())
        
        # Full data as table
        tables = [{'columns': df.columns.tolist(), 'data': df.values.tolist()}]
        
        metadata = {
            'rows': len(df),
            'columns': len(df.columns),
            'column_names': df.columns.tolist()
        }
        
        return '\n'.join(text_parts), tables, metadata, 0.95
    
    def _parse_excel(self, content: bytes, ext: str) -> Tuple[str, List, Dict, float]:
        """Parse Excel files."""
        if not self.has_pandas or not self.has_openpyxl:
            raise ImportError("pandas and openpyxl required. Run: pip install pandas openpyxl")
        
        import pandas as pd
        
        # Read all sheets
        xlsx = pd.ExcelFile(io.BytesIO(content))
        
        text_parts = []
        tables = []
        total_rows = 0
        
        for sheet_name in xlsx.sheet_names:
            df = pd.read_excel(xlsx, sheet_name=sheet_name)
            total_rows += len(df)
            
            text_parts.append(f"\n=== Sheet: {sheet_name} ===")
            text_parts.append(f"Columns: {', '.join(df.columns.astype(str).tolist())}")
            text_parts.append(df.head(20).to_string())
            
            tables.append({
                'sheet': sheet_name,
                'columns': df.columns.tolist(),
                'data': df.values.tolist()
            })
        
        metadata = {
            'sheets': xlsx.sheet_names,
            'total_rows': total_rows
        }
        
        return '\n'.join(text_parts), tables, metadata, 0.95
    
    def _parse_json(self, content: bytes, ext: str) -> Tuple[str, List, Dict, float]:
        """Parse JSON files (including FHIR)."""
        data = json.loads(content.decode('utf-8'))
        
        # Check if it's FHIR
        if isinstance(data, dict) and 'resourceType' in data:
            return self._parse_fhir_json(data)
        
        # Pretty print JSON as text
        text = json.dumps(data, indent=2)
        
        # Try to flatten for readability
        if isinstance(data, dict):
            flat_text = self._flatten_json_to_text(data)
            text = f"{flat_text}\n\n--- Raw JSON ---\n{text}"
        
        return text, [], {'type': 'json'}, 0.9
    
    def _flatten_json_to_text(self, data: Dict, prefix: str = '') -> str:
        """Flatten nested JSON to readable text."""
        lines = []
        for key, value in data.items():
            full_key = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                lines.append(self._flatten_json_to_text(value, full_key))
            elif isinstance(value, list):
                if value and isinstance(value[0], dict):
                    for i, item in enumerate(value[:5]):  # Limit to first 5
                        lines.append(self._flatten_json_to_text(item, f"{full_key}[{i}]"))
                else:
                    lines.append(f"{full_key}: {', '.join(str(v) for v in value[:10])}")
            else:
                lines.append(f"{full_key}: {value}")
        return '\n'.join(lines)
    
    def _parse_xml(self, content: bytes, ext: str) -> Tuple[str, List, Dict, float]:
        """Parse XML files (including CDA/CCDA)."""
        import xml.etree.ElementTree as ET
        
        root = ET.fromstring(content)
        
        # Check if CDA/CCDA
        if 'ClinicalDocument' in root.tag:
            return self._parse_cda_xml(root)
        
        # Generic XML to text
        text_parts = []
        self._xml_to_text(root, text_parts)
        
        return '\n'.join(text_parts), [], {'root_tag': root.tag}, 0.85
    
    def _xml_to_text(self, element, text_parts: List, depth: int = 0):
        """Recursively convert XML to readable text."""
        indent = "  " * depth
        tag = element.tag.split('}')[-1]  # Remove namespace
        
        if element.text and element.text.strip():
            text_parts.append(f"{indent}{tag}: {element.text.strip()}")
        elif len(element) == 0:
            text_parts.append(f"{indent}{tag}: (empty)")
        else:
            text_parts.append(f"{indent}{tag}:")
        
        for child in element:
            self._xml_to_text(child, text_parts, depth + 1)
    
    def _parse_hl7(self, content: bytes, ext: str) -> Tuple[str, List, Dict, float]:
        """Parse HL7 v2.x messages."""
        text = content.decode('utf-8', errors='ignore')
        
        # Parse HL7 segments
        segments = text.strip().split('\r')
        if len(segments) == 1:
            segments = text.strip().split('\n')
        
        parsed_parts = ["=== HL7 Message ===\n"]
        metadata = {}
        
        for segment in segments:
            if not segment.strip():
                continue
            
            fields = segment.split('|')
            segment_type = fields[0]
            
            # Parse common segments
            if segment_type == 'MSH':
                metadata['message_type'] = fields[8] if len(fields) > 8 else 'Unknown'
                metadata['sending_app'] = fields[2] if len(fields) > 2 else ''
                parsed_parts.append(f"Message Type: {metadata['message_type']}")
                
            elif segment_type == 'PID':
                # Patient identification
                parsed_parts.append(f"\nPatient Information:")
                if len(fields) > 5:
                    name_parts = fields[5].split('^')
                    parsed_parts.append(f"  Name: {' '.join(name_parts[:2])}")
                if len(fields) > 7:
                    parsed_parts.append(f"  DOB: {fields[7]}")
                if len(fields) > 8:
                    parsed_parts.append(f"  Sex: {fields[8]}")
                if len(fields) > 11:
                    parsed_parts.append(f"  Address: {fields[11].replace('^', ' ')}")
                    
            elif segment_type == 'DG1':
                # Diagnosis
                parsed_parts.append(f"\nDiagnosis:")
                if len(fields) > 3:
                    parsed_parts.append(f"  Code: {fields[3].split('^')[0]}")
                if len(fields) > 4:
                    parsed_parts.append(f"  Description: {fields[4]}")
                    
            elif segment_type == 'OBX':
                # Observation/Result
                if len(fields) > 5:
                    obs_id = fields[3].split('^')[1] if '^' in fields[3] else fields[3]
                    value = fields[5]
                    unit = fields[6] if len(fields) > 6 else ''
                    parsed_parts.append(f"  {obs_id}: {value} {unit}")
            
            elif segment_type in ['AL1', 'RXA', 'OBR', 'PV1']:
                parsed_parts.append(f"\n{segment_type} Segment: {' | '.join(fields[1:5])}")
        
        return '\n'.join(parsed_parts), [], metadata, 0.9
    
    def _parse_fhir(self, content: bytes, ext: str) -> Tuple[str, List, Dict, float]:
        """Parse FHIR JSON resources."""
        data = json.loads(content.decode('utf-8'))
        return self._parse_fhir_json(data)
    
    def _parse_fhir_json(self, data: Dict) -> Tuple[str, List, Dict, float]:
        """Parse FHIR JSON resource."""
        resource_type = data.get('resourceType', 'Unknown')
        
        text_parts = [f"=== FHIR {resource_type} Resource ===\n"]
        
        if resource_type == 'Patient':
            name = data.get('name', [{}])[0]
            text_parts.append(f"Name: {name.get('given', [''])[0]} {name.get('family', '')}")
            text_parts.append(f"DOB: {data.get('birthDate', 'Unknown')}")
            text_parts.append(f"Gender: {data.get('gender', 'Unknown')}")
            
        elif resource_type == 'Condition':
            code = data.get('code', {}).get('coding', [{}])[0]
            text_parts.append(f"Condition: {code.get('display', 'Unknown')}")
            text_parts.append(f"Code: {code.get('code', '')} ({code.get('system', '')})")
            text_parts.append(f"Status: {data.get('clinicalStatus', {}).get('coding', [{}])[0].get('code', '')}")
            
        elif resource_type == 'MedicationRequest':
            med = data.get('medicationCodeableConcept', {}).get('coding', [{}])[0]
            text_parts.append(f"Medication: {med.get('display', 'Unknown')}")
            text_parts.append(f"Status: {data.get('status', 'Unknown')}")
            
        elif resource_type == 'Observation':
            code = data.get('code', {}).get('coding', [{}])[0]
            value = data.get('valueQuantity', {})
            text_parts.append(f"Observation: {code.get('display', 'Unknown')}")
            text_parts.append(f"Value: {value.get('value', '')} {value.get('unit', '')}")
            
        elif resource_type == 'Bundle':
            entries = data.get('entry', [])
            text_parts.append(f"Bundle with {len(entries)} entries:\n")
            for entry in entries[:10]:  # First 10 entries
                resource = entry.get('resource', {})
                text_parts.append(f"  - {resource.get('resourceType', 'Unknown')}")
        
        # Add raw JSON preview
        text_parts.append(f"\n--- Raw Resource ---\n{json.dumps(data, indent=2)[:2000]}")
        
        return '\n'.join(text_parts), [], {'resourceType': resource_type}, 0.95
    
    def _parse_cda_xml(self, root) -> Tuple[str, List, Dict, float]:
        """Parse CDA/CCDA clinical documents."""
        text_parts = ["=== Clinical Document (CDA) ===\n"]
        
        # Find namespaces
        ns = {'cda': 'urn:hl7-org:v3'}
        
        # Try to extract key sections
        try:
            # Document title
            title = root.find('.//cda:title', ns)
            if title is not None and title.text:
                text_parts.append(f"Title: {title.text}")
            
            # Patient info
            patient = root.find('.//cda:patient', ns)
            if patient is not None:
                name = patient.find('.//cda:name', ns)
                if name is not None:
                    given = name.find('cda:given', ns)
                    family = name.find('cda:family', ns)
                    if given is not None and family is not None:
                        text_parts.append(f"Patient: {given.text} {family.text}")
            
            # Sections
            for section in root.findall('.//cda:section', ns):
                title_elem = section.find('cda:title', ns)
                text_elem = section.find('cda:text', ns)
                
                if title_elem is not None:
                    text_parts.append(f"\n=== {title_elem.text} ===")
                
                if text_elem is not None:
                    # Extract all text content
                    section_text = ''.join(text_elem.itertext())
                    text_parts.append(section_text.strip())
                    
        except Exception as e:
            logger.warning(f"CDA parsing incomplete: {e}")
        
        return '\n'.join(text_parts), [], {'format': 'CDA'}, 0.85
    
    def _parse_image(self, content: bytes, ext: str) -> Tuple[str, List, Dict, float]:
        """Parse images using OCR."""
        if not self.has_ocr:
            raise ImportError("OCR requires pytesseract and Pillow. Run: pip install pytesseract Pillow")
        
        from PIL import Image
        import pytesseract
        
        image = Image.open(io.BytesIO(content))
        
        # Perform OCR
        text = pytesseract.image_to_string(image)
        
        metadata = {
            'size': image.size,
            'format': image.format,
            'mode': image.mode
        }
        
        return text, [], metadata, 0.7  # Lower confidence for OCR


# Singleton instance
_parser = None

def get_file_parser() -> UniversalFileParser:
    """Get singleton file parser instance."""
    global _parser
    if _parser is None:
        _parser = UniversalFileParser()
    return _parser
