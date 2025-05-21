import os
import shutil

def empty_folder(directory_name):
    """Empty the folder, removing all files and subdirectories inside it."""
    if not os.path.isdir(directory_name):
        os.makedirs(directory_name)
    else:
        # Loop through each item in the folder
        for the_file in os.listdir(directory_name):
            file_path = os.path.join(directory_name, the_file)
            try:
                if os.path.isfile(file_path):
                    os.unlink(file_path)  # Remove a file
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)  # Recursively remove a directory
            except Exception as e:
                print(f"Error while deleting {file_path}: {e}")

def list_dir(path):
    """Return a list of files and directories in the given path."""
    return os.listdir(path)
