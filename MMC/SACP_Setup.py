import os
import shutil
from pathlib import Path
import logging
import argparse
import math

class SACPCreator:
    """
    Creates SACP directory structure and collects ligand files from the original library.
    """
    
    def __init__(self, library_path: str, sacp_path: str, split: int = 1):
        """
        Initialize the SACP creator.
        
        Args:
            library_path (str): Path to the original library parent directory
            sacp_path (str): Path where the SACP directory should be created
            split (int): Number of SACP directories to create (default: 1)
        """
        self.library_path = Path(library_path)
        self.sacp_base = Path(sacp_path)
        self.split = max(1, split)  # Ensure at least 1 split
        self.sacp_dirs = []
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
        # Validate paths
        if not self.library_path.exists():
            raise FileNotFoundError(f"Library path does not exist: {library_path}")
            
        # Create SACP directory paths
        if self.split == 1:
            self.sacp_dirs = [self.sacp_base / 'SACP']
        else:
            self.sacp_dirs = [self.sacp_base / f'SACP_{i+1}' for i in range(self.split)]
        
    def get_molecule_directories(self):
        """
        Find all molecule directories in the original library.
        
        Returns:
            list: List of molecule directory paths
        """
        return [d for d in self.library_path.iterdir() 
                if d.is_dir() and d.name != 'File_Prep']
    
    def find_ligand_files(self, molecule_dir):
        """
        Find lig.top and lig.slv files in the molecule's AMBER directory.
        
        Args:
            molecule_dir (Path): Path to molecule directory
            
        Returns:
            tuple: Paths to lig.top and lig.slv files, or (None, None) if not found
        """
        amber_dir = molecule_dir / 'RESP' / 'AMBER'
        if not amber_dir.exists():
            self.logger.warning(f"AMBER directory not found for {molecule_dir.name}")
            return None, None
            
        lig_top = amber_dir / 'lig.top'
        lig_slv = amber_dir / 'lig.slv'
        
        if not lig_top.exists() or not lig_slv.exists():
            self.logger.warning(f"Missing ligand files for {molecule_dir.name}")
            return None, None
            
        return lig_top, lig_slv
    
    def create_sacp_structure(self):
        """
        Create the SACP directory structure and copy ligand files.
        """
        try:
            # Create all SACP directories
            for sacp_dir in self.sacp_dirs:
                sacp_dir.mkdir(parents=True, exist_ok=True)
                self.logger.info(f"Created SACP directory: {sacp_dir}")
            
            # Get all molecule directories
            mol_dirs = self.get_molecule_directories()
            
            # Calculate molecules per directory
            total_mols = len(mol_dirs)
            mols_per_dir = math.ceil(total_mols / self.split)
            
            # Process each molecule directory
            successful_copies = 0
            for idx, mol_dir in enumerate(mol_dirs):
                # Determine which SACP directory to use
                sacp_idx = min(idx // mols_per_dir, self.split - 1)
                target_sacp_dir = self.sacp_dirs[sacp_idx]
                
                mol_name = mol_dir.name
                new_mol_dir = target_sacp_dir / mol_name
                
                # Find ligand files
                lig_top, lig_slv = self.find_ligand_files(mol_dir)
                if lig_top is None or lig_slv is None:
                    continue
                
                # Create molecule directory in SACP and copy files
                new_mol_dir.mkdir(exist_ok=True)
                shutil.copy2(lig_top, new_mol_dir / 'lig.top')
                shutil.copy2(lig_slv, new_mol_dir / 'lig.slv')
                
                successful_copies += 1
                self.logger.info(f"Copied ligand files for {mol_name} to {target_sacp_dir.name}")
            
            self.logger.info(f"Successfully processed {successful_copies} molecules across {self.split} directories")
            
        except Exception as e:
            self.logger.error(f"Error during SACP creation: {str(e)}")
            raise
            
    def verify_sacp_structure(self):
        """
        Verify that all files were copied correctly.
        
        Returns:
            bool: True if verification passed, False otherwise
        """
        try:
            all_correct = True
            total_molecules = 0
            
            for sacp_dir in self.sacp_dirs:
                molecule_count = 0
                
                for mol_dir in sacp_dir.iterdir():
                    if not mol_dir.is_dir():
                        continue
                        
                    molecule_count += 1
                    lig_top = mol_dir / 'lig.top'
                    lig_slv = mol_dir / 'lig.slv'
                    
                    if not lig_top.exists() or not lig_slv.exists():
                        self.logger.error(f"Missing files in {sacp_dir.name}/{mol_dir.name}")
                        all_correct = False
                
                total_molecules += molecule_count
                self.logger.info(f"Molecules in {sacp_dir.name}: {molecule_count}")
            
            self.logger.info(f"Total molecules across all SACP directories: {total_molecules}")
            return all_correct
            
        except Exception as e:
            self.logger.error(f"Error during verification: {str(e)}")
            return False

def parse_arguments():
    """
    Parse command line arguments.
    
    Returns:
        argparse.Namespace: Parsed command line arguments
    """
    parser = argparse.ArgumentParser(
        description='Create SACP directory structure and copy ligand files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent('''
            Example usage:
                python create_sacp.py --library_path /path/to/library --sacp_path /path/for/output --split 3
                
            The script will:
            1. Read molecule directories from the library path
            2. Create specified number of SACP directories at the output path
            3. Distribute and copy lig.top and lig.slv files across SACP directories
        ''')
    )
    
    parser.add_argument(
        '--library_path',
        type=str,
        required=True,
        help='Path to the original library parent directory'
    )
    
    parser.add_argument(
        '--sacp_path',
        type=str,
        required=True,
        help='Path where the SACP directory should be created'
    )
    
    parser.add_argument(
        '--split',
        type=int,
        default=1,
        help='Number of SACP directories to create (default: 1)'
    )
    
    return parser.parse_args()

def main():
    """Main function to run the SACP creation process."""
    # Parse command line arguments
    args = parse_arguments()
    
    try:
        # Initialize the SACP creator
        creator = SACPCreator(
            library_path=args.library_path,
            sacp_path=args.sacp_path,
            split=args.split
        )
        
        # Create the SACP structure and copy files
        creator.create_sacp_structure()
        
        # Verify the structure
        if creator.verify_sacp_structure():
            print("SACP creation completed and verified successfully")
        else:
            print("SACP creation completed with errors, please check the logs")
            
    except Exception as e:
        print(f"Error: {str(e)}")
        return 1
        
    return 0

if __name__ == "__main__":
    import textwrap
    import sys
    sys.exit(main())
