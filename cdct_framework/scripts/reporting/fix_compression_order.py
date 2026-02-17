#!/usr/bin/env python3
"""
Fix compression level ordering in existing CDCT concept files.

Your current JSONs have:
  Level 0 = Full text (WRONG)
  Level 4 = Minimal text (WRONG)

Paper requires:
  Level 0 = Minimal text (1-3 words) - MOST COMPRESSED
  Level 4 = Full text (100+ words) - LEAST COMPRESSED

This script reverses the corpus array and updates compression_level values.
"""

import json
import glob
from pathlib import Path
import shutil
from datetime import datetime

def fix_concept_file(input_path: str, output_path: str = None) -> dict:
    """
    Reverses compression levels in a concept JSON file.
    
    Args:
        input_path: Path to input JSON
        output_path: Path to save fixed JSON (default: overwrite input)
    
    Returns:
        Fixed concept data
    """
    with open(input_path, 'r') as f:
        data = json.load(f)
    
    # Extract corpus
    corpus = data.get('corpus', [])
    
    if not corpus:
        print(f"  ⚠️  Empty corpus in {input_path}")
        return data
    
    # Reverse the order of corpus entries
    reversed_corpus = list(reversed(corpus))
    
    # Update compression_level values to match new order
    for i, entry in enumerate(reversed_corpus):
        entry['compression_level'] = i
    
    # Update data
    data['corpus'] = reversed_corpus
    
    # Save
    if output_path is None:
        output_path = input_path
    
    with open(output_path, 'w') as f:
        json.dump(data, f, indent=2)
    
    return data


def main():
    print("╔════════════════════════════════════════════════════════════════╗")
    print("║     CDCT Compression Level Order Fix                          ║")
    print("║     Converts: Level 0=Full → Level 0=Minimal (Paper Correct) ║")
    print("╚════════════════════════════════════════════════════════════════╝")
    print()
    
    # Find all concept files
    concept_files = glob.glob("concepts/*.json")
    
    if not concept_files:
        print("❌ No concept files found in concepts/ directory")
        return
    
    print(f"Found {len(concept_files)} concept files")
    print()
    
    # Create backup
    backup_dir = f"concepts_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    Path(backup_dir).mkdir(exist_ok=True)
    
    print(f"📦 Creating backup in: {backup_dir}/")
    for f in concept_files:
        shutil.copy(f, backup_dir)
    print("✓ Backup complete")
    print()
    
    # Process each file
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("Processing files...")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    
    for concept_file in concept_files:
        filename = Path(concept_file).name
        print(f"\n{filename}")
        
        # Load original
        with open(concept_file, 'r') as f:
            original = json.load(f)
        
        original_corpus = original.get('corpus', [])
        if len(original_corpus) != 5:
            print(f"  ⚠️  Expected 5 levels, found {len(original_corpus)}")
        
        # Show before
        print("  Before:")
        for i, entry in enumerate(original_corpus):
            text_preview = entry['text'][:50] + "..." if len(entry['text']) > 50 else entry['text']
            word_count = len(entry['text'].split())
            print(f"    L{i}: {word_count:3d} words - {text_preview}")
        
        # Fix
        fixed = fix_concept_file(concept_file)
        
        # Show after
        print("  After:")
        for i, entry in enumerate(fixed['corpus']):
            text_preview = entry['text'][:50] + "..." if len(entry['text']) > 50 else entry['text']
            word_count = len(entry['text'].split())
            print(f"    L{i}: {word_count:3d} words - {text_preview}")
        
        # Validate monotonic increase
        word_counts = [len(e['text'].split()) for e in fixed['corpus']]
        is_monotonic = all(word_counts[i] <= word_counts[i+1] for i in range(len(word_counts)-1))
        
        if is_monotonic:
            print("  ✅ Monotonic word count increase verified")
        else:
            print("  ⚠️  Warning: Word counts not strictly monotonic")
    
    print()
    print("╔════════════════════════════════════════════════════════════════╗")
    print("║                    FIX COMPLETE                                ║")
    print("╚════════════════════════════════════════════════════════════════╝")
    print()
    print(f"✓ Processed {len(concept_files)} files")
    print(f"✓ Backup saved to: {backup_dir}/")
    print()
    print("Next steps:")
    print("  1. Validate: bash validate_all_concepts.sh")
    print("  2. Rerun experiments with corrected compression order")
    print()


if __name__ == "__main__":
    main()
