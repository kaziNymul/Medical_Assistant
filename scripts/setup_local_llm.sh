#!/bin/bash
# ===========================================
# Setup Local LLM for Clinical Data Extraction
# ===========================================
# This script installs dependencies and downloads the FLAN-T5 model

set -e

echo "================================================"
echo "  Setting up Local LLM Extraction (FLAN-T5)"
echo "================================================"

# Create model cache directory
MODEL_DIR="/mnt/e/medical_assistant/models"
mkdir -p "$MODEL_DIR"
echo "✓ Model cache directory: $MODEL_DIR"

# Install PyTorch (CPU version for your system)
echo ""
echo "Installing PyTorch (CPU version)..."
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu

# Install Transformers and dependencies
echo ""
echo "Installing Transformers..."
pip install transformers sentencepiece

# Install file parsing libraries
echo ""
echo "Installing file parsers..."
pip install pypdf python-docx openpyxl pandas

# Download the model
echo ""
echo "Downloading FLAN-T5 Base model (~250MB)..."
echo "This will take 1-3 minutes depending on your connection..."
cd /mnt/e/medical_assistant
python -c "
from transformers import T5Tokenizer, T5ForConditionalGeneration
import os

cache_dir = '$MODEL_DIR'
model_name = 'google/flan-t5-base'

print('Downloading tokenizer...')
T5Tokenizer.from_pretrained(model_name, cache_dir=cache_dir)

print('Downloading model...')
T5ForConditionalGeneration.from_pretrained(model_name, cache_dir=cache_dir)

print('✅ Model downloaded successfully!')
"

echo ""
echo "================================================"
echo "  Setup Complete!"
echo "================================================"
echo ""
echo "Model: google/flan-t5-base"
echo "Cache: $MODEL_DIR"
echo "RAM Required: ~2GB during extraction"
echo "Expected extraction time: 5-15 seconds per document"
echo ""
echo "To test the extraction:"
echo "  python -c \"from src.extraction.llm_extractor import get_extractor; e = get_extractor(); print('Ready!')\""
echo ""
