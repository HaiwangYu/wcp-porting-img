import argparse
import glob
import json
import os
import shutil
import tempfile
import zipfile

def merge_json_arrays(src_file1, src_file2, dest_file):
    with open(src_file1, 'r') as file1:
        data1 = json.load(file1)
    with open(src_file2, 'r') as file2:
        data2 = json.load(file2)

    merged_data = data1 + data2

    with open(dest_file, 'w') as dest:
        json.dump(merged_data, dest)


def merge_into(dest_dir, incoming_dir):
    """
    Merge files from incoming_dir into dest_dir.
    - JSON files: append arrays when the same relative path exists in dest_dir.
    - Other files: keep existing dest version; copy only if missing.
    """
    for root, _, files in os.walk(incoming_dir):
        relative_path = os.path.relpath(root, incoming_dir)
        dest_path = os.path.join(dest_dir, relative_path)
        os.makedirs(dest_path, exist_ok=True)

        for file in files:
            incoming_file = os.path.join(root, file)
            dest_file = os.path.join(dest_path, file)

            if os.path.exists(dest_file):
                if file.endswith(".json"):
                    merge_json_arrays(dest_file, incoming_file, dest_file)
                # Keep existing non-JSON files; do nothing.
            else:
                shutil.copy2(incoming_file, dest_file)

def merge_zip_list(zip_paths, output_zip_base):
    if not zip_paths:
        raise ValueError("No zip files provided.")

    output_dir = tempfile.mkdtemp(prefix="merge_zip_output_")
    created_output = None

    try:
        for idx, zip_path in enumerate(zip_paths):
            with tempfile.TemporaryDirectory(prefix="merge_zip_input_") as temp_in:
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(temp_in)

                if created_output is None:
                    # First zip initializes the output directory.
                    shutil.copytree(temp_in, output_dir, dirs_exist_ok=True)
                    created_output = True
                else:
                    merge_into(output_dir, temp_in)

        shutil.make_archive(output_zip_base, 'zip', output_dir)
    finally:
        shutil.rmtree(output_dir, ignore_errors=True)

def normalize_output_basename(output_path):
    return output_path[:-4] if output_path.endswith(".zip") else output_path

def parse_args():
    parser = argparse.ArgumentParser(
        description="Merge multiple zip files (supporting glob patterns) into one."
    )
    parser.add_argument(
        "output_zip",
        help="Output zip file path ('.zip' is optional).",
    )
    parser.add_argument(
        "inputs",
        nargs="+",
        help="Zip files or glob patterns (e.g., 'mabc-apa*-face*.zip').",
    )
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    output_base = normalize_output_basename(args.output_zip)

    zip_list = []
    for pattern in args.inputs:
        zip_list.extend(sorted(glob.glob(pattern)))

    if not zip_list:
        raise SystemExit("No zip files matched the provided patterns.")

    # Remove any existing archive to avoid appending ".zip" twice when re-running.
    existing_zip = f"{output_base}.zip"
    if os.path.exists(existing_zip):
        os.remove(existing_zip)

    merge_zip_list(zip_list, output_base)
    print(f"Merged {len(zip_list)} zip files into {existing_zip}")
