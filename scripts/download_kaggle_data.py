#!/usr/bin/env python3
"""
Kaggle Data Downloader for Medical Assistant.

Downloads raw clinical/healthcare datasets from Kaggle and stores them
in the raw data directory. Processing and masking is done separately
by the data processing pipeline.

DATA FLOW:
    Kaggle → data/raw/ (Bronze) → Processing API → data/processed/ (Silver)

SETUP:
1. Install kaggle: pip install kaggle
2. Create Kaggle API credentials:
   - Go to kaggle.com -> Account -> Create New API Token
   - Save kaggle.json to ~/.kaggle/kaggle.json
   - chmod 600 ~/.kaggle/kaggle.json

USAGE:
    # List available datasets
    python scripts/download_kaggle_data.py --list
    
    # Download a specific dataset
    python scripts/download_kaggle_data.py --dataset healthcare
    
    # Download all available datasets
    python scripts/download_kaggle_data.py --dataset all
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime

# Available datasets with metadata
DATASETS = {
    "healthcare": {
        "kaggle_id": "prasad22/healthcare-dataset",
        "description": "Healthcare Dataset with patient records (882 Gold)",
        "type": "structured",
        "contains_pii": True,
        "fields": ["Name", "Age", "Gender", "Blood Type", "Medical Condition", 
                   "Medication", "Doctor", "Hospital", "Insurance Provider",
                   "Admission Type", "Date of Admission", "Discharge Date",
                   "Test Results", "Billing Amount"],
    },
    "clinical-notes": {
        "kaggle_id": "akashadesai/clinical-notes",
        "description": "Clinical Notes with medical documentation",
        "type": "text",
        "contains_pii": True,
        "fields": ["clinical_note", "patient_id"],
    },
    "diabetes": {
        "kaggle_id": "hasibur013/diabetes-dataset",
        "description": "Diabetes indicators dataset (Pima Indians)",
        "type": "structured",
        "contains_pii": False,
        "fields": ["Pregnancies", "Glucose", "BloodPressure", "SkinThickness",
                   "Insulin", "BMI", "DiabetesPedigreeFunction", "Age", "Outcome"],
    },
    "diabetes-health": {
        "kaggle_id": "mohankrishnathalla/diabetes-health-indicators-dataset",
        "description": "Diabetes Health Indicators (BRFSS 2015)",
        "type": "structured", 
        "contains_pii": False,
        "fields": ["Diabetes_012", "HighBP", "HighChol", "BMI", "Smoker",
                   "HeartDiseaseorAttack", "PhysActivity", "HvyAlcoholConsump"],
    },
    "nbme-clinical": {
        "kaggle_id": "algerwang/nbme-score-clinical-patient-notes",
        "description": "NBME Clinical Patient Notes (competition)",
        "type": "text",
        "contains_pii": True,
        "fields": ["pn_history", "pn_num", "case_num"],
    },
    "heart-failure": {
        "kaggle_id": "aadarshvelu/heart-failure-prediction-clinical-records",
        "description": "Heart Failure Clinical Records (95 Silver)",
        "type": "structured",
        "contains_pii": False,
        "fields": ["age", "anaemia", "creatinine_phosphokinase", "diabetes",
                   "ejection_fraction", "high_blood_pressure", "platelets",
                   "serum_creatinine", "serum_sodium", "sex", "smoking", "time"],
    },
}


def check_kaggle_setup() -> bool:
    """Check if Kaggle API is properly configured."""
    kaggle_json = Path.home() / ".kaggle" / "kaggle.json"
    
    if not kaggle_json.exists():
        print("=" * 60)
        print("ERROR: Kaggle API not configured!")
        print("=" * 60)
        print("\nSetup instructions:")
        print("1. Go to https://www.kaggle.com/settings")
        print("2. Scroll to 'API' section")
        print("3. Click 'Create New Token'")
        print("4. Save the downloaded kaggle.json:")
        print("   mkdir -p ~/.kaggle")
        print("   mv ~/Downloads/kaggle.json ~/.kaggle/")
        print("   chmod 600 ~/.kaggle/kaggle.json")
        return False
    
    try:
        import kaggle
        return True
    except ImportError:
        print("Installing kaggle package...")
        subprocess.run([sys.executable, "-m", "pip", "install", "kaggle"], check=True)
        return True


def download_dataset(dataset_key: str, output_dir: Path) -> dict | None:
    """
    Download a dataset from Kaggle to the raw data directory.
    
    Returns metadata about the download.
    """
    if dataset_key not in DATASETS:
        print(f"Unknown dataset: {dataset_key}")
        print(f"Available: {', '.join(DATASETS.keys())}")
        return None
    
    dataset = DATASETS[dataset_key]
    kaggle_id = dataset["kaggle_id"]
    
    print(f"\n{'='*60}")
    print(f"Downloading: {dataset['description']}")
    print(f"Kaggle ID: {kaggle_id}")
    print(f"Type: {dataset['type']}")
    print(f"Contains PII patterns: {dataset['contains_pii']}")
    print("=" * 60)
    
    # Create output directory
    dataset_dir = output_dir / dataset_key
    dataset_dir.mkdir(parents=True, exist_ok=True)
    
    # Download using Kaggle CLI
    cmd = [
        "kaggle", "datasets", "download",
        "-d", kaggle_id,
        "-p", str(dataset_dir),
        "--unzip"
    ]
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(f"✓ Downloaded to: {dataset_dir}")
        
        # List downloaded files
        files = list(dataset_dir.glob("*"))
        print(f"  Files: {[f.name for f in files]}")
        
        # Create metadata file
        metadata = {
            "dataset_key": dataset_key,
            "kaggle_id": kaggle_id,
            "description": dataset["description"],
            "type": dataset["type"],
            "contains_pii": dataset["contains_pii"],
            "expected_fields": dataset["fields"],
            "downloaded_at": datetime.now().isoformat(),
            "files": [f.name for f in files],
            "status": "raw",
            "processed": False,
        }
        
        metadata_path = dataset_dir / "_metadata.json"
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)
        
        return metadata
        
    except subprocess.CalledProcessError as e:
        print(f"✗ Download failed: {e}")
        print(f"  stderr: {e.stderr}")
        return None


def list_datasets():
    """Print available datasets."""
    print("\n" + "=" * 70)
    print("AVAILABLE KAGGLE DATASETS")
    print("=" * 70)
    
    for key, info in DATASETS.items():
        pii_marker = "⚠️  PII" if info["contains_pii"] else "✓ No PII"
        print(f"\n  {key}")
        print(f"    Description: {info['description']}")
        print(f"    Type: {info['type']}")
        print(f"    Status: {pii_marker}")
        print(f"    Fields: {', '.join(info['fields'][:5])}{'...' if len(info['fields']) > 5 else ''}")
    
    print("\n" + "=" * 70)
    print("USAGE:")
    print("  python scripts/download_kaggle_data.py --dataset <name>")
    print("  python scripts/download_kaggle_data.py --dataset all")
    print("=" * 70)


def check_existing_downloads(raw_dir: Path):
    """Check what's already downloaded."""
    print("\n" + "=" * 60)
    print("EXISTING RAW DATA")
    print("=" * 60)
    
    if not raw_dir.exists():
        print("  No raw data directory yet.")
        return
    
    for dataset_dir in raw_dir.iterdir():
        if not dataset_dir.is_dir():
            continue
        
        metadata_path = dataset_dir / "_metadata.json"
        if metadata_path.exists():
            with open(metadata_path) as f:
                meta = json.load(f)
            status = "✓ Processed" if meta.get("processed") else "○ Not processed"
            print(f"  {dataset_dir.name}: {status}")
            print(f"    Downloaded: {meta.get('downloaded_at', 'Unknown')}")
        else:
            files = list(dataset_dir.glob("*"))
            print(f"  {dataset_dir.name}: {len(files)} files (no metadata)")


def main():
    parser = argparse.ArgumentParser(
        description="Download Kaggle datasets for Medical Assistant"
    )
    parser.add_argument(
        "--dataset",
        choices=list(DATASETS.keys()) + ["all"],
        help="Dataset to download"
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available datasets"
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show status of downloaded data"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/raw/kaggle"),
        help="Output directory for raw downloads (default: data/raw/kaggle)"
    )
    
    args = parser.parse_args()
    
    # Default action: list datasets
    if args.list or (not args.dataset and not args.status):
        list_datasets()
        return
    
    if args.status:
        check_existing_downloads(args.output_dir)
        return
    
    # Check Kaggle setup
    if not check_kaggle_setup():
        return
    
    # Determine which datasets to download
    if args.dataset == "all":
        datasets_to_download = list(DATASETS.keys())
    else:
        datasets_to_download = [args.dataset]
    
    # Download each dataset
    results = []
    for dataset_key in datasets_to_download:
        result = download_dataset(dataset_key, args.output_dir)
        if result:
            results.append(result)
    
    # Summary
    print("\n" + "=" * 60)
    print("DOWNLOAD SUMMARY")
    print("=" * 60)
    print(f"  Downloaded: {len(results)} / {len(datasets_to_download)} datasets")
    print(f"  Location: {args.output_dir}")
    
    print("\n" + "=" * 60)
    print("NEXT STEPS")
    print("=" * 60)
    print("  1. Start the server:")
    print("     python -m src.main")
    print("")
    print("  2. Process raw data (applies masking):")
    print("     curl -X POST http://localhost:8000/data/process")
    print("")
    print("  3. Check processing status:")
    print("     curl http://localhost:8000/data/status")
    print("")
    print("  4. Query the data:")
    print("     curl -X POST http://localhost:8000/query/extract \\")
    print('       -H "Content-Type: application/json" \\')
    print('       -d \'{"query": "diabetes medications"}\'')


if __name__ == "__main__":
    main()
