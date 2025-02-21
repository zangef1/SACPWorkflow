#!/usr/bin/env python3
import os
import shutil
import subprocess
import argparse
import datetime
import re

def get_charge_multiplicity(g_file_path):
    """Extract charge and multiplicity from .g file using same approach as com_prep.py."""
    try:
        with open(g_file_path, 'r') as f:
            geometry_lines = f.readlines()
        
        # Process geometry file
        for line in geometry_lines:
            # Clean line
            clean_line = line.strip()
            
            # Skip comment lines and empty lines
            if clean_line.startswith('#') or clean_line.startswith('Put') or clean_line == '':
                continue
            
            # Detect charge and multiplicity line (flexible pattern)
            if re.match(r'^-?\d+\s+-?\d+$', clean_line):
                parts = clean_line.split()
                return parts[0], parts[1]
                
        print(f"\nError in {os.path.basename(g_file_path)}:")
        print("Could not find valid charge and multiplicity values.")
        return None, None
        
    except Exception as e:
        print(f"\nError reading {g_file_path}:")
        print(str(e))
        return None, None

def create_resp_input(charge, multiplicity):
    """Create RESP input content with correct charge and multiplicity."""
    return f'''%mem=35MW
%chk=mpp
%nproc=16
#HF/6-31G* Guess=read Geom=checkpoint SCF=tight Test Pop=MK iop(6/33=2) iop(6/42=6) iop(6/50=1) opt nosymm

mpp

{charge}  {multiplicity}

antechamber-ini.esp

antechamber.esp
'''

def setup_resp_folders(jobs_dir):
    """Create RESP folders and generate appropriate mpp.com files."""
    job_dirs = {}
    
    if not os.path.isdir(jobs_dir):
        print(f"Error: '{jobs_dir}' is not a valid directory")
        return {}
    
    for item in os.listdir(jobs_dir):
        full_path = os.path.join(jobs_dir, item)
        if os.path.isdir(full_path):
            # Check for .chk and .g files
            chk_files = [f for f in os.listdir(full_path) if f.endswith('.chk')]
            g_files = [f for f in os.listdir(full_path) if f.endswith('.g')]
            
            if chk_files and g_files:
                # Get charge and multiplicity from .g file
                g_file_path = os.path.join(full_path, g_files[0])
                charge, multiplicity = get_charge_multiplicity(g_file_path)
                
                if charge is None or multiplicity is None:
                    print(f"Warning: Could not determine charge and multiplicity for {item}, skipping...")
                    continue
                
                # Create RESP directory
                resp_dir = os.path.join(full_path, 'RESP')
                if not os.path.exists(resp_dir):
                    os.makedirs(resp_dir)
                    print("Created RESP directory for: {}".format(item))
                
                # Copy .chk file to RESP directory
                for chk_file in chk_files:
                    src = os.path.join(full_path, chk_file)
                    dst = os.path.join(resp_dir, chk_file)
                    shutil.copy2(src, dst)
                    print("Copied {} to {}/RESP".format(chk_file, item))
                
                # Create mpp.com with correct charge and multiplicity
                mpp_content = create_resp_input(charge, multiplicity)
                mpp_path = os.path.join(resp_dir, 'mpp.com')
                with open(mpp_path, 'w') as f:
                    f.write(mpp_content)
                print("Created mpp.com for {} with charge {} and multiplicity {}".format(
                    item, charge, multiplicity))
                
                job_dirs[item] = "Ready"
    
    if not job_dirs:
        print("\nNo suitable directories found!")
        return {}
        
    print("\nProcessed folders in {}:".format(jobs_dir))
    for job in sorted(job_dirs.keys()):
        print("- {}".format(job))
        
    return job_dirs

def list_resp_jobs(jobs_dir):
    """List available RESP jobs (directories with both .chk and mpp.com)."""
    job_dirs = {}
    
    if not os.path.isdir(jobs_dir):
        print(f"Error: '{jobs_dir}' is not a valid directory")
        return []
    
    for item in os.listdir(jobs_dir):
        full_path = os.path.join(jobs_dir, item)
        if os.path.isdir(full_path):
            resp_dir = os.path.join(full_path, 'RESP')
            if os.path.exists(resp_dir):
                mpp_path = os.path.join(resp_dir, 'mpp.com')
                if os.path.exists(mpp_path):
                    job_dirs[item] = "Ready"
    
    if not job_dirs:
        print("\nNo RESP jobs ready! Make sure each RESP folder has mpp.com file.")
        return []

    print("\nAvailable RESP jobs in {}:".format(jobs_dir))
    print("{:<5} {:<30} {:<10}".format("Index", "Directory", "Status"))
    print("-" * 45)
    for i, job in enumerate(sorted(job_dirs.keys()), 1):
        print("{:<5} {:<30} {:<10}".format(i, job, job_dirs[job]))
    
    return sorted(job_dirs.keys())

