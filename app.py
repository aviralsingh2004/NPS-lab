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

@app.route('/upload-key', methods=['POST'])
def upload_key_file():
    if 'file' not in request.files:
        return jsonify({'status': 'error', 'message': 'No file part'}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({'status': 'error', 'message': 'No selected file'}), 400
        
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_KEY'], filename))
        return jsonify({'status': 'success', 'message': 'Key file uploaded successfully'})
    return jsonify({'status': 'error', 'message': 'Invalid file format'}), 400

@app.route('/share-key/<peer_ip>', methods=['POST'])
def share_key_with_peer(peer_ip):
    try:
        # Get the key file
        list_directory = tools.list_dir('key')
        if not list_directory:
            return jsonify({'status': 'error', 'message': 'No key file available. Please encrypt a file first.'}), 400
            
        key_path = './key/' + list_directory[0]
        with open(key_path, 'rb') as f:
            key_data = f.read()
            
        # Ensure key is in the correct format before sending
        if not key_data.startswith(b'-----BEGIN'):
            try:
                # First try to decode as base64
                decoded_key = base64.urlsafe_b64decode(key_data)
                # Then encode it back to ensure it's in the correct format
                key_data = base64.urlsafe_b64encode(decoded_key)
            except:
                # If decoding fails, try to encode the original key
                key_data = base64.urlsafe_b64encode(key_data)
        
        # Convert key to base64 string for transmission
        key_b64 = base64.b64encode(key_data).decode('utf-8')
        
        # Send key to peer
        response = requests.post(
            f'http://{peer_ip}:8000/receive-key',
            json={'key_data': key_b64}  # Send as JSON instead of file
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
        if not request.is_json:
            return jsonify({'status': 'error', 'message': 'Invalid request format'}), 400
            
        data = request.get_json()
        if 'key_data' not in data:
            return jsonify({'status': 'error', 'message': 'No key data received'}), 400
            
        # Decode the base64 key data
        try:
            key_data = base64.b64decode(data['key_data'])
        except:
            return jsonify({'status': 'error', 'message': 'Invalid key format'}), 400
            
        # Ensure key is in the correct format
        if not key_data.startswith(b'-----BEGIN'):
            try:
                # First try to decode as base64
                decoded_key = base64.urlsafe_b64decode(key_data)
                # Then encode it back to ensure it's in the correct format
                key_data = base64.urlsafe_b64encode(decoded_key)
            except:
                # If decoding fails, try to encode the original key
                key_data = base64.urlsafe_b64encode(key_data)
            
        # Save the received key
        os.makedirs('received_keys', exist_ok=True)
        sender_ip = request.remote_addr
        key_path = os.path.join('received_keys', f'key_from_{sender_ip}.pem')
        with open(key_path, 'wb') as f:
            f.write(key_data)
        
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

@app.route('/download-received-key/<peer_ip>')
def download_received_key(peer_ip):
    try:
        key_path = os.path.join('received_keys', f'key_from_{peer_ip}.pem')
        if not os.path.exists(key_path):
            flash('No key found from this peer')
            return redirect(url_for('connect'))
            
        return send_file(
            key_path,
            download_name=f'key_from_{peer_ip}.pem',
            as_attachment=True
        )
    except Exception as e:
        flash(f'Error downloading key: {str(e)}')
        return redirect(url_for('connect'))

@app.route('/use-shared-key/<peer_ip>', methods=['POST'])
def use_shared_key(peer_ip):
    try:
        key_path = os.path.join('received_keys', f'key_from_{peer_ip}.pem')
        if not os.path.exists(key_path):
            return jsonify({'status': 'error', 'message': 'No key found from this peer'}), 404
            
        # Read the key data
        with open(key_path, 'rb') as f:
            key_data = f.read()
            
        # Ensure key is in the correct format
        if not key_data.startswith(b'-----BEGIN'):
            try:
                # First try to decode as base64
                decoded_key = base64.urlsafe_b64decode(key_data)
                # Then encode it back to ensure it's in the correct format
                key_data = base64.urlsafe_b64encode(decoded_key)
            except:
                # If decoding fails, try to encode the original key
                key_data = base64.urlsafe_b64encode(key_data)
            
        # Copy the key to the key directory
        tools.empty_folder('key')
        with open(os.path.join('key', 'received_key.pem'), 'wb') as f:
            f.write(key_data)
            
        return jsonify({'status': 'success', 'message': 'Key ready to use. You can now decrypt files.'})
        
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

@app.route('/check-key-status')
def check_key_status():
    try:
        list_directory = tools.list_dir('key')
        has_key = len(list_directory) > 0
        return jsonify({'hasKey': has_key})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/download_data', methods=['GET', 'POST'])
def upload_key():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
            
        file = request.files['file']
        if file.filename == '':
            flash('No selected file')
            return 'NO FILE SELECTED'
            
        # Check if we need to handle a key file
        if 'keyFile' in request.files and request.files['keyFile'].filename != '':
            key_file = request.files['keyFile']
            if key_file and allowed_file(key_file.filename):
                tools.empty_folder('key')
                filename = secure_filename(key_file.filename)
                key_path = os.path.join(app.config['UPLOAD_KEY'], filename)
                key_file.save(key_path)
                
                # Verify key format
                try:
                    with open(key_path, 'rb') as f:
                        key_data = f.read()
                    if not key_data.startswith(b'-----BEGIN'):
                        try:
                            decoded_key = base64.urlsafe_b64decode(key_data)
                            key_data = base64.urlsafe_b64encode(decoded_key)
                            with open(key_path, 'wb') as f:
                                f.write(key_data)
                        except:
                            key_data = base64.urlsafe_b64encode(key_data)
                            with open(key_path, 'wb') as f:
                                f.write(key_data)
                except Exception as e:
                    flash(f'Error processing key file: {str(e)}')
                    return redirect(request.url)
        
        # Save the encrypted file
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        
        # Check if we have a key before proceeding
        list_directory = tools.list_dir('key')
        if not list_directory:
            flash('No key available. Please upload a key file or use a shared key.')
            return redirect(request.url)
            
        try:
            # Verify key format before decryption
            key_path = os.path.join('key', list_directory[0])
            with open(key_path, 'rb') as f:
                key_data = f.read()
            if not key_data.startswith(b'-----BEGIN'):
                try:
                    decoded_key = base64.urlsafe_b64decode(key_data)
                    key_data = base64.urlsafe_b64encode(decoded_key)
                    with open(key_path, 'wb') as f:
                        f.write(key_data)
                except:
                    key_data = base64.urlsafe_b64encode(key_data)
                    with open(key_path, 'wb') as f:
                        f.write(key_data)
            
            return start_decryption()
        except ValueError as e:
            flash(f'Decryption failed: {str(e)}')
            return redirect(request.url)
        except Exception as e:
            flash(f'An error occurred: {str(e)}')
            return redirect(request.url)
    return redirect('/')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)
