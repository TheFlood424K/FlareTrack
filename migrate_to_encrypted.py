#!/usr/bin/env python3
"""Migration script to encrypt existing FlareTrack JSON data files.

This script will:
1. Find all unencrypted .json files in the data/logs directory
2. Create encrypted .enc versions using AES-256 encryption
3. Create backups of original files
4. Provide verification that encryption was successful

Usage:
    python migrate_to_encrypted.py [--data-dir PATH] [--no-backup]
    
Examples:
    # Migrate default data directory with backups
    python migrate_to_encrypted.py
    
    # Migrate custom directory without creating backups
    python migrate_to_encrypted.py --data-dir /path/to/data --no-backup
"""

import argparse
import sys
from pathlib import Path
from encryption import DataEncryption, DataMigration


def main():
    parser = argparse.ArgumentParser(
        description="Migrate FlareTrack JSON files to encrypted format"
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default="data/logs",
        help="Directory containing JSON log files (default: data/logs)"
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Skip creating backup files"
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify encryption integrity after migration"
    )
    
    args = parser.parse_args()
    
    # Convert to Path object
    data_dir = Path(args.data_dir)
    
    # Check if directory exists
    if not data_dir.exists():
        print(f"Error: Directory '{data_dir}' does not exist.")
        sys.exit(1)
    
    if not data_dir.is_dir():
        print(f"Error: '{data_dir}' is not a directory.")
        sys.exit(1)
    
    print("FlareTrack Data Migration Tool")
    print("=" * 50)
    print(f"Data directory: {data_dir.absolute()}")
    print(f"Create backups: {not args.no_backup}")
    print(f"Verify after migration: {args.verify}")
    print()
    
    # Initialize encryption and migration
    try:
        encryption = DataEncryption()
        migration = DataMigration(encryption)
    except Exception as e:
        print(f"Error initializing encryption: {e}")
        sys.exit(1)
    
    # Find JSON files to migrate
    json_files = list(data_dir.glob("*.json"))
    
    if not json_files:
        print(f"No .json files found in {data_dir}")
        print("Nothing to migrate.")
        return 0
    
    print(f"Found {len(json_files)} file(s) to migrate:")
    for f in json_files:
        print(f"  - {f.name}")
    print()
    
    # Confirm migration
    response = input("Proceed with migration? [y/N]: ")
    if response.lower() not in ['y', 'yes']:
        print("Migration cancelled.")
        return 0
    
    print()
    
    # Perform migration
    encrypted_files = migration.migrate_directory(
        data_dir,
        pattern="*.json",
        backup=not args.no_backup
    )
    
    # Verification
    if args.verify and encrypted_files:
        print("\nVerifying encrypted files...")
        failed = []
        for enc_file in encrypted_files:
            json_file = enc_file.with_suffix('.json')
            if json_file.exists():
                try:
                    if migration.verify_migration(json_file, enc_file):
                        print(f"  ✓ {enc_file.name} verified")
                    else:
                        print(f"  ✗ {enc_file.name} verification failed")
                        failed.append(enc_file)
                except Exception as e:
                    print(f"  ✗ {enc_file.name} error: {e}")
                    failed.append(enc_file)
        
        if failed:
            print(f"\nWarning: {len(failed)} file(s) failed verification")
            return 1
        else:
            print("\nAll files verified successfully!")
    
    print("\n" + "=" * 50)
    print("Migration complete!")
    print(f"Encrypted: {len(encrypted_files)} file(s)")
    print()
    print("Next steps:")
    print("1. Test loading data with the encrypted files")
    print("2. If everything works, you can delete the .json files")
    print("3. Keep .json.backup files as a safety measure")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
