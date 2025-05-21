import socket
import json
import threading
import ssl
import os
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
import datetime

class KeySharing:
    def __init__(self, port=5001):
        self.port = port
        self.private_key = None
        self.public_key = None
        self.server_socket = None
        self.running = False
        self.shared_keys = {}
        self.cert_path = "server.crt"
        self.key_path = "server.key"
        
    def _create_self_signed_cert(self):
        # Generate key
        if not self.private_key:
            self.private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048
            )
            self.public_key = self.private_key.public_key()

        # Generate self-signed certificate
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, u"localhost")
        ])
        
        cert = x509.CertificateBuilder().subject_name(
            subject
        ).issuer_name(
            issuer
        ).public_key(
            self.public_key
        ).serial_number(
            x509.random_serial_number()
        ).not_valid_before(
            datetime.datetime.utcnow()
        ).not_valid_after(
            datetime.datetime.utcnow() + datetime.timedelta(days=10)
        ).add_extension(
            x509.SubjectAlternativeName([
                x509.DNSName(u"localhost")
            ]),
            critical=False,
        ).sign(self.private_key, hashes.SHA256())
        
        # Create directories if they don't exist
        os.makedirs('certs', exist_ok=True)
        
        # Save certificate
        cert_path = os.path.join('certs', self.cert_path)
        key_path = os.path.join('certs', self.key_path)
        
        # Save certificate and private key
        with open(cert_path, "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))
            
        with open(key_path, "wb") as f:
            f.write(self.private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            ))
            
        return cert_path, key_path
        
    def start(self):
        self.running = True
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind(('0.0.0.0', self.port))
        self.server_socket.listen(5)
        
        # Create SSL context
        self.context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        cert_path, key_path = self._create_self_signed_cert()
        self.context.load_cert_chain(certfile=cert_path, keyfile=key_path)
        
        # Start listening thread
        self.listen_thread = threading.Thread(target=self._listen_loop)
        self.listen_thread.daemon = True
        self.listen_thread.start()

    def stop(self):
        self.running = False
        if self.server_socket:
            self.server_socket.close()

    def _listen_loop(self):
        while self.running:
            try:
                client_socket, addr = self.server_socket.accept()
                ssl_socket = self.context.wrap_socket(client_socket, server_side=True)
                client_thread = threading.Thread(
                    target=self._handle_client,
                    args=(ssl_socket, addr)
                )
                client_thread.daemon = True
                client_thread.start()
            except Exception as e:
                if self.running:
                    print(f"Error accepting connection: {e}")

    def _handle_client(self, ssl_socket, addr):
        try:
            data = ssl_socket.recv(4096)
            message = json.loads(data.decode())
            
            if message['type'] == 'key_share':
                # Store the received key
                self.shared_keys[addr[0]] = message['key']
                
                # Send acknowledgment
                response = {
                    'type': 'ack',
                    'status': 'success'
                }
                ssl_socket.send(json.dumps(response).encode())
                
        except Exception as e:
            print(f"Error handling client {addr}: {e}")
        finally:
            ssl_socket.close()

    def share_key(self, peer_addr, key_data):
        """Share a key with a peer"""
        try:
            # Create SSL context for client
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            
            # Connect to peer
            with socket.create_connection((peer_addr, self.port)) as sock:
                with context.wrap_socket(sock, server_hostname=peer_addr) as ssl_socket:
                    # Send key data
                    message = {
                        'type': 'key_share',
                        'key': key_data
                    }
                    ssl_socket.send(json.dumps(message).encode())
                    
                    # Wait for acknowledgment
                    response = json.loads(ssl_socket.recv(4096).decode())
                    return response['status'] == 'success'
                    
        except Exception as e:
            print(f"Error sharing key with {peer_addr}: {e}")
            return False

    def get_shared_key(self, peer_addr):
        """Get a key shared by a peer"""
        return self.shared_keys.get(peer_addr) 