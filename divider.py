import tools

def divide():
    tools.empty_folder('files')
    tools.empty_folder('raw_data')
    
    # Get the uploaded file list
    FILE = tools.list_dir('uploads')
    FILE = './uploads/' + FILE[0]

    MAX = 1024 * 32  # 32 KB max chapter size
    BUF = 50 * 1024 * 1024  # 50 MB buffer size (adjusted for practicality)

    chapters = 0
    uglybuf = b''  # Use bytes for binary data

    # Open meta data file for writing
    with open('raw_data/meta_data.txt', 'w') as meta_data:
        file__name = FILE.split('/')[-1]  # Extract file name from path
        print(file__name)
        meta_data.write("File_Name=%s\n" % file__name)

        # Read the file and divide it into parts
        with open(FILE, 'rb') as src:
            while True:
                target_filename = 'files/SECRET%07d' % chapters
                with open(target_filename, 'wb') as target_file:
                    written = 0

                    while written < MAX:
                        if len(uglybuf) > 0:
                            target_file.write(uglybuf)

                        data = src.read(min(BUF, MAX - written))

                        if not data:
                            break
                        
                        target_file.write(data)
                        written += len(data)
                        
                        # Read the next byte to continue the division process
                        uglybuf = src.read(1)

                        if len(uglybuf) == 0:
                            break

                # Increment chapter count and stop if end of file
                chapters += 1
                if len(uglybuf) == 0:
                    break
        
        # Write the number of chapters to the metadata
        meta_data.write("chapters=%d" % (chapters + 1))

