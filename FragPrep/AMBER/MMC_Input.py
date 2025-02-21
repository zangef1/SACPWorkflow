#!/usr/bin/env python3
import os
import argparse
from typing import Dict, List, Tuple

class MoleculeConverter:
    def __init__(self):
        self.atoms_data = {}
        self.coords = {}
        self.atom_types = {}
        self.charges = {}
        self.atom_order = []

    def read_pdb_file(self, pdb_path: str) -> None:
        """Extract coordinates and atom sequence from PDB file"""
        with open(pdb_path, 'r') as f:
            for line in f:
                if line.startswith('ATOM'):
                    atom_num = int(line[6:11].strip())
                    atom_name = line[12:16].strip()
                    x = float(line[30:38])
                    y = float(line[38:46])
                    z = float(line[46:54])
                    self.coords[atom_name] = (x, y, z)
                    self.atom_order.append(atom_name)

    def read_prepi_file(self, prepi_path: str) -> None:
        """Extract atom types from PREPI file"""
        with open(prepi_path, 'r') as f:
            lines = f.readlines()
            start_processing = False
            
            for line in lines:
                if 'CORRECT' in line:
                    start_processing = True
                    continue
                if start_processing and 'LOOP' in line:
                    break
                if start_processing and line.strip() and 'DUMM' not in line:
                    parts = line.strip().split()
                    if len(parts) >= 8:
                        atom_name = parts[1]
                        atom_type = parts[2]
                        self.atom_types[atom_name] = atom_type

    def read_top_file(self, top_path: str) -> None:
        """Extract charges from TOP file"""
        with open(top_path, 'r') as f:
            lines = f.readlines()
            
            charge_section = False
            for i, line in enumerate(lines):
                if '%FLAG CHARGE' in line:
                    charge_start = i + 2
                    charge_section = True
                    continue
                if charge_section and '%FLAG' in line:
                    charge_end = i
                    break
                    
            if charge_section:
                charges = []
                for line in lines[charge_start:charge_end]:
                    values = [float(line[i:i+16].strip()) for i in range(0, len(line.strip()), 16)]
                    charges.extend(values)
                
                charges = [charge/18.2223 for charge in charges]
                
                for i, atom_name in enumerate(self.atom_order):
                    if i < len(charges):
                        self.charges[atom_name] = charges[i]

    def format_line(self, atom_name: str) -> str:
        """Format a single line according to the required format"""
        try:
            x, y, z = self.coords[atom_name]
            atom_type = self.atom_types[atom_name]
            charge = self.charges[atom_name]
            
            # Format atom type (2 chars + exactly 6 spaces)
            line = f" {atom_type:<2}      "  # 1 space, atom type, 6 spaces
            
            # Format all numbers to exact width (8 chars including sign)
            def format_num(val):
                if val >= 0:
                    num_str = f" {abs(val):7.5f}"  # space + 7 chars
                else:
                    num_str = f"-{abs(val):7.5f}"  # minus + 7 chars
                return num_str
                
            # Build the line with:
            # - 2 spaces between coordinate numbers
            # - 4 spaces before "1"
            # - 2 spaces between "1" and "MOL"
            # - 2 spaces between "MOL" and atom name
            x_str = format_num(x)
            y_str = format_num(y)
            z_str = format_num(z)
            charge_str = format_num(charge)
            
            return f"{line}{x_str}  {y_str}  {z_str}  {charge_str}    1  MOL  {atom_name}"
            
        except KeyError as e:
            raise Exception(f"Missing data for atom {atom_name}: {str(e)}")
            
        except KeyError as e:
            raise Exception(f"Missing data for atom {atom_name}: {str(e)}")
            
        except KeyError as e:
            raise Exception(f"Missing data for atom {atom_name}: {str(e)}")
            
        except KeyError as e:
            raise Exception(f"Missing data for atom {atom_name}: {str(e)}")

    def create_slv_file(self, output_path: str) -> None:
        """Generate the .slv file"""
        with open(output_path, 'w') as f:
            for atom_name in self.atom_order:
                line = self.format_line(atom_name)
                f.write(line + '\n')

