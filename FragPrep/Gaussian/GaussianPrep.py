#!/usr/bin/env python3
import os
import re
import shutil
import argparse

def prepare_gaussian_input_batch(input_dir, output_dir, template_file):
    """
    Batch prepare Gaussian input files for multiple geometry files.

    Parameters:
    - input_dir: Directory containing .g geometry files
    - output_dir: Directory to save output folders
    - template_file: Path to the template .com file with Gaussian settings
    """
    if not os.path.isdir(input_dir):
        print("Error: {} is not a valid directory.".format(input_dir))
        return

    if not os.path.exists(template_file):
        print("Error: Template file {} not found.".format(template_file))
        return

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print("Created output directory: {}".format(output_dir))

    found_files = False
    for filename in os.listdir(input_dir):
        if filename.endswith('.g'):
            found_files = True
            base_name = os.path.splitext(filename)[0]
            job_dir = os.path.join(output_dir, base_name)

            if not os.path.exists(job_dir):
                os.makedirs(job_dir)
                print("Created directory: {}".format(job_dir))

            src_g_file = os.path.join(input_dir, filename)
            dst_g_file = os.path.join(job_dir, filename)
            shutil.copy2(src_g_file, dst_g_file)
            print("Copied {} to {}".format(filename, job_dir))

            prepare_single_gaussian_input(
                src_g_file,
                template_file,
                job_dir
            )

            print("Created mpp.com in {}\n".format(job_dir))
    
    if not found_files:
        print("No .g files found in {}".format(input_dir))

def prepare_single_gaussian_input(base_geometry_file, template_file, output_dir):
    """
    Prepare Gaussian input file with fixed output name 'mpp.com'.

    Parameters:
    - base_geometry_file: Path to the file containing molecule geometries
    - template_file: Path to the template .com file with Gaussian settings
    - output_dir: Directory to save prepared .com files
    """
    with open(template_file, 'r') as f:
        template_content = f.read()

    with open(base_geometry_file, 'r') as f:
        geometry_lines = f.readlines()

    current_molecule = []
    is_collecting = False

    for line in geometry_lines:
        clean_line = line.strip()

        if clean_line.startswith('#') or clean_line.startswith('Put') or clean_line == '':
            continue

        if re.match(r'^-?\d+\s+-?\d+$', clean_line):
            is_collecting = True
            current_molecule.append(line)
            continue

        if is_collecting:
            current_molecule.append(line)

    output_file = os.path.join(output_dir, 'mpp.com')
    write_gaussian_input(template_content, current_molecule, output_file)

def write_gaussian_input(template, geometry_lines, output_file):
    """
    Write Gaussian input file by combining template and geometry.

    Parameters:
    - template: Template content for Gaussian input
    - geometry_lines: Lines describing molecule geometry
    - output_file: Path to save the output .com file
    """
    full_content = template.rstrip() + '\n\n' + ''.join(geometry_lines) + '\n'

    with open(output_file, 'w') as f:
        f.write(full_content)

def main():
    parser = argparse.ArgumentParser(description='Prepare Gaussian input files from .g files.')
    parser.add_argument('--input', '-i', required=True, help='Directory containing .g files')
    parser.add_argument('--output', '-o', required=True, help='Directory for output folders')
    parser.add_argument('--template', '-t', required=True, help='Path to template.com file')
    args = parser.parse_args()

    prepare_gaussian_input_batch(args.input, args.output, args.template)

if __name__ == "__main__":
    main()
