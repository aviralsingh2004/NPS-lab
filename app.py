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
app.secret_key = os.urandom(24)

# Create necessary directories
for directory in [UPLOAD_FOLDER, UPLOAD_KEY, 'files', 'encrypted', 'restored_file', 'raw_data', 'received_files']:
    os.makedirs(directory, exist_ok=True)

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
    except:
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

def encrypt_file(file_path):
    """Encrypt a file and return the key path"""
    try:
        logger.debug(f"Starting encryption of file: {file_path}")
        
        # Save file to uploads directory
        filename = os.path.basename(file_path)
        upload_path = os.path.join(UPLOAD_FOLDER, filename)
        
        # Ensure the file exists
        if not os.path.exists(file_path):
            raise Exception(f"Source file not found: {file_path}")
            
        # Move the file to uploads directory
        os.rename(file_path, upload_path)
        logger.debug(f"File moved to uploads: {upload_path}")
        
        # Clear any existing files in the necessary directories
        tools.empty_folder('files')
        tools.empty_folder('encrypted')
        tools.empty_folder('key')
        
        # Encrypt the file
        dv.divide()
        enc.encrypter()
        
        # Get the generated key
        list_directory = tools.list_dir('key')
        if not list_directory:
            raise Exception("No key generated during encryption")
        
        key_path = os.path.join('key', list_directory[0])
        logger.debug(f"Encryption completed. Key path: {key_path}")
        
        return key_path
    except Exception as e:
        logger.error(f"Error in encrypt_file: {str(e)}")
        raise

def decrypt_file(file_path, key_path):
    """Decrypt a file using the provided key"""
    try:
        logger.debug(f"Starting decryption of file: {file_path} with key: {key_path}")
        
        # Save the encrypted file
        filename = os.path.basename(file_path)
        upload_path = os.path.join(UPLOAD_FOLDER, filename)
        
        # Ensure the file exists
        if not os.path.exists(file_path):
            raise Exception(f"Source file not found: {file_path}")
            
        # Move the file to uploads directory
        os.rename(file_path, upload_path)
        logger.debug(f"File moved to uploads: {upload_path}")
        
        # Save the key
        key_filename = os.path.basename(key_path)
        key_upload_path = os.path.join(UPLOAD_KEY, key_filename)
        
        # Ensure the key exists
        if not os.path.exists(key_path):
            raise Exception(f"Key file not found: {key_path}")
            
        # Move the key to key directory
        os.rename(key_path, key_upload_path)
        logger.debug(f"Key moved to key directory: {key_upload_path}")
        
        # Clear any existing files in the necessary directories
        tools.empty_folder('restored_file')
        tools.empty_folder('raw_data')
        
        # Decrypt the file
        dec.decrypter()
        rst.restore()
        
        # Get the decrypted file
        list_directory = tools.list_dir('restored_file')
        if not list_directory:
            raise Exception("No file restored after decryption")
        
        decrypted_path = os.path.join('restored_file', list_directory[0])
        logger.debug(f"Decryption completed. File path: {decrypted_path}")
        
        return decrypted_path
    except Exception as e:
        logger.error(f"Error in decrypt_file: {str(e)}")
        raise

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
                requests.post(f'http://{ip}:8000/peer-connected', 
                            json={'peer': get_local_ip()},
                            timeout=5)
            except:
                pass  # Ignore if notification fails
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
            return jsonify({'status': 'success'})
    except Exception as e:
        logger.error(f"Error in peer_connected: {str(e)}")
    return jsonify({'status': 'error'}), 400

@app.route('/get-connections')
def get_connections():
    return jsonify({'connections': list(peer_connections.keys())})

@app.route('/ping')
def ping():
    return jsonify({'status': 'success'})