def generate_job_script(job_dir, jobs_dir, log_dir):
    """Generate submission script for a single RESP job."""
    full_path = os.path.abspath(os.path.join(jobs_dir, job_dir, 'RESP'))
    script_path = os.path.join(log_dir, f"submit_resp_{job_dir}.sh")
    
    with open(script_path, 'w') as script:
        script.write(f'''#!/bin/bash
#SBATCH --job-name=resp_{job_dir}
#SBATCH --output={log_dir}/resp_{job_dir}_%j.out
#SBATCH --error={log_dir}/resp_{job_dir}_%j.err
#SBATCH --time=5:59:00
#SBATCH -N 1
#SBATCH -n 16
#SBATCH --partition=short

# Load Gaussian
module load gaussian/g16
source /shared/centos7/gaussian/g16/bsd/g16.profile

# Set up scratch directory
export GAUSS_SCRDIR=/scratch/$USER/gaussian_resp_{job_dir}_$SLURM_JOB_ID
mkdir -p $GAUSS_SCRDIR

# Set current working directory
work={full_path}
cd $work

# Run job
echo "Starting RESP job in {job_dir} at $(date)"
g16 mpp.com
job_status=$?
echo "Finished RESP job in {job_dir} at $(date)"

# Cleanup scratch directory and temporary files
rm -rf $GAUSS_SCRDIR
rm -f Gau-*

exit $job_status
''')
    
    os.chmod(script_path, 0o755)
    return script_path

def submit_job(script_path):
    """Submit a single job and return the job ID."""
    try:
        process = subprocess.Popen(['sbatch', script_path], 
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                universal_newlines=True)
        stdout, stderr = process.communicate()
        
        if process.returncode == 0:
            # Extract job ID from slurm output
            job_id = stdout.strip().split()[-1]
            return True, job_id, None
        else:
            return False, None, stderr
    except Exception as e:
        return False, None, str(e)

def main():
    parser = argparse.ArgumentParser(description='Setup RESP folders and submit jobs.')
    parser.add_argument('--setup', action='store_true', help='Create RESP folders and generate input files')
    parser.add_argument('--submit', action='store_true', help='Submit RESP jobs')
    parser.add_argument('-n', '--number', type=int, help='Number of jobs to submit')
    parser.add_argument('-i', '--indices', type=str, help='Specific job indices (comma-separated)')
    parser.add_argument('-a', '--all', action='store_true', help='Submit all jobs')
    parser.add_argument('-l', '--list', action='store_true', help='List available jobs')
    parser.add_argument('-s', '--start', type=int, help='Start index (1-based)', default=1)
    parser.add_argument('-j', '--jobs_dir', type=str, help='Directory containing job folders', default=None)
    args = parser.parse_args()

    if not (args.setup or args.submit or args.list):
        print("\nPlease specify either --setup to create RESP folders, --submit to submit jobs, or -l/--list to list jobs")
        return

    # Determine the directory to scan for jobs
    if args.jobs_dir:
        jobs_dir = os.path.abspath(args.jobs_dir)
    else:
        base_directory = os.getcwd()
        jobs_dir = os.path.dirname(base_directory)

    if args.setup:
        setup_resp_folders(jobs_dir)
        return

    if args.list or args.submit:
        available_jobs = list_resp_jobs(jobs_dir)
        if not available_jobs:
            return

        if args.list:
            return

        if args.submit:
            # Create logs directory with timestamp
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            log_dir = os.path.join(os.getcwd(), f"resp_jobs_{timestamp}")
            os.makedirs(log_dir, exist_ok=True)

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
                print("  -a/--all: Submit all jobs")
                print("  -n/--number: Submit specific number of jobs")
                print("  -i/--indices: Submit specific job indices")
                return

            print("\nPreparing to submit {} RESP jobs:".format(len(selected_jobs)))
            for job in selected_jobs:
                print("- {}".format(job))

            response = input("\nSubmit these RESP jobs? (y/n): ")
            if response.lower() == 'y':
                successful_jobs = 0
                failed_jobs = []
                
                print("\nSubmitting jobs...")
                for job_dir in selected_jobs:
                    script_path = generate_job_script(job_dir, jobs_dir, log_dir)
                    success, job_id, error = submit_job(script_path)
                    
                    if success:
                        print(f"Submitted {job_dir}: Job ID {job_id}")
                        successful_jobs += 1
                    else:
                        print(f"Failed to submit {job_dir}: {error}")
                        failed_jobs.append(job_dir)
                
                print("\nSubmission Summary:")
                print(f"Successfully submitted: {successful_jobs}")
                print(f"Failed to submit: {len(failed_jobs)}")
                if failed_jobs:
                    print("Failed jobs:")
                    for job in failed_jobs:
                        print(f"- {job}")
                print(f"\nLog files will be saved in: {log_dir}")
            else:
                print("\nSubmission cancelled")

if __name__ == "__main__":
    main()
