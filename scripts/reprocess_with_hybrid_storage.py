#!/usr/bin/env python3
"""
Re-process data with Hybrid Architecture.

This script re-processes all Kaggle data to:
1. Store ORIGINAL (unmasked) data in on-prem SQLite database
2. Store MASKED data in cloud-ready Silver/Gold layers
3. Re-index the vector store with new record IDs

Security Architecture:
┌─────────────────────────────────────────────────────────────────────────┐
│  On-Prem Database                  Cloud (AI Processing)               │
│  (Hospital Network)                (Databricks/FAISS)                  │
│                                                                         │
│  ┌─────────────────┐              ┌─────────────────┐                 │
│  │ Original Data   │    UUID      │ Masked Data     │                 │
│  │ - John Smith    │◄────────────►│ - [MASKED_NAME] │                 │
│  │ - Dr. Johnson   │   record_id  │ - [MASKED_NAME] │                 │
│  │ - 555-1234      │              │ - [MASKED]      │                 │
│  └─────────────────┘              └─────────────────┘                 │
│         🔒                               ☁️                           │
└─────────────────────────────────────────────────────────────────────────┘

Usage:
    python scripts/reprocess_with_hybrid_storage.py
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.panel import Panel
from rich.table import Table


console = Console()


def main():
    console.print(Panel.fit(
        "[bold blue]🏥 Hybrid Data Architecture Processor[/bold blue]\n"
        "[dim]Re-processing data with On-Prem + Cloud split[/dim]",
        border_style="blue"
    ))
    
    # Step 1: Clear old processed data
    console.print("\n[bold yellow]Step 1:[/bold yellow] Clearing old processed data...")
    
    processed_dir = project_root / "data" / "processed"
    ai_ready_dir = project_root / "data" / "ai_ready"
    onprem_dir = project_root / "data" / "onprem"
    
    # Delete old files
    for dir_path in [processed_dir, ai_ready_dir]:
        if dir_path.exists():
            for f in dir_path.glob("*.json"):
                f.unlink()
                console.print(f"  [dim]Deleted: {f.name}[/dim]")
    
    # Delete old on-prem database
    old_db = onprem_dir / "patient_records.db"
    if old_db.exists():
        old_db.unlink()
        console.print(f"  [dim]Deleted old on-prem DB[/dim]")
    
    console.print("[green]✓ Old data cleared[/green]")
    
    # Step 2: Reset dataset metadata to allow re-processing
    console.print("\n[bold yellow]Step 2:[/bold yellow] Resetting dataset metadata...")
    
    kaggle_dir = project_root / "data" / "raw" / "kaggle"
    if kaggle_dir.exists():
        for metadata_file in kaggle_dir.glob("*/_metadata.json"):
            import json
            with open(metadata_file) as f:
                metadata = json.load(f)
            metadata["processed"] = False
            with open(metadata_file, "w") as f:
                json.dump(metadata, f, indent=2)
            console.print(f"  [dim]Reset: {metadata_file.parent.name}[/dim]")
    
    console.print("[green]✓ Metadata reset[/green]")
    
    # Step 3: Re-process with hybrid storage
    console.print("\n[bold yellow]Step 3:[/bold yellow] Processing with hybrid architecture...")
    
    from src.data.processor import get_processor
    from src.data.onprem_db import get_onprem_db
    
    processor = get_processor()
    result = processor.process_all()
    
    if result["success"]:
        console.print(f"[green]✓ Processed {result['datasets_processed']} datasets[/green]")
        
        # Show details
        for r in result.get("results", []):
            if r.get("success"):
                console.print(f"  [cyan]{r['file']}[/cyan]: "
                            f"{r.get('original_records', 0)} records → "
                            f"{r.get('onprem_records_stored', 0)} in on-prem, "
                            f"{r.get('gold_documents', 0)} gold docs")
    else:
        console.print(f"[red]✗ Processing failed: {result.get('message')}[/red]")
        return False
    
    # Step 4: Check on-prem database stats
    console.print("\n[bold yellow]Step 4:[/bold yellow] On-Prem Database Status...")
    
    db = get_onprem_db()
    stats = db.get_stats()
    
    table = Table(title="On-Prem Database (Original Data)", show_header=True)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    
    table.add_row("Total Records", str(stats.get("total_records", 0)))
    table.add_row("Database Path", stats.get("database_path", "N/A"))
    table.add_row("Database Size", f"{stats.get('database_size_mb', 0)} MB")
    
    console.print(table)
    
    # Step 5: Re-index vector store
    console.print("\n[bold yellow]Step 5:[/bold yellow] Re-indexing vector store with new record IDs...")
    
    # Clear old index
    index_path = project_root / "data" / "vector_store"
    if index_path.exists():
        import shutil
        shutil.rmtree(index_path)
        console.print("  [dim]Cleared old vector index[/dim]")
    
    from src.rag.pipeline import RAGPipeline
    
    # Create fresh pipeline
    pipeline = RAGPipeline(
        data_dir=str(ai_ready_dir),
        index_path=str(index_path),
    )
    
    # Index new data
    indexed = pipeline.index_documents()
    console.print(f"[green]✓ Indexed {indexed['chunks_indexed']} chunks from {indexed['documents_processed']} documents[/green]")
    
    # Final summary
    console.print("\n" + "="*60)
    console.print(Panel.fit(
        "[bold green]✓ Hybrid Architecture Setup Complete![/bold green]\n\n"
        f"[cyan]On-Prem DB:[/cyan] {stats.get('total_records', 0)} original records\n"
        f"[cyan]Cloud (FAISS):[/cyan] {indexed['chunks_indexed']} masked chunks\n\n"
        "[dim]Original patient data stays on-prem.\n"
        "Only masked data is sent to cloud/AI.[/dim]",
        border_style="green"
    ))
    
    # Test: Verify we can link masked → original
    console.print("\n[bold yellow]Verification:[/bold yellow] Testing record linkage...")
    
    # Get a sample record ID from processed data
    sample_gold = list(ai_ready_dir.glob("*.json"))
    if sample_gold:
        import json
        with open(sample_gold[0]) as f:
            gold_data = json.load(f)
        
        if gold_data.get("documents"):
            sample_doc = gold_data["documents"][0]
            sample_id = sample_doc.get("id")
            
            if sample_id:
                # Try to get original
                original = db.get_original_record(sample_id, "test", "verification")
                if original:
                    console.print(f"[green]✓ Record linkage works![/green]")
                    console.print(f"  Masked ID: [cyan]{sample_id}[/cyan]")
                    console.print(f"  Original Patient: [cyan]{original.get('patient_name', 'N/A')}[/cyan]")
                    console.print(f"  Original Doctor: [cyan]{original.get('doctor_name', 'N/A')}[/cyan]")
                else:
                    console.print("[yellow]⚠ Could not verify record linkage[/yellow]")
    
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
