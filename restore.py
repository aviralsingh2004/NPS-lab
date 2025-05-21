import os
import tools

def restore():
    tools.empty_folder('restored_file')

    # Initialize variables
    chapters = 0

    # Read metadata from the file
    with open('raw_data/meta_data.txt', 'r') as meta_data:
        meta_info = []
        for row in meta_data:
            temp = row.strip().split('=')
            if len(temp) > 1:
                meta_info.append(temp[1])

    # Extract the file name from the meta info
    address = 'restored_file/' + meta_info[0]

    # List of files to be restored, sorted by filename
    list_of_files = sorted(tools.list_dir('files'))

    # Write the restored file
    with open(address, 'wb') as writer:
        for file in list_of_files:
            path = 'files/' + file
            with open(path, 'rb') as reader:
                # Read file contents and write them to the restored file
                writer.write(reader.read())

    # Clean up the 'files' folder
    tools.empty_folder('files')
