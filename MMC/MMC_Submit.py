#!/usr/bin/env python3
import os
from pathlib import Path
import argparse
import logging
import subprocess
from datetime import datetime

class MMCJobSubmitter:
    def __init__(self, sacp_path, mmc_path):
        self.sacp_dir = Path(sacp_path)
        self.mmc_path = Path(mmc_path)
        self.mmc_bin = self.mmc_path / 'mmc.bin'
        
        # Create logs directory
        self.logs_dir = Path('slurm_logs')
        self.logs_dir.mkdir(exist_ok=True)
        
        # Setup logging
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_file = self.logs_dir / f'job_submission_{timestamp}.log'
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
        # Validate paths
        if not self.sacp_dir.exists():
            raise FileNotFoundError(f"SACP directory not found: {sacp_path}")
        if not self.mmc_path.exists():
            raise FileNotFoundError(f"MMC directory not found: {mmc_path}")
        if not self.mmc_bin.exists():
            raise FileNotFoundError(f"mmc.bin not found in {mmc_path}")
            
        # If we find a nested SACP directory, use that instead
        nested_sacp = self.sacp_dir / 'SACP'
        if nested_sacp.exists() and nested_sacp.is_dir():
            self.sacp_dir = nested_sacp
        
        self.logger.info(f"Processing SACP directory: {self.sacp_dir}")
        self.logger.info(f"Using MMC binary: {self.mmc_bin}")
        
    def create_batch_slurm_script(self, mol_dirs, batch_number):
        """Create a SLURM submission script for a batch of molecule directories."""
        script_path = self.logs_dir / f'batch_{batch_number}_submit.sh'
        
        # Generate the parallel command to process all directories in the batch
        parallel_commands = []
        for mol_dir in mol_dirs:
            parallel_commands.append(
                f"cd {mol_dir.absolute()} && {self.mmc_bin.absolute()} < prot.inp > prot.out"
            )
        
        script_content = f"""#!/bin/bash
#SBATCH --job-name=MMC_batch_{batch_number}
#SBATCH --output={self.logs_dir}/batch_{batch_number}_slurm_%j.out
#SBATCH --error={self.logs_dir}/batch_{batch_number}_slurm_%j.err
#SBATCH --time=47:59:00
#SBATCH --nodes=1
#SBATCH --ntasks={len(mol_dirs)}
#SBATCH --cpus-per-task=1
#SBATCH --partition=short

module load parallel
parallel --jobs {len(mol_dirs)} ::: {' '.join(f'"{cmd}"' for cmd in parallel_commands)}
"""
        with open(script_path, 'w') as f:
            f.write(script_content)
        
        # Make script executable
        script_path.chmod(0o755)
        
        return script_path

    def submit_job(self, script_path):
        """Submit a job to SLURM."""
        try:
            result = subprocess.run(
                ['sbatch', str(script_path)],
                capture_output=True,
                text=True,
                check=True
            )
            job_id = result.stdout.strip().split()[-1]
            self.logger.info(f"Submitted job {job_id} for batch script {script_path.name}")
            return job_id
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Error submitting job for {script_path.name}: {e.stderr}")
            return None

    def process_all_molecules_in_batches(self, batch_size):
        """Process and submit jobs in batches."""
        mol_dirs = self.get_molecule_directories()
        if not mol_dirs:
            self.logger.error("No directories with prot.inp found!")
            return
        
        self.logger.info(f"Found {len(mol_dirs)} directories to process")
        
        submitted_jobs = []
        for i in range(0, len(mol_dirs), batch_size):
            batch_dirs = mol_dirs[i:i+batch_size]
            batch_number = i // batch_size + 1
            
            self.logger.info(f"\nProcessing batch {batch_number}")
            
            # Create SLURM batch script
            script_path = self.create_batch_slurm_script(batch_dirs, batch_number)
            self.logger.info(f"Created batch submission script: {script_path}")
            
            # Submit job
            job_id = self.submit_job(script_path)
            if job_id:
                submitted_jobs.append((f"batch_{batch_number}", job_id))
        
        # Print summary
        self.logger.info("\n" + "="*50)
        self.logger.info("Submission Summary:")
        self.logger.info(f"Total batches processed: {len(submitted_jobs)}")
        self.logger.info(f"Successfully submitted jobs: {len(submitted_jobs)}")
        self.logger.info("\nSubmitted Batches:")
        for batch_name, job_id in submitted_jobs:
            self.logger.info(f"  {batch_name}: {job_id}")
        self.logger.info("="*50)

    def get_molecule_directories(self):
        """Find all molecule directories containing prot.inp."""
        molecule_dirs = []
        for d in self.sacp_dir.iterdir():
            if d.is_dir() and (d / 'prot.inp').exists():
                molecule_dirs.append(d)
                self.logger.info(f"Found directory with prot.inp: {d.name}")
        return molecule_dirs

def parse_arguments():
    parser = argparse.ArgumentParser(
        description='Submit MMC jobs to SLURM'
    )
    parser.add_argument('--sacp_path', type=str, required=True, help='Path to the SACP directory')
    parser.add_argument('--mmc_path', type=str, required=True, help='Path to the MMC program directory')
    parser.add_argument('--batch_size', type=int, default=8, help='Number of jobs per batch')
    return parser.parse_args()

def main():
    args = parse_arguments()
    try:
        submitter = MMCJobSubmitter(args.sacp_path, args.mmc_path)
        submitter.process_all_molecules_in_batches(args.batch_size)
        print("\nJob submission completed successfully!")
    except Exception as e:
        print(f"Error: {str(e)}")
        return 1
    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())


