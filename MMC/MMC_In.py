import os
from pathlib import Path
import argparse
import logging
import shutil
import re
from datetime import datetime

class SACPProcessor:
    def __init__(self, sacp_path: str, template_path: str, protein_path: str = None):
        self.sacp_dir = Path(sacp_path)
        self.template_path = Path(template_path)
        self.protein_path = Path(protein_path) if protein_path else None
        
        # Create logs directory if it doesn't exist
        self.logs_dir = Path('logs')
        self.logs_dir.mkdir(exist_ok=True)
        
        # Create log filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_file = self.logs_dir / f'sacp_processing_{timestamp}.log'
        
        # Setup logging to both file and console
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
        # Log the start of processing
        self.logger.info("="*50)
        self.logger.info("Starting SACP processing")
        self.logger.info(f"Log file: {log_file}")
        self.logger.info("="*50)
        
        # Validate paths
        if not self.sacp_dir.exists():
            raise FileNotFoundError(f"SACP directory not found: {sacp_path}")
        if not self.template_path.exists():
            raise FileNotFoundError(f"Template file not found: {template_path}")
        if self.protein_path and not self.protein_path.exists():
            raise FileNotFoundError(f"Protein directory not found: {protein_path}")
            
        # If we find a nested SACP directory, use that instead
        nested_sacp = self.sacp_dir / 'SACP'
        if nested_sacp.exists() and nested_sacp.is_dir():
            self.sacp_dir = nested_sacp
            
        self.logger.info(f"Processing SACP directory: {self.sacp_dir}")
        
    def copy_protein_files(self, molecule_dir: Path):
        """
        Copy all files from protein directory to molecule directory.
        
        Args:
            molecule_dir (Path): Path to molecule directory
        """
        if not self.protein_path:
            return
            
        try:
            self.logger.info(f"Copying protein files to {molecule_dir.name}")
            for item in self.protein_path.iterdir():
                if item.is_file() and not item.name.startswith('.'):
                    dest = molecule_dir / item.name
                    shutil.copy2(item, dest)
                    self.logger.info(f"Copied {item.name} to {molecule_dir.name}")
                    
        except Exception as e:
            self.logger.error(f"Error copying protein files to {molecule_dir.name}: {str(e)}")
            
    def get_molecule_directories(self):
        """Find all molecule directories in SACP that contain lig.slv."""
        molecule_dirs = []
        self.logger.info("Contents of SACP directory:")
        for item in self.sacp_dir.iterdir():
            if not item.name.startswith('.'):
                self.logger.info(f"Found: {item}")
                if item.is_dir():
                    slv_file = item / 'lig.slv'
                    if slv_file.exists():
                        molecule_dirs.append(item)
                        self.logger.info(f"Found valid molecule directory: {item.name}")
        return molecule_dirs
            
    def parse_slv_file(self, slv_path: Path):
        """Count atoms in lig.slv file."""
        try:
            with open(slv_path, 'r') as f:
                atoms = sum(1 for line in f if line.strip())
            self.logger.info(f"Counted {atoms} atoms in {slv_path}")
            return atoms
        except Exception as e:
            self.logger.error(f"Error reading {slv_path}: {str(e)}")
            return None
            
    def update_template(self, template_content: str, atom_count: int):
        """Update only the atom count in SLVA line."""
        pattern = r'(SLVA\s+)\d+(\s+1\s+MOL\s+1\s+\w+\s+!\s+Read\s+)\d+(\s+solvent atoms)'
        
        def replace_numbers(match):
            return f"{match.group(1)}{atom_count}{match.group(2)}{atom_count}{match.group(3)}"
            
        updated = re.sub(pattern, replace_numbers, template_content)
        
        if updated == template_content:
            self.logger.warning("No SLVA line was modified in the template!")
            
        return updated
    
    def process_all_molecules(self):
        """Process all molecule directories."""
        try:
            # Read template file
            with open(self.template_path, 'r') as f:
                template_content = f.read()
            
            self.logger.info("Template file content preview:")
            self.logger.info(template_content[:200] + "...")
            
            # Get molecule directories
            mol_dirs = self.get_molecule_directories()
            self.logger.info(f"Found {len(mol_dirs)} molecule directories")
            
            if not mol_dirs:
                self.logger.error("No valid molecule directories found!")
                return
            
            # Process each directory
            successful_count = 0
            for mol_dir in mol_dirs:
                self.logger.info(f"\nProcessing {mol_dir.name}")
                
                # Process template
                slv_path = mol_dir / 'lig.slv'
                atom_count = self.parse_slv_file(slv_path)
                if atom_count is None:
                    continue
                
                # Update template
                updated_content = self.update_template(template_content, atom_count)
                
                # Write new prot.inp
                out_path = mol_dir / 'prot.inp'
                with open(out_path, 'w') as f:
                    f.write(updated_content)
                
                # Copy protein files if protein path is provided
                self.copy_protein_files(mol_dir)
                
                successful_count += 1
                self.logger.info(f"Completed processing {mol_dir.name}")
            
            # Log summary
            self.logger.info("\n" + "="*50)
            self.logger.info("Processing Summary:")
            self.logger.info(f"Total molecule directories found: {len(mol_dirs)}")
            self.logger.info(f"Successfully processed: {successful_count}")
            if self.protein_path:
                self.logger.info(f"Protein files copied from: {self.protein_path}")
            self.logger.info("="*50)
                
        except Exception as e:
            self.logger.error(f"Error during processing: {str(e)}")
            raise

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Process SACP directories, update templates, and copy protein files'
    )
    
    parser.add_argument(
        '--sacp_path',
        type=str,
        required=True,
        help='Path to the SACP directory'
    )
    
    parser.add_argument(
        '--template_path',
        type=str,
        required=True,
        help='Path to the template file'
    )
    
    parser.add_argument(
        '--protein_path',
        type=str,
        required=False,
        help='Path to the protein directory containing files to copy'
    )
    
    return parser.parse_args()

def main():
    args = parse_arguments()
    
    try:
        processor = SACPProcessor(
            args.sacp_path,
            args.template_path,
            args.protein_path
        )
        processor.process_all_molecules()
        print("\nProcessing completed successfully!")
        print(f"Log file saved in: {processor.logs_dir}")
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return 1
        
    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())
