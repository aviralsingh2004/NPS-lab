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

UPLOAD_FOLDER = './uploads/'
UPLOAD_KEY = './key/'
ALLOWED_EXTENSIONS = {'pem', 'txt', 'pdf', 'doc', 'docx', 'jpg', 'jpeg', 'png'}

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['UPLOAD_KEY'] = UPLOAD_KEY
app.secret_key = os.urandom(24)

# Create necessary directories
for directory in [UPLOAD_FOLDER, UPLOAD_KEY, 'files', 'encrypted', 'restored_file', 'raw_data', 'received_files']:
    os.makedirs(directory, exist_ok=True)

# Store connected peers
connected_peers = {}

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

def encrypt_file(file_path):
    """Encrypt a file and return the key path"""
    # Save file to uploads directory
    filename = os.path.basename(file_path)
    upload_path = os.path.join(UPLOAD_FOLDER, filename)
    os.rename(file_path, upload_path)
    
    # Encrypt the file
    dv.divide()
    enc.encrypter()
    
    # Get the generated key
    list_directory = tools.list_dir('key')
    if not list_directory:
        raise Exception("No key generated during encryption")
    
    return os.path.join('key', list_directory[0])

def decrypt_file(file_path, key_path):
    """Decrypt a file using the provided key"""
    # Save the encrypted file
    filename = os.path.basename(file_path)
    upload_path = os.path.join(UPLOAD_FOLDER, filename)
    os.rename(file_path, upload_path)
    
    # Save the key
    key_filename = os.path.basename(key_path)
    key_upload_path = os.path.join(UPLOAD_KEY, key_filename)
    os.rename(key_path, key_upload_path)
    
    # Decrypt the file
    dec.decrypter()
    rst.restore()
    
    # Get the decrypted file
    list_directory = tools.list_dir('restored_file')
    if not list_directory:
        raise Exception("No file restored after decryption")
    
    return os.path.join('restored_file', list_directory[0])

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
        response = requests.get(f'http://{ip}:8000/ping', timeout=2)
        if response.status_code == 200:
            return jsonify({'status': 'success', 'message': 'Connection successful'})
    except RequestException:
        pass
    return jsonify({'status': 'error', 'message': 'Could not connect to device'})

@app.route('/ping')
def ping():
    return jsonify({'status': 'success'})

@app.route('/share-file', methods=['POST'])
def share_file():
    try:
        if 'file' not in request.files:
            return jsonify({'status': 'error', 'message': 'No file part'}), 400
            
        file = request.files['file']
        if file.filename == '':
            return jsonify({'status': 'error', 'message': 'No selected file'}), 400
            
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            
            # Encrypt the file
            key_path = encrypt_file(file_path)
            
            # Read the key
            with open(key_path, 'rb') as f:
                key_data = f.read()
            
            # Convert key to base64 for transmission
            key_b64 = base64.b64encode(key_data).decode('utf-8')
            
            return jsonify({
                'status': 'success',
                'message': 'File encrypted and ready to share',
                'key': key_b64
            })
            
        return jsonify({'status': 'error', 'message': 'Invalid file format'}), 400
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/receive-file', methods=['POST'])
def receive_file():
    try:
        if 'file' not in request.files or 'key' not in request.form:
            return jsonify({'status': 'error', 'message': 'Missing file or key'}), 400
            
        file = request.files['file']
        key_b64 = request.form['key']
        
        if file.filename == '':
            return jsonify({'status': 'error', 'message': 'No selected file'}), 400
            
        if file and allowed_file(file.filename):
            # Save the encrypted file
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            
            # Save the key
            key_data = base64.b64decode(key_b64)
            key_path = os.path.join(app.config['UPLOAD_KEY'], 'received_key.pem')
            with open(key_path, 'wb') as f:
                f.write(key_data)
            
            # Decrypt the file
            decrypted_path = decrypt_file(file_path, key_path)
            
            return jsonify({
                'status': 'success',
                'message': 'File decrypted successfully',
                'filename': os.path.basename(decrypted_path)
            })
            
        return jsonify({'status': 'error', 'message': 'Invalid file format'}), 400
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/download/<filename>')
def download_file(filename):
    try:
        return send_file(
            os.path.join('restored_file', filename),
            as_attachment=True
        )
    except Exception as e:
        return str(e), 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)
