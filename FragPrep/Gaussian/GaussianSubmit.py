#!/usr/bin/env python3
import os
import subprocess
import argparse
import datetime

def check_node_availability():
    try:
        process = subprocess.Popen(['sinfo', '-o', '%n %C'], 
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                universal_newlines=True)
        stdout, stderr = process.communicate()
        
        if process.returncode == 0:
            print("\nCurrent node availability:")
            print(stdout)
            return True
        return False
    except Exception as e:
        print(f"Error checking nodes: {str(e)}")
        return False

def check_job_completion(job_dir, jobs_dir):
    """Check if a job has completed successfully."""
    log_path = os.path.join(jobs_dir, job_dir, 'mpp.log')
    if not os.path.exists(log_path):
        return False, "No log file found"
    
    try:
        with open(log_path, 'r') as f:
            content = f.read()
            if "Normal termination" in content:
                return True, "Completed"
            else:
                return False, "Incomplete or error"
    except Exception as e:
        return False, f"Error reading log: {str(e)}"

def list_job_status(jobs_dir, incomplete_only=False):
    """List all jobs and their status in the specified jobs directory."""
    job_dirs = {}
    
    if not os.path.isdir(jobs_dir):
        print(f"Error: '{jobs_dir}' is not a valid directory")
        return []

    for item in os.listdir(jobs_dir):
        full_path = os.path.join(jobs_dir, item)
        if os.path.isdir(full_path):
            mpp_path = os.path.join(full_path, 'mpp.com')
            if os.path.exists(mpp_path):
                completed, status = check_job_completion(item, jobs_dir)
                if not incomplete_only or not completed:
                    job_dirs[item] = status
    
    if not job_dirs:
        print("\nNo jobs found!")
        print("Jobs directory: {}".format(jobs_dir))
        return []

    print("\nAvailable jobs in {}:".format(jobs_dir))
    print("{:<5} {:<30} {:<10}".format("Index", "Directory", "Status"))
    print("-" * 45)
    for i, (job, status) in enumerate(sorted(job_dirs.items()), 1):
        print("{:<5} {:<30} {:<10}".format(i, job, status))
    
    return [job for job, _ in sorted(job_dirs.items())]

def generate_job_script(job_dir, jobs_dir, log_dir):
    """Generate submission script for a single job."""
    full_path = os.path.abspath(os.path.join(jobs_dir, job_dir))
    script_path = os.path.join(log_dir, f"submit_{job_dir}.sh")
    
    with open(script_path, 'w') as script:
        script.write(f'''#!/bin/bash
#SBATCH --job-name={job_dir}
#SBATCH --output={log_dir}/{job_dir}_%j.out
#SBATCH --error={log_dir}/{job_dir}_%j.err
#SBATCH --time=5:59:00
#SBATCH -N 1
#SBATCH -n 16
#SBATCH --partition=short

module load gaussian/g16
source /shared/centos7/gaussian/g16/bsd/g16.profile

# Set up scratch directory
export GAUSS_SCRDIR=/scratch/$USER/gaussian_{job_dir}_$SLURM_JOB_ID
mkdir -p $GAUSS_SCRDIR

work={full_path}
cd $work

echo "Starting job in {job_dir} at $(date)"
echo "Running on node: $SLURMD_NODENAME"
g16 mpp.com
job_status=$?
echo "Finished job in {job_dir} at $(date)"

rm -rf $GAUSS_SCRDIR
rm -f Gau-*

exit $job_status
''')
    
    os.chmod(script_path, 0o755)
    return script_path

def submit_job(script_path):
    try:
        process = subprocess.Popen(['sbatch', script_path], 
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                universal_newlines=True)
        stdout, stderr = process.communicate()
        
        if process.returncode == 0:
            job_id = stdout.strip().split()[-1]
            return True, job_id, None
        else:
            return False, None, stderr
    except Exception as e:
        return False, None, str(e)

def main():
    parser = argparse.ArgumentParser(description='Submit Gaussian jobs.')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('-n', '--number', type=int, help='Number of jobs to submit')
    group.add_argument('-i', '--indices', type=str, help='Specific job indices (comma-separated)')
    group.add_argument('-a', '--all', action='store_true', help='Submit all incomplete jobs')
    group.add_argument('-l', '--list', action='store_true', help='List all jobs and their status')
    parser.add_argument('-s', '--start', type=int, help='Start index (1-based)', default=1)
    parser.add_argument('--status', action='store_true', help='Show status of all jobs')
    parser.add_argument('-j', '--jobs_dir', type=str, help='Directory containing job folders', default=None)
    args = parser.parse_args()

    # Determine the directory to scan for jobs
    if args.jobs_dir:
        jobs_dir = os.path.abspath(args.jobs_dir)
    else:
        base_directory = os.getcwd()
        jobs_dir = os.path.dirname(base_directory)
    
    if args.status:
        list_job_status(jobs_dir, incomplete_only=False)
        return

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_dir = os.path.join(os.getcwd(), f"gaussian_jobs_{timestamp}")
    os.makedirs(log_dir, exist_ok=True)
    
    available_jobs = list_job_status(jobs_dir, incomplete_only=True)
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
        print("  -a/--all: Submit all incomplete jobs")
        print("  -n/--number: Submit specific number of jobs")
        print("  -i/--indices: Submit specific job indices")
        print("  -l/--list: List jobs")
        print("  --status: Show all job statuses")
        return

    print("\nPreparing to submit {} jobs:".format(len(selected_jobs)))
    for job in selected_jobs:
        print("- {}".format(job))

    check_node_availability()

    response = input("\nSubmit these jobs? (y/n): ")
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
