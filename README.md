Usage
Run the script from the command line with the required arguments: input directory, output directory, and template file.

Command Syntax
python3 GaussianPrep.py --input INPUT_DIR --output OUTPUT_DIR --template TEMPLATE_FILE

--input, -i: Directory containing .g geometry files.
--output, -o: Directory where output job folders will be created.
--template, -t: Path to the Gaussian template .com file.

Sample Output Structure

jobs/
├── mol1/
│   ├── mol1.g
│   └── mpp.com
├── mol2/
│   ├── mol2.g
│   └── mpp.com

Command Syntax
python3 GaussianSubmit.py -a -j jobs/ 



