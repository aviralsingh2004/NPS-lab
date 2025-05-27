import os
from flask import Flask, request, redirect, url_for, render_template, send_file, flash, jsonify
from werkzeug.utils import secure_filename
import tools
import divider as dv
import encrypter as enc
import decrypter as dec
import restore as rst
import socket
import requests
from requests.exceptions import RequestException
import base64
import json
import threading
import time
import logging
from flask_cors import CORS
import traceback
import shutil

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

UPLOAD_FOLDER = './uploads/'
UPLOAD_KEY = './key/'
ALLOWED_EXTENSIONS = {'pem', 'txt', 'pdf', 'doc', 'docx', 'jpg', 'jpeg', 'png'}

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})  # Enable CORS for all routes
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['UPLOAD_KEY'] = UPLOAD_KEY
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.secret_key = os.urandom(24)

# Create necessary directories with better error handling
required_directories = [UPLOAD_FOLDER, UPLOAD_KEY, 'files', 'encrypted', 'restored_file', 'raw_data', 'received_files']
for directory in required_directories:
    try:
        os.makedirs(directory, exist_ok=True)
        
        # Verify directory was created and is writable
        if not os.path.exists(directory):
            raise Exception(f"Failed to create directory: {directory}")
        if not os.access(directory, os.W_OK):
            raise Exception(f"Directory is not writable: {directory}")
            
        logger.debug(f"Directory verified: {directory}")
    except Exception as e:
        logger.error(f"Error with directory {directory}: {str(e)}")
        # Don't exit, but log the error for debugging

# Store connected peers and their status
connected_peers = {}
peer_connections = {}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception as e:
        logger.error(f"Error getting local IP: {str(e)}")
        return '127.0.0.1'

def test_peer_connection(peer_ip):
    """Test connection to a peer with better error handling"""
    try:
        response = requests.get(f'http://{peer_ip}:8000/ping', timeout=5)
        return response.status_code == 200
    except requests.exceptions.ConnectionError:
        logger.error(f"Connection error to peer {peer_ip}")
        return False
    except requests.exceptions.Timeout:
        logger.error(f"Timeout connecting to peer {peer_ip}")
        return False
    except Exception as e:
        logger.error(f"Error connecting to peer {peer_ip}: {str(e)}")
        return False

def safe_remove_file(file_path):
    """Safely remove a file with error handling"""
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.debug(f"Removed file: {file_path}")
    except Exception as e:
        logger.error(f"Error removing file {file_path}: {str(e)}")

def safe_copy_file(src, dst):
    """Safely copy a file instead of moving it"""
    try:
        if not os.path.exists(src):
            logger.error(f"Source file does not exist: {src}")
            return False
            
        if not os.access(src, os.R_OK):
            logger.error(f"Source file is not readable: {src}")
            return False
            
        # Ensure destination directory exists
        dst_dir = os.path.dirname(dst)
        if not os.path.exists(dst_dir):
            os.makedirs(dst_dir, exist_ok=True)
            logger.debug(f"Created destination directory: {dst_dir}")
            
        if not os.access(dst_dir, os.W_OK):
            logger.error(f"Destination directory is not writable: {dst_dir}")
            return False
            
        shutil.copy2(src, dst)
        
        # Verify the copy was successful
        if not os.path.exists(dst):
            logger.error(f"File was not copied successfully to: {dst}")
            return False
            
        src_size = os.path.getsize(src)
        dst_size = os.path.getsize(dst)
        
        if src_size != dst_size:
            logger.error(f"File sizes don't match - src: {src_size}, dst: {dst_size}")
            return False
            
        logger.debug(f"Successfully copied file from {src} to {dst} ({dst_size} bytes)")
        return True
        
    except Exception as e:
        logger.error(f"Error copying file from {src} to {dst}: {str(e)}")
        return False

