#!/usr/bin/env python3
"""
Validate generated CDCT concepts using compression_validator.
Fixed to work with your existing validator structure.
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, 'src')

from compression_validator import validate_compression_protocol

def format_validation_report(filename: str, validation: dict) -> str:
    """Format validation results as readable report."""
    lines = []
    lines.append("=" * 60)
    lines.append(f"File: {filename}")
    lines.append("=" * 60)
    
    # Status
    status = "✅ VALID" if validation['valid'] else "❌ INVALID"
    lines.append(f"\nStatus: {status}\n")
    
    # Text lengths
    if 'text_lengths' in validation and validation['text_lengths']:
        lengths = validation['text_lengths']
        lines.append("Word counts per level:")
        for i, length in enumerate(lengths):
            lines.append(f"  Level {i}: {length} words")
        lines.append("")
    
    # Compression ratio
    if 'compression_ratio' in validation and validation['compression_ratio']:
        ratio = validation['compression_ratio']
        lines.append(f"Compression ratio: {ratio:.1f}x\n")
    
    # Errors
    if validation.get('errors'):
        lines.append("ERRORS:")
        for error in validation['errors']:
            lines.append(f"  ❌ {error}")
        lines.append("")
    
    # Warnings
    if validation.get('warnings'):
        lines.append("WARNINGS:")
        for warning in validation['warnings']:
            lines.append(f"  ⚠️  {warning}")
        lines.append("")
    
    lines.append("=" * 60)
    return "\n".join(lines)


def main():
    print("╔════════════════════════════════════════════════════════════════╗")
    print("║          CDCT Concept Validation                               ║")
    print("╚════════════════════════════════════════════════════════════════╝")
    print()
    
    # Find all concept files
    concept_files = sorted(Path("concepts").glob("*.json"))
    
    if not concept_files:
        print("❌ No concept files found in concepts/ directory")
        return 1
    
    print(f"Found {len(concept_files)} concept files")
    print()
    
    all_valid = True
    results = []
    
    for concept_file in concept_files:
        filename = concept_file.name
        
        try:
            with open(concept_file, 'r') as f:
                data = json.load(f)
            
            corpus = data.get('corpus', [])
            validation = validate_compression_protocol(corpus)
            
            # Print formatted report
            report = format_validation_report(filename, validation)
            print(report)
            print()
            
            results.append({
                'file': filename,
                'valid': validation['valid'],
                'errors': len(validation.get('errors', [])),
                'warnings': len(validation.get('warnings', []))
            })
            
            if not validation['valid']:
                all_valid = False
        
        except Exception as e:
            print(f"❌ Error loading {filename}: {e}")
            results.append({
                'file': filename,
                'valid': False,
                'errors': 1,
                'warnings': 0
            })
            all_valid = False
            print()
    
    # Summary
    print("╔════════════════════════════════════════════════════════════════╗")
    print("║                  VALIDATION SUMMARY                            ║")
    print("╚════════════════════════════════════════════════════════════════╝")
    print()
    
    valid_count = sum(1 for r in results if r['valid'])
    total_errors = sum(r['errors'] for r in results)
    total_warnings = sum(r['warnings'] for r in results)
    
    print(f"Total files:     {len(results)}")
    print(f"Valid:           {valid_count}")
    print(f"Invalid:         {len(results) - valid_count}")
    print(f"Total errors:    {total_errors}")
    print(f"Total warnings:  {total_warnings}")
    print()
    
    if all_valid:
        print("✅ All concepts passed validation!")
        print()
        print("Ready to run experiments:")
        print("  python main.py --concept concepts/physics_f_equals_ma.json \\")
        print("                 --model gpt-4.1 --deployment '4.1'")
        return 0
    else:
        print("❌ Some concepts failed validation.")
        print()
        print("To fix with LLM generation:")
        print("  python generate_8_concepts.py")
        return 1


if __name__ == "__main__":
    sys.exit(main())