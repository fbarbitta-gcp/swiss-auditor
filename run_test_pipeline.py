#!/usr/bin/env python3
import asyncio
import os
import sys
import logging

"""
Utility script to test the Swiss Auditor pipeline locally.

Usage:
    Running with default CAMERA_test data:
    python3 run_test_pipeline.py

    Running with specific files:
    python3 run_test_pipeline.py <invoice_path> <clinical_path_1> [<clinical_path_2> ...]
"""

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from agents.pipeline import run_pipeline

async def main():
    # Use defaults if no arguments provided
    if len(sys.argv) == 1:
        invoice = "data/CAMERA_test/rendicion camera.pdf"
        clinical = ["data/CAMERA_test/HPR HCs para IA_CAMERA CARINA_CAMERA CARINA MARIEL-HIN66675_18.pdf"]
        output_dir = "data/CAMERA_test_output"
    elif len(sys.argv) >= 3:
        invoice = sys.argv[1]
        clinical = sys.argv[2:]
        output_dir = os.path.dirname(invoice) if os.path.dirname(invoice) else "output"
    else:
        print("Usage: python3 run_test_pipeline.py [<invoice_path> <clinical_path_1> ...]")
        return

    if not os.path.exists(invoice):
        print(f"Invoice file not found: {invoice}")
        print("Please ensure the path is correct or run without arguments to use CAMERA_test defaults.")
        return

    print(f"Running pipeline with invoice: {invoice}")
    print(f"Clinical records: {clinical}")
    print(f"Output directory: {output_dir}")
    
    os.makedirs(output_dir, exist_ok=True)
    
    try:
        await run_pipeline(invoice_path=invoice, clinical_paths=clinical, output_dir=output_dir)
        print("\n[SUCCESS] Pipeline execution completed successfully!")
        print(f"Check results in: {output_dir}")
    except Exception as e:
        print(f"\n[FAILURE] Pipeline finished with error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