@app.route('/share-file', methods=['POST'])
def share_file():
    try:
        logger.debug("Received file share request")
        
        if 'file' not in request.files:
            logger.error("No file part in request")
            return jsonify({'status': 'error', 'message': 'No file part'}), 400
            
        file = request.files['file']
        if file.filename == '':
            logger.error("No selected file")
            return jsonify({'status': 'error', 'message': 'No selected file'}), 400
            
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            
            # Save the file
            file.save(file_path)
            logger.debug(f"File saved to: {file_path}")
            
            try:
                # Encrypt the file
                key_path = encrypt_file(file_path)
                logger.debug(f"File encrypted successfully, key path: {key_path}")
                
                # Read the key
                with open(key_path, 'rb') as f:
                    key_data = f.read()
                
                # Convert key to base64 for transmission
                key_b64 = base64.b64encode(key_data).decode('utf-8')
                logger.debug("Key converted to base64")
                
                # Read the encrypted file
                encrypted_files = tools.list_dir('encrypted')
                if not encrypted_files:
                    raise Exception("No encrypted file found")
                
                encrypted_file_path = os.path.join('encrypted', encrypted_files[0])
                with open(encrypted_file_path, 'rb') as f:
                    encrypted_data = f.read()
                
                # Convert encrypted file to base64
                encrypted_b64 = base64.b64encode(encrypted_data).decode('utf-8')
                logger.debug("Encrypted file converted to base64")
                
                return jsonify({
                    'status': 'success',
                    'message': 'File encrypted and ready to share',
                    'key': key_b64,
                    'encrypted_file': encrypted_b64,
                    'filename': filename
                })
            except Exception as e:
                logger.error(f"Error during encryption process: {str(e)}")
                # Clean up any partial files
                if os.path.exists(file_path):
                    os.remove(file_path)
                raise
            
        logger.error(f"Invalid file format: {file.filename}")
        return jsonify({'status': 'error', 'message': 'Invalid file format'}), 400
    except Exception as e:
        logger.error(f"Error in share_file: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/receive-file', methods=['POST'])
def receive_file():
    try:
        logger.debug("Received file receive request")
        
        if not request.is_json:
            logger.error("Request is not JSON")
            return jsonify({'status': 'error', 'message': 'Invalid request format'}), 400
            
        data = request.get_json()
        if 'encrypted_file' not in data or 'key' not in data or 'filename' not in data:
            logger.error("Missing required data")
            return jsonify({'status': 'error', 'message': 'Missing required data'}), 400
            
        encrypted_b64 = data['encrypted_file']
        key_b64 = data['key']
        filename = secure_filename(data['filename'])
        
        try:
            # Save the encrypted file
            encrypted_data = base64.b64decode(encrypted_b64)
            encrypted_file_path = os.path.join('raw_data', 'store_in_me.enc')
            with open(encrypted_file_path, 'wb') as f:
                f.write(encrypted_data)
            logger.debug(f"Encrypted file saved to: {encrypted_file_path}")
            
            # Save the key
            key_data = base64.b64decode(key_b64)
            key_path = os.path.join(app.config['UPLOAD_KEY'], f'{filename}.key')
            with open(key_path, 'wb') as f:
                f.write(key_data)
            logger.debug(f"Key saved to: {key_path}")
            
            # Decrypt the file
            decrypted_path = decrypt_file(encrypted_file_path, key_path)
            logger.debug(f"File decrypted to: {decrypted_path}")
            
            # Move the decrypted file to received_files directory
            received_filename = os.path.basename(decrypted_path)
            received_path = os.path.join('received_files', received_filename)
            os.rename(decrypted_path, received_path)
            logger.debug(f"Decrypted file moved to: {received_path}")
            
            return jsonify({
                'status': 'success',
                'message': 'File decrypted successfully',
                'filename': received_filename
            })
        except Exception as e:
            logger.error(f"Error during decryption process: {str(e)}")
            # Clean up any partial files
            if os.path.exists(encrypted_file_path):
                os.remove(encrypted_file_path)
            if os.path.exists(key_path):
                os.remove(key_path)
            raise
            
    except Exception as e:
        logger.error(f"Error in receive_file: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/received-files')
def get_received_files():
    try:
        files = os.listdir('received_files')
        return jsonify({'files': files})
    except Exception as e:
        logger.error(f"Error in get_received_files: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/download/<filename>')
def download_file(filename):
    try:
        return send_file(
            os.path.join('received_files', filename),
            as_attachment=True
        )
    except Exception as e:
        logger.error(f"Error in download_file: {str(e)}")
        return str(e), 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)
