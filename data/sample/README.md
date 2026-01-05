# Kaggle Data Directory

This directory contains clinical data downloaded from Kaggle.

## Quick Setup

```bash
# 1. Install kaggle CLI
pip install kaggle

# 2. Setup Kaggle API credentials
# Go to kaggle.com -> Account -> Create New API Token
# Save kaggle.json to ~/.kaggle/kaggle.json
mkdir -p ~/.kaggle
mv ~/Downloads/kaggle.json ~/.kaggle/
chmod 600 ~/.kaggle/kaggle.json

# 3. Download datasets
python scripts/download_kaggle_data.py --dataset healthcare
```

## Available Datasets

| Dataset | Command | Description |
|---------|---------|-------------|
| Healthcare Dataset | `--dataset healthcare` | Patient records with conditions, medications (882 Gold) |
| Clinical Notes | `--dataset clinical-notes` | Direct clinical text documentation |
| Diabetes | `--dataset diabetes` | Diabetes indicators and outcomes |
| NBME Clinical | `--dataset nbme-clinical` | Competition clinical patient notes |

## Recommended Dataset

For this project, we recommend:

```bash
python scripts/download_kaggle_data.py --dataset healthcare
```

This dataset includes:
- Patient demographics
- Medical conditions (including diabetes)
- Medications
- Hospital admissions
- Test results

## After Download

The script converts Kaggle data to clinical notes format in `data/sample/`.
Then ingest via API:

```bash
curl -X POST http://localhost:8000/documents/ingest-sample
```

## Privacy Note

Even though Kaggle data is synthetic/public, we still apply PII masking
to demonstrate proper healthcare data handling practices.
