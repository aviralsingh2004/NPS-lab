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

UPLOAD_FOLDER = './uploads/'
UPLOAD_KEY = './key/'
ALLOWED_EXTENSIONS = {'pem'}

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['UPLOAD_KEY'] = UPLOAD_KEY
app.secret_key = os.urandom(24)

# Create necessary directories
for directory in [UPLOAD_FOLDER, UPLOAD_KEY, 'files', 'encrypted', 'restored_file', 'raw_data']:
    os.makedirs(directory, exist_ok=True)

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

@app.route('/share-key/<peer_ip>', methods=['POST'])
def share_key_with_peer(peer_ip):
    try:
        # Get the key file
        list_directory = tools.list_dir('key')
        if not list_directory:
            return jsonify({'status': 'error', 'message': 'No key file available'}), 400
            
        key_path = './key/' + list_directory[0]
        with open(key_path, 'rb') as f:
            key_data = f.read()
            
        # Send key to peer
        response = requests.post(
            f'http://{peer_ip}:8000/receive-key',
            files={'key': ('key.pem', key_data)}
        )
        
        if response.status_code == 200:
            return jsonify({'status': 'success', 'message': f'Key shared with {peer_ip}'})
        else:
            return jsonify({'status': 'error', 'message': 'Failed to share key'}), 500
            
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/receive-key', methods=['POST'])
def receive_key():
    try:
        if 'key' not in request.files:
            return jsonify({'status': 'error', 'message': 'No key file received'}), 400
            
        key_file = request.files['key']
        if key_file.filename == '':
            return jsonify({'status': 'error', 'message': 'No key file selected'}), 400
            
        # Save the received key
        os.makedirs('received_keys', exist_ok=True)
        sender_ip = request.remote_addr
        key_path = os.path.join('received_keys', f'key_from_{sender_ip}.pem')
        key_file.save(key_path)
        
        return jsonify({'status': 'success', 'message': 'Key received successfully'})
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/received-keys')
def get_received_keys():
    try:
        os.makedirs('received_keys', exist_ok=True)
        keys = []
        for filename in os.listdir('received_keys'):
            if filename.startswith('key_from_') and filename.endswith('.pem'):
                ip = filename[9:-4]  # Extract IP from filename
                keys.append(ip)
        return jsonify({'keys': keys})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/use-shared-key/<peer_ip>', methods=['POST'])
def use_shared_key(peer_ip):
    try:
        key_path = os.path.join('received_keys', f'key_from_{peer_ip}.pem')
        if not os.path.exists(key_path):
            return jsonify({'status': 'error', 'message': 'No key found from this peer'}), 404
            
        # Copy the key to the key directory
        tools.empty_folder('key')
        with open(key_path, 'rb') as src, open(os.path.join('key', 'received_key.pem'), 'wb') as dst:
            dst.write(src.read())
            
        return jsonify({'status': 'success', 'message': 'Key ready to use'})
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

def start_encryption():
    dv.divide()
    tools.empty_folder('uploads')
    enc.encrypter()
    return render_template('success.html')

def start_decryption():
    dec.decrypter()
    tools.empty_folder('key')
    rst.restore()
    return render_template('restore_success.html')

@app.route('/return-key/My_Key.pem')
def return_key():
    list_directory = tools.list_dir('key')
    filename = './key/' + list_directory[0]
    return send_file(filename, download_name='My_Key.pem', as_attachment=True)

@app.route('/return-file/')
def return_file():
    list_directory = tools.list_dir('restored_file')
    filename = './restored_file/' + list_directory[0]
    print("****************************************")
    print(list_directory[0])
    print("****************************************")
    return send_file(filename, download_name=list_directory[0], as_attachment=True)

@app.route('/download/')
def downloads():
    return render_template('download.html')

@app.route('/upload')
def call_page_upload():
    return render_template('upload.html')

@app.route('/home')
def back_home():
    tools.empty_folder('key')
    tools.empty_folder('restored_file')
    return render_template('index.html')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/network')
def network():
    return render_template('network.html')

@app.route('/data', methods=['GET', 'POST'])
def upload_file():
    tools.empty_folder('uploads')
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            flash('No selected file')
            return 'NO FILE SELECTED'
        if file:
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            return start_encryption()
        return 'Invalid File Format!'
    return redirect('/')

@app.route('/download_data', methods=['GET', 'POST'])
def upload_key():
    tools.empty_folder('key')
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            flash('No selected file')
            return 'NO FILE SELECTED'
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_KEY'], filename))
            return start_decryption()
        return 'Invalid File Format!'
    return redirect('/')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)