def encrypt_file(file_path):
    """Encrypt a file and return the key path"""
    try:
        logger.debug(f"Starting encryption of file: {file_path}")
        
        # Ensure the file exists and is readable
        if not os.path.exists(file_path):
            raise Exception(f"Source file not found: {file_path}")
        
        if not os.access(file_path, os.R_OK):
            raise Exception(f"Source file is not readable: {file_path}")
            
        file_size = os.path.getsize(file_path)
        if file_size == 0:
            raise Exception(f"Source file is empty: {file_path}")
            
        logger.debug(f"Source file verified - size: {file_size} bytes")
        
        # Since the file is already in the uploads directory (saved by Flask),
        # we don't need to copy it again. Just verify it's there.
        if not file_path.startswith(UPLOAD_FOLDER):
            # If for some reason the file is not in uploads, copy it
            filename = os.path.basename(file_path)
            upload_path = os.path.join(UPLOAD_FOLDER, filename)
            
            if not safe_copy_file(file_path, upload_path):
                raise Exception(f"Failed to copy file to uploads directory")
            
            logger.debug(f"File copied to uploads: {upload_path}")
        else:
            logger.debug(f"File already in uploads directory: {file_path}")
        
        # Clear any existing files in the necessary directories
        try:
            tools.empty_folder('files')
            tools.empty_folder('encrypted')
            tools.empty_folder('key')
            logger.debug("Cleared working directories")
        except Exception as e:
            logger.warning(f"Error clearing folders: {str(e)}")
        
        # Encrypt the file
        try:
            logger.debug("Starting divide process")
            dv.divide()
            logger.debug("Starting encryption process")
            enc.encrypter()
            logger.debug("Encryption process completed")
        except Exception as e:
            logger.error(f"Error during encryption process: {str(e)}")
            raise Exception(f"Encryption failed: {str(e)}")
        
        # Get the generated key
        try:
            list_directory = tools.list_dir('key')
            if not list_directory:
                raise Exception("No key generated during encryption")
            
            key_path = os.path.join('key', list_directory[0])
            
            # Verify key file exists and is not empty
            if not os.path.exists(key_path):
                raise Exception("Generated key file does not exist")
            if os.path.getsize(key_path) == 0:
                raise Exception("Generated key file is empty")
                
            logger.debug(f"Encryption completed successfully. Key path: {key_path}")
            return key_path
        except Exception as e:
            logger.error(f"Error accessing generated key: {str(e)}")
            raise
        
    except Exception as e:
        logger.error(f"Error in encrypt_file: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise

def decrypt_file(file_path, key_path):
    """Decrypt a file using the provided key"""
    try:
        logger.debug(f"Starting decryption of file: {file_path} with key: {key_path}")
        
        # Ensure the encrypted file exists
        if not os.path.exists(file_path):
            raise Exception(f"Encrypted file not found: {file_path}")
            
        # Ensure the key exists
        if not os.path.exists(key_path):
            raise Exception(f"Key file not found: {key_path}")
            
        # Verify files are not empty
        if os.path.getsize(file_path) == 0:
            raise Exception("Encrypted file is empty")
        if os.path.getsize(key_path) == 0:
            raise Exception("Key file is empty")
            
        # Clear any existing files in the necessary directories, EXCEPT raw_data
        try:
            tools.empty_folder('restored_file')
        except Exception as e:
            logger.warning(f"Error clearing restored_file folder: {str(e)}")
        
        # Decrypt the file
        try:
            dec.decrypter()
            rst.restore()
        except Exception as e:
            logger.error(f"Error during decryption process: {str(e)}")
            raise Exception(f"Decryption failed: {str(e)}")
        
        # Get the decrypted file
        try:
            list_directory = tools.list_dir('restored_file')
            if not list_directory:
                raise Exception("No file restored after decryption")
            
            decrypted_path = os.path.join('restored_file', list_directory[0])
            
            # Verify decrypted file exists and is not empty
            if not os.path.exists(decrypted_path) or os.path.getsize(decrypted_path) == 0:
                raise Exception("Decrypted file is invalid or empty")
                
            logger.debug(f"Decryption completed. File path: {decrypted_path}")
            return decrypted_path
        except Exception as e:
            logger.error(f"Error accessing decrypted file: {str(e)}")
            raise
        
    except Exception as e:
        logger.error(f"Error in decrypt_file: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise

@app.errorhandler(413)
def too_large(e):
    return jsonify({'status': 'error', 'message': 'File too large'}), 413

@app.errorhandler(Exception)
def handle_exception(e):
    logger.error(f"Unhandled exception: {str(e)}")
    logger.error(f"Traceback: {traceback.format_exc()}")
    return jsonify({'status': 'error', 'message': 'Internal server error'}), 500

@app.route('/')
def index():
    return redirect(url_for('connect'))

@app.route('/connect')
def connect():
    local_ip = get_local_ip()
    return render_template('connect.html', local_ip=local_ip)

@app.route('/test-connection/<ip>')
def test_connection(ip):
    try:
        if test_peer_connection(ip):
            # Notify the peer about the connection
            try:
                response = requests.post(f'http://{ip}:8000/peer-connected', 
                            json={'peer': get_local_ip()},
                            timeout=5)
                if response.status_code == 200:
                    peer_connections[ip] = True
            except Exception as e:
                logger.warning(f"Failed to notify peer {ip}: {str(e)}")
            return jsonify({'status': 'success', 'message': 'Connection successful'})
    except Exception as e:
        logger.error(f"Error in test_connection: {str(e)}")
    return jsonify({'status': 'error', 'message': 'Could not connect to device'})

@app.route('/peer-connected', methods=['POST'])
def peer_connected():
    try:
        data = request.get_json()
        if data and 'peer' in data:
            peer = data['peer']
            peer_connections[peer] = True
            logger.info(f"Peer connected: {peer}")
            return jsonify({'status': 'success'})
    except Exception as e:
        logger.error(f"Error in peer_connected: {str(e)}")
    return jsonify({'status': 'error', 'message': 'Invalid request'}), 400

@app.route('/get-connections')
def get_connections():
    return jsonify({'connections': list(peer_connections.keys())})

@app.route('/ping')
def ping():
    return jsonify({'status': 'success', 'timestamp': time.time()})

@app.route('/share-file', methods=['POST'])
def share_file():
    logger.debug("=== Starting file share request ===")
    
    try:
        # Check if request has file part
        if 'file' not in request.files:
            logger.error("No file part in request")
            return jsonify({'status': 'error', 'message': 'No file part in request'}), 400
            
        file = request.files['file']
        if file.filename == '':
            logger.error("No file selected")
            return jsonify({'status': 'error', 'message': 'No file selected'}), 400
            
        if not file:
            logger.error("File object is None")
            return jsonify({'status': 'error', 'message': 'Invalid file'}), 400
            
        logger.debug(f"Received file: {file.filename}")
        
        # Check file extension
        if not allowed_file(file.filename):
            logger.error(f"Invalid file format: {file.filename}")
            return jsonify({'status': 'error', 'message': f'Invalid file format. Allowed: {ALLOWED_EXTENSIONS}'}), 400
            
        # Secure the filename
        filename = secure_filename(file.filename)
        if not filename:
            logger.error("Filename became empty after securing")
            return jsonify({'status': 'error', 'message': 'Invalid filename'}), 400
            
        # Create file path
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        logger.debug(f"Saving file to: {file_path}")
        
        # Ensure upload directory exists and is writable
        try:
            if not os.path.exists(app.config['UPLOAD_FOLDER']):
                os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                logger.debug(f"Created upload directory: {app.config['UPLOAD_FOLDER']}")
            
            # Check if directory is writable
            if not os.access(app.config['UPLOAD_FOLDER'], os.W_OK):
                raise Exception(f"Upload directory is not writable: {app.config['UPLOAD_FOLDER']}")
                
        except Exception as e:
            logger.error(f"Upload directory issue: {str(e)}")
            return jsonify({'status': 'error', 'message': f'Upload directory error: {str(e)}'}), 500
        
        # Save the file
        try:
            logger.debug(f"Attempting to save file to: {file_path}")
            file.save(file_path)
            logger.debug(f"File.save() completed for: {file_path}")
            
            # Verify file was saved correctly
            if not os.path.exists(file_path):
                raise Exception("File was not saved properly - file does not exist after save")
            
            file_size = os.path.getsize(file_path)
            if file_size == 0:
                raise Exception("Saved file is empty")
            
            logger.debug(f"File saved and verified successfully - size: {file_size} bytes")
                
        except Exception as e:
            logger.error(f"Error saving file: {str(e)}")
            logger.error(f"Upload folder: {app.config['UPLOAD_FOLDER']}")
            logger.error(f"File path: {file_path}")
            logger.error(f"Upload folder exists: {os.path.exists(app.config['UPLOAD_FOLDER'])}")
            logger.error(f"Upload folder writable: {os.access(app.config['UPLOAD_FOLDER'], os.W_OK) if os.path.exists(app.config['UPLOAD_FOLDER']) else 'N/A'}")
            return jsonify({'status': 'error', 'message': f'Failed to save file: {str(e)}'}), 500
        
        # Encrypt the file
        try:
            logger.debug("Starting encryption process")
            key_path = encrypt_file(file_path)
            logger.debug(f"File encrypted successfully, key path: {key_path}")
            
            # Read the key with error handling
            try:
                with open(key_path, 'rb') as f:
                    key_data = f.read()
                if not key_data:
                    raise Exception("Key file is empty")
                key_b64 = base64.b64encode(key_data).decode('utf-8')
                logger.debug("Key converted to base64 successfully")
            except Exception as e:
                logger.error(f"Error reading key file: {str(e)}")
                raise Exception(f"Failed to read encryption key: {str(e)}")
            
            # Read the encrypted file
            try:
                encrypted_files = tools.list_dir('encrypted')
                if not encrypted_files:
                    raise Exception("No encrypted file found")
                
                encrypted_file_path = os.path.join('encrypted', encrypted_files[0])
                logger.debug(f"Reading encrypted file: {encrypted_file_path}")
                
                with open(encrypted_file_path, 'rb') as f:
                    encrypted_data = f.read()
                if not encrypted_data:
                    raise Exception("Encrypted file is empty")
                    
                encrypted_b64 = base64.b64encode(encrypted_data).decode('utf-8')
                logger.debug("Encrypted file converted to base64 successfully")
            except Exception as e:
                logger.error(f"Error reading encrypted file: {str(e)}")
                raise Exception(f"Failed to read encrypted file: {str(e)}")
            
            logger.debug("=== File share request completed successfully ===")
            return jsonify({
                'status': 'success',
                'message': 'File encrypted and ready to share',
                'key': key_b64,
                'encrypted_file': encrypted_b64,
                'filename': filename,
                'file_size': len(encrypted_data)
            })
            
        except Exception as e:
            logger.error(f"Error during encryption process: {str(e)}")
            # Clean up the uploaded file if encryption fails
            safe_remove_file(file_path)
            return jsonify({'status': 'error', 'message': f'Encryption failed: {str(e)}'}), 500
            
    except Exception as e:
        logger.error(f"Unexpected error in share_file: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({'status': 'error', 'message': f'Server error: {str(e)}'}), 500

@app.route('/receive-file', methods=['POST'])
def receive_file():
    logger.debug("=== Starting file receive request ===")
    
    try:
        # Check if request is JSON
        if not request.is_json:
            logger.error("Request is not JSON")
            return jsonify({'status': 'error', 'message': 'Request must be JSON'}), 400
            
        data = request.get_json()
        if not data:
            logger.error("No JSON data received")
            return jsonify({'status': 'error', 'message': 'No JSON data'}), 400
            
        # Check required fields
        required_fields = ['encrypted_file', 'key', 'filename']
        for field in required_fields:
            if field not in data:
                logger.error(f"Missing required field: {field}")
                return jsonify({'status': 'error', 'message': f'Missing required field: {field}'}), 400
            
        encrypted_b64 = data['encrypted_file']
        key_b64 = data['key']
        original_filename = data['filename']
        filename = secure_filename(original_filename)
        
        if not filename:
            logger.error("Invalid filename after securing")
            return jsonify({'status': 'error', 'message': 'Invalid filename'}), 400
        
        logger.debug(f"Receiving file: {filename}")
        
        # Define paths with unique names
        encrypted_file_raw_data_path = os.path.join('raw_data', 'store_in_me.enc')
        key_path = os.path.join(app.config['UPLOAD_KEY'], f'{filename}.key')
        
        try:
            # Clean up any existing files with similar names
            potential_conflict = os.path.join('raw_data', 'store_in_me.enc')
            safe_remove_file(potential_conflict)
            potential_conflict = os.path.join(app.config['UPLOAD_FOLDER'], 'store_in_me.enc')
            safe_remove_file(potential_conflict)
            
            # Decode and save the encrypted file
            try:
                if not encrypted_b64:
                    raise Exception("No encrypted file data provided")
                    
                encrypted_data = base64.b64decode(encrypted_b64)
                if not encrypted_data:
                    raise Exception("Decoded encrypted data is empty")
                    
                # Ensure raw_data directory exists
                os.makedirs('raw_data', exist_ok=True)
                    
                with open(encrypted_file_raw_data_path, 'wb') as f:
                    f.write(encrypted_data)
                logger.debug(f"Encrypted file saved to: {encrypted_file_raw_data_path} ({len(encrypted_data)} bytes)")
            except Exception as e:
                logger.error(f"Error saving encrypted file: {str(e)}")
                return jsonify({'status': 'error', 'message': f'Failed to process encrypted file: {str(e)}'}), 400
            
            # Decode and save the key
            try:
                if not key_b64:
                    raise Exception("No key data provided")
                    
                key_data = base64.b64decode(key_b64)
                if not key_data:
                    raise Exception("Decoded key data is empty")
                
                # Ensure key directory exists
                os.makedirs(app.config['UPLOAD_KEY'], exist_ok=True)
                    
                with open(key_path, 'wb') as f:
                    f.write(key_data)
                logger.debug(f"Key saved to: {key_path} ({len(key_data)} bytes)")
            except Exception as e:
                logger.error(f"Error saving key: {str(e)}")
                safe_remove_file(encrypted_file_raw_data_path)
                return jsonify({'status': 'error', 'message': f'Failed to process key: {str(e)}'}), 400
            
            # Decrypt the file
            try:
                logger.debug("Starting decryption process")
                decrypted_path = decrypt_file(encrypted_file_raw_data_path, key_path)
                logger.debug(f"File decrypted to: {decrypted_path}")
            except Exception as e:
                logger.error(f"Decryption failed: {str(e)}")
                safe_remove_file(encrypted_file_raw_data_path)
                safe_remove_file(key_path)
                return jsonify({'status': 'error', 'message': f'File decryption failed: {str(e)}'}), 500
            
            # Move the decrypted file to received_files directory
            try:
                # Ensure received_files directory exists
                os.makedirs('received_files', exist_ok=True)
                
                # Use the original filename for the final file
                received_path = os.path.join('received_files', original_filename)
                
                # If file exists, create a unique name
                counter = 1
                while os.path.exists(received_path):
                    base_name, ext = os.path.splitext(original_filename)
                    received_path = os.path.join('received_files', f"{base_name}_{counter}{ext}")
                    counter += 1
                
                shutil.move(decrypted_path, received_path)
                final_filename = os.path.basename(received_path)
                logger.debug(f"Decrypted file moved to: {received_path}")
            except Exception as e:
                logger.error(f"Error moving decrypted file: {str(e)}")
                safe_remove_file(encrypted_file_raw_data_path)
                safe_remove_file(key_path)
                return jsonify({'status': 'error', 'message': f'Failed to save final file: {str(e)}'}), 500
            
            # Clean up temporary files
            safe_remove_file(encrypted_file_raw_data_path)
            safe_remove_file(key_path)
            
            logger.debug("=== File receive request completed successfully ===")
            return jsonify({
                'status': 'success',
                'message': 'File received and decrypted successfully',
                'filename': final_filename
            })
            
        except Exception as e:
            logger.error(f"Error during file processing: {str(e)}")
            # Clean up any partial files
            safe_remove_file(encrypted_file_raw_data_path)
            safe_remove_file(key_path)
            return jsonify({'status': 'error', 'message': f'Processing failed: {str(e)}'}), 500
            
    except Exception as e:
        logger.error(f"Unexpected error in receive_file: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({'status': 'error', 'message': f'Server error: {str(e)}'}), 500

@app.route('/received-files')
def get_received_files():
    try:
        files = []
        if os.path.exists('received_files'):
            files = os.listdir('received_files')
        return jsonify({'files': files})
    except Exception as e:
        logger.error(f"Error in get_received_files: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/download/<filename>')
def download_file(filename):
    try:
        file_path = os.path.join('received_files', filename)
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            return jsonify({'status': 'error', 'message': 'File not found'}), 404
            
        return send_file(file_path, as_attachment=True)
    except Exception as e:
        logger.error(f"Error in download_file: {str(e)}")
        return jsonify({'status': 'error', 'message': 'Download failed'}), 500

if __name__ == '__main__':
    logger.info("Starting Flask application...")
    app.run(host='0.0.0.0', port=8000, debug=True, threaded=True)