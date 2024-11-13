# Script to automatically download the BDEW data file from the specified URL, extract the required file, verify the checksum, and move it to the right location.
# TODO: If the checksum check on the file from bdew.de fails, the script should attempt to download the file from the archive.org URL as a fallback and check that checksum instead.
# TODO: (or, the user could be prompted to confirm if they want to proceed with the file from archive.org if the checksum fails / wants to proceed with the updated file)

# This file was created largely with the help of ChatGPT

import os
import requests
import zipfile
import hashlib
import shutil

# Constants
URL = "https://www.bdew.de/media/documents/Profile.zip"
ARCHIVE_URL = "https://web.archive.org/web/20241002081545/https://www.bdew.de/media/documents/Profile.zip"
ZIP_FILE = "Profile.zip"
TARGET_FILE = "Repräsentative Profile VDEW.xls"
EXPECTED_CHECKSUM = "5bdcfd169c298f04cf538178e97e171376b26ed07c444b5c2068c7a52a27299d"
DEST_DIR = "h2pp/bdew_data"
DEST_FILE = os.path.join(DEST_DIR, "repraesentative_profile_vdew.xls")


def download_file(url, filename):
    """Download the file from the specified URL."""
    print(f"Downloading from {url}...")
    response = requests.get(url, stream=True)
    if response.status_code == 200:
        with open(filename, 'wb') as f:
            f.write(response.content)
        print(f"Downloaded {filename}")
    else:
        raise Exception(f"Failed to download from {url}")


def extract_file(zip_path, target_filename):
    """Extracts a specific file from a zip archive, handling encoding issues."""
    print(f"Extracting {target_filename} from {zip_path}...")
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        # List files in the zip to check for encoding issues
        for file_info in zip_ref.infolist():
            if TARGET_FILE.lower() in file_info.filename.lower():
                # Extract and rename the file to ensure correct encoding
                zip_ref.extract(file_info.filename)
                extracted_file = file_info.filename
                os.rename(extracted_file, TARGET_FILE)
                print(f"Extracted and renamed to {TARGET_FILE}")
                return
        raise FileNotFoundError(f"{TARGET_FILE} not found in the zip file")


def verify_checksum(filename, expected_checksum):
    """Verify the SHA256 checksum of a file."""
    print(f"Verifying checksum of {filename}...")
    sha256 = hashlib.sha256()
    with open(filename, "rb") as f:
        for block in iter(lambda: f.read(4096), b""):
            sha256.update(block)
    file_checksum = sha256.hexdigest()
    if file_checksum == expected_checksum:
        print("Checksum verified successfully.")
        return True
    else:
        print(f"Checksum mismatch! Expected: {expected_checksum}, Got: {file_checksum}. This might indicate a corrupted file or the file was updated.")
        return False


def main():
    # Step 1: Download the ZIP file (primary URL, fallback to archive if needed)
    try:
        download_file(URL, ZIP_FILE)
    except Exception as e:
        print(e)
        print("Trying archived version...")
        download_file(ARCHIVE_URL, ZIP_FILE)

    # Step 2: Extract the file with encoding correction
    try:
        extract_file(ZIP_FILE, TARGET_FILE)
    except FileNotFoundError as e:
        print(e)
        return

    # Step 3: Verify the checksum
    if not verify_checksum(TARGET_FILE, EXPECTED_CHECKSUM):
        print("Checksum verification failed. Exiting.")
        return

    # Step 4: Create the destination directory if it doesn't exist
    os.makedirs(DEST_DIR, exist_ok=True)

    # Step 5: Move and rename the file
    shutil.move(TARGET_FILE, DEST_FILE)
    print(f"File moved to {DEST_FILE}")

    # Step 6: Clean up the ZIP file
    os.remove(ZIP_FILE)
    print("Temporary files cleaned up.")

    print("Process completed successfully.")


if __name__ == "__main__":
    main()
