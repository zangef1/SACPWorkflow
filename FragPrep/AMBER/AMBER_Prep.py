#!/usr/bin/env python3
import os
import subprocess
import argparse

def run_command(command, cwd=None):
    """Execute a command and return status, output, and error."""
    process = subprocess.Popen(command, 
                               stdout=subprocess.PIPE, 
                               stderr=subprocess.PIPE,
                               universal_newlines=True,
                               shell=True,
                               cwd=cwd)
    stdout, stderr = process.communicate()
    return process.returncode == 0, stdout, stderr

def generate_amber_params(base_directory, indices=None, num_jobs=None):
    parent_dir = os.path.dirname(base_directory)
    job_dirs = {}
    
    for item in os.listdir(parent_dir):
        if item == os.path.basename(base_directory):
            continue
            
        full_path = os.path.join(parent_dir, item)
        if os.path.isdir(full_path):
            resp_dir = os.path.join(full_path, 'RESP')
            if os.path.exists(resp_dir):
                mpp_log = os.path.join(resp_dir, 'mpp.log')
                if os.path.exists(mpp_log):
                    job_dirs[item] = resp_dir
    
    if not job_dirs:
        print("\nNo completed RESP calculations found!")
        return

    # Sort the jobs
    sorted_jobs = sorted(job_dirs.items())
    
    # Handle job selection
    if indices:
        try:
            selected_jobs = [(sorted_jobs[i-1][0], sorted_jobs[i-1][1]) for i in indices]
        except IndexError:
            print("Error: Invalid job indices provided")
            return
    elif num_jobs:
        selected_jobs = sorted_jobs[:num_jobs]
    else:
        selected_jobs = sorted_jobs

    print("\nFound {} completed RESP calculations, processing {} jobs:".format(
        len(job_dirs), len(selected_jobs)))
    print("{:<5} {:<30} {:<10}".format("Index", "Directory", "Status"))
    print("-" * 45)
    
    successful = []
    failed = []
    
    for i, (job_dir, resp_path) in enumerate(selected_jobs, 1):
        print("{:<5} {:<30} Processing...".format(i, job_dir))
        
        # Create amber directory
        amber_dir = os.path.join(resp_path, 'AMBER')
        os.makedirs(amber_dir, exist_ok=True)
        
        # Get input log file
        log_file = os.path.join(resp_path, 'mpp.log')
        
        try:
            # Run antechamber for mol2
            mol2_cmd = f"antechamber -fi gout -fo mol2 -pf y -i {log_file} -o MOL.mol2 -c resp"
            success_mol2, out_mol2, err_mol2 = run_command(mol2_cmd, cwd=amber_dir)
            
            if not success_mol2:
                failed.append((job_dir, "mol2 generation failed"))
                print("{:<5} {:<30} Failed at mol2 generation".format(i, job_dir))
                continue
                
            # Run antechamber for prepi
            prepi_cmd = f"antechamber -fi gout -fo prepi -pf y -i {log_file} -o MOL.prepi -c resp"
            success_prepi, out_prepi, err_prepi = run_command(prepi_cmd, cwd=amber_dir)
            
            if not success_prepi:
                failed.append((job_dir, "prepi generation failed"))
                print("{:<5} {:<30} Failed at prepi generation".format(i, job_dir))
                continue
            
            # Run parmchk2
            parmchk_cmd = f"parmchk2 -f prepi -i MOL.prepi -o MOL.frcmod"
            success_parm, out_parm, err_parm = run_command(parmchk_cmd, cwd=amber_dir)
            
            if not success_parm:
                failed.append((job_dir, "parmchk2 failed"))
                print("{:<5} {:<30} Failed at parmchk2".format(i, job_dir))
                continue
                
            # Run antechamber to generate PDB
            pdb_cmd = f"antechamber -fi prepi -fo pdb -i MOL.prepi -o MOL.pdb"
            success_pdb, out_pdb, err_pdb = run_command(pdb_cmd, cwd=amber_dir)
            
            if not success_pdb:
                failed.append((job_dir, "PDB generation failed"))
                print("{:<5} {:<30} Failed at PDB generation".format(i, job_dir))
                continue
            
            # Create tleap input file
            tleap_content = """source leaprc.gaff
loadamberprep MOL.prepi
loadAmberParams MOL.frcmod
LIG = loadpdb MOL.pdb
saveAmberParm LIG lig.top lig.crd
quit
"""
            tleap_input_path = os.path.join(amber_dir, 'tleap.in')
            with open(tleap_input_path, 'w') as f:
                f.write(tleap_content)
            
            # Run tleap
            tleap_cmd = f"tleap -f tleap.in"
            success_tleap, out_tleap, err_tleap = run_command(tleap_cmd, cwd=amber_dir)

            if not success_tleap:
                failed.append((job_dir, f"tleap failed:\n{err_tleap}"))
                print("{:<5} {:<30} Failed at tleap".format(i, job_dir))
                # Print the stderr for debugging
                print("tleap error output:\n", err_tleap)
                continue

            # If all steps successful
            successful.append(job_dir)
            print("{:<5} {:<30} Completed".format(i, job_dir))
            
        except Exception as e:
            failed.append((job_dir, str(e)))
            print("{:<5} {:<30} Error: {}".format(i, job_dir, str(e)))
    
    # Print summary
    print("\nParameter Generation Summary:")
    print(f"Successfully processed: {len(successful)}")
    print(f"Failed: {len(failed)}")
    
    if successful:
        print("\nSuccessful jobs:")
        for job in successful:
            amber_dir = os.path.join(parent_dir, job, 'RESP', 'AMBER')
            print(f"- {job}")
            print("  Files generated:")
            for f in ["MOL.mol2", "MOL.prepi", "MOL.frcmod", "MOL.pdb", "lig.top", "lig.crd"]:
                print(f"  - {os.path.join(amber_dir, f)}")
    
    if failed:
        print("\nFailed jobs:")
        for job, reason in failed:
            print(f"- {job}: {reason}")

def main():
    parser = argparse.ArgumentParser(description='Generate Amber parameters from RESP calculations.')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('-n', '--number', type=int, help='Number of jobs to process')
    group.add_argument('-i', '--indices', type=str, help='Specific job indices to process (comma-separated)')
    group.add_argument('-a', '--all', action='store_true', help='Process all jobs (default)')
    parser.add_argument('-l', '--list', action='store_true', help='List available jobs without processing')
    parser.add_argument('-v', '--verbose', action='store_true', help='Show detailed output')
    args = parser.parse_args()
    
    base_directory = os.getcwd()
    
    # Convert indices string to list if provided
    indices = None
    if args.indices:
        try:
            indices = [int(x.strip()) for x in args.indices.split(',')]
        except ValueError:
            print("Error: Invalid indices format. Use comma-separated numbers (e.g., 1,3,5)")
            return
    
    generate_amber_params(base_directory, indices=indices, num_jobs=args.number)

if __name__ == "__main__":
    main()
