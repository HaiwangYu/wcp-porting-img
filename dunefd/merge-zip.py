import os
import shutil
import zipfile
import json
import glob
import sys

def merge_json_arrays(src_file1, src_file2, dest_file):
    with open(src_file1, 'r') as file1:
        data1 = json.load(file1)
    with open(src_file2, 'r') as file2:
        data2 = json.load(file2)

    merged_data = data1 + data2

    with open(dest_file, 'w') as dest:
        json.dump(merged_data, dest)


def merge_directories(src_dir1, src_dir2, dest_dir):
    for root, _, files in os.walk(src_dir1):
        relative_path = os.path.relpath(root, src_dir1)
        dest_path = os.path.join(dest_dir, relative_path)
        os.makedirs(dest_path, exist_ok=True)

        for file in files:
            src_file1 = os.path.join(root, file)
            dest_file = os.path.join(dest_path, file)

            if file.endswith(".json") and os.path.exists(os.path.join(src_dir2, relative_path, file)):
                # If a JSON file with the same name exists in src_dir2, merge them
                src_file2 = os.path.join(src_dir2, relative_path, file)
                merge_json_arrays(src_file1, src_file2, dest_file)
            else:
                shutil.copy2(src_file1, dest_file)

    # Copy files from src_dir2 that are not already handled
    for root, _, files in os.walk(src_dir2):
        relative_path = os.path.relpath(root, src_dir2)
        dest_path = os.path.join(dest_dir, relative_path)
        os.makedirs(dest_path, exist_ok=True)

        for file in files:
            src_file2 = os.path.join(root, file)
            dest_file = os.path.join(dest_path, file)

            if not os.path.exists(dest_file):
                shutil.copy2(src_file2, dest_file)

def main(zip_pattern, output_zip):
    # Temporary directories for extracted contents
    temp_dir1 = "temp_dir1"
    temp_dir2 = "temp_dir2"
    output_dir = "output_dir"

    os.makedirs(temp_dir1, exist_ok=True)
    os.makedirs(temp_dir2, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)

    try:
        # Find matching zip files
        zip_files = glob.glob(zip_pattern)

        # Extract zip files
        for zip_file in zip_files:
            try:
                with zipfile.ZipFile(zip_file, 'r') as zip_ref:
                    print(f"Extracting {zip_file}")
                    zip_ref.extractall(temp_dir1)
                    temp_dir1_files = os.listdir("temp_dir1")
                    print(temp_dir1_files)
            except zipfile.BadZipFile:
                continue

        # Merge directories
        merge_directories(temp_dir1, temp_dir2, output_dir)

        # Create a zip file from the output directory
        shutil.make_archive(output_zip, 'zip', output_dir)
    finally:
        # Clean up temporary directories
        shutil.rmtree(temp_dir1)
        shutil.rmtree(temp_dir2)
        shutil.rmtree(output_dir)

if __name__ == "__main__":
    # FILEPATH: /home/yuhw/wc/dunefd/img/merge-zip.py
    if len(sys.argv) < 2:
        print("Usage: python merge-zip.py <zip_pattern>")
        sys.exit(1)

    zip_pattern = sys.argv[1]
    print(zip_pattern)
    output_zip = "mabc"  # Replace with desired output directory

    shutil.rmtree(output_zip, ignore_errors=True)
    main(zip_pattern, output_zip)
    print(f"Files merged successfully into {output_zip}")