def list_amber_jobs(base_directory):
    """List available jobs with AMBER results."""
    parent_dir = os.path.dirname(base_directory)
    current_dir = os.path.basename(base_directory)
    job_dirs = {}
    
    for item in os.listdir(parent_dir):
        if item == current_dir:
            continue
            
        full_path = os.path.join(parent_dir, item)
        if os.path.isdir(full_path):
            resp_dir = os.path.join(full_path, 'RESP')
            if os.path.exists(resp_dir):
                amber_dir = os.path.join(resp_dir, 'AMBER')
                if os.path.exists(amber_dir):
                    if all(os.path.exists(os.path.join(amber_dir, f)) for f in ['MOL.pdb', 'MOL.prepi']):
                        job_dirs[item] = "Ready"
    
    if not job_dirs:
        print("\nNo jobs with AMBER results found in RESP/AMBER folders!")
        print(f"Looking in: {parent_dir}")
        return []

    print("\nAvailable jobs with AMBER results:")
    print("{:<5} {:<30} {:<10}".format("Index", "Directory", "Status"))
    print("-" * 45)
    for i, job in enumerate(sorted(job_dirs.keys()), 1):
        print("{:<5} {:<30} {:<10}".format(i, job, job_dirs[job]))
    
    return sorted(job_dirs.keys())

def process_molecule(pdb_path: str, prepi_path: str, top_path: str, output_path: str) -> None:
    """Process molecule files and generate .slv file"""
    try:
        converter = MoleculeConverter()
        
        converter.read_pdb_file(pdb_path)
        converter.read_prepi_file(prepi_path)
        converter.read_top_file(top_path)
        converter.create_slv_file(output_path)
        
        print(f"Successfully created SLV file: {output_path}")
        
    except Exception as e:
        print(f"Error processing molecule: {str(e)}")
        raise

def main():
    parser = argparse.ArgumentParser(description='Convert AMBER results to SLV format for MMC')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('-n', '--number', type=int, help='Number of jobs to process')
    group.add_argument('-i', '--indices', type=str, help='Specific job indices (comma-separated)')
    group.add_argument('-a', '--all', action='store_true', help='Process all jobs')
    group.add_argument('-l', '--list', action='store_true', help='List available jobs')
    parser.add_argument('-s', '--start', type=int, help='Start index (1-based)', default=1)
    args = parser.parse_args()

    base_directory = os.getcwd()
    available_jobs = list_amber_jobs(base_directory)
    
    if not available_jobs:
        return
        
    if args.list:
        return

    if args.all:
        selected_jobs = available_jobs
    elif args.indices:
        try:
            indices = [int(x.strip()) for x in args.indices.split(',')]
            selected_jobs = [available_jobs[i-1] for i in indices]
        except (ValueError, IndexError):
            print("Error: Invalid indices")
            return
    elif args.number:
        start_idx = args.start - 1
        if start_idx < 0 or start_idx >= len(available_jobs):
            print("Error: Invalid start index")
            return
        end_idx = min(start_idx + args.number, len(available_jobs))
        selected_jobs = available_jobs[start_idx:end_idx]
    else:
        print("\nPlease specify one of:")
        print("  -a/--all: Process all jobs")
        print("  -n/--number: Process specific number of jobs")
        print("  -i/--indices: Process specific jobs")
        print("  -l/--list: List available jobs")
        return

    print("\nPreparing to process {} jobs:".format(len(selected_jobs)))
    for job in selected_jobs:
        print("- {}".format(job))

    response = input("\nProcess these jobs? (y/n): ")
    if response.lower() == 'y':
        parent_dir = os.path.dirname(base_directory)
        successful_jobs = 0
        failed_jobs = []
        
        print("\nProcessing jobs...")
        for job_dir in selected_jobs:
            amber_dir = os.path.join(parent_dir, job_dir, 'RESP', 'AMBER')
            try:
                pdb_path = os.path.join(amber_dir, 'MOL.pdb')
                prepi_path = os.path.join(amber_dir, 'MOL.prepi')
                top_path = os.path.join(amber_dir, 'lig.top')
                output_path = os.path.join(amber_dir, 'lig.slv')
                
                process_molecule(pdb_path, prepi_path, top_path, output_path)
                successful_jobs += 1
                
            except Exception as e:
                print(f"Failed to process {job_dir}: {str(e)}")
                failed_jobs.append(job_dir)
        
        print("\nProcessing Summary:")
        print(f"Successfully processed: {successful_jobs}")
        print(f"Failed to process: {len(failed_jobs)}")
        if failed_jobs:
            print("Failed jobs:")
            for job in failed_jobs:
                print(f"- {job}")
    else:
        print("\nProcessing cancelled")

if __name__ == "__main__":
    main()
