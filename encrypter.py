import tools
import os
import base64
from cryptography.fernet import Fernet, MultiFernet
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.ciphers.aead import AESCCM

def Algo1(data, key):
    f = Fernet(key)
    with open("raw_data/store_in_me.enc", "wb") as target_file:
        secret_data = f.encrypt(data)
        target_file.write(secret_data)

def Algo1_extented(filename, key1, key2):
    f = MultiFernet([Fernet(key1), Fernet(key2)])
    source_filename = 'files/' + filename
    target_filename = 'encrypted/' + filename

    with open(source_filename, 'rb') as file:
        raw = file.read()  # Read entire file content
    secret_data = f.encrypt(raw)

    with open(target_filename, 'wb') as target_file:
        target_file.write(secret_data)

def Algo2(filename, key, nonce):
    aad = b"authenticated but unencrypted data"
    chacha = ChaCha20Poly1305(key)
    source_filename = 'files/' + filename
    target_filename = 'encrypted/' + filename

    with open(source_filename, 'rb') as file:
        raw = file.read()
    secret_data = chacha.encrypt(nonce, raw, aad)

    with open(target_filename, 'wb') as target_file:
        target_file.write(secret_data)

def Algo3(filename, key, nonce):
    aad = b"authenticated but unencrypted data"
    aesgcm = AESGCM(key)
    source_filename = 'files/' + filename
    target_filename = 'encrypted/' + filename

    with open(source_filename, 'rb') as file:
        raw = file.read()
    secret_data = aesgcm.encrypt(nonce, raw, aad)

    with open(target_filename, 'wb') as target_file:
        target_file.write(secret_data)

def Algo4(filename, key, nonce):
    aad = b"authenticated but unencrypted data"
    aesccm = AESCCM(key)
    source_filename = 'files/' + filename
    target_filename = 'encrypted/' + filename

    with open(source_filename, 'rb') as file:
        raw = file.read()
    secret_data = aesccm.encrypt(nonce, raw, aad)

    with open(target_filename, 'wb') as target_file:
        target_file.write(secret_data)

def encrypter():
    tools.empty_folder('key')
    tools.empty_folder('encrypted')

    # Generate encryption keys
    key_1 = Fernet.generate_key()
    key_1_1 = Fernet.generate_key()
    key_1_2 = Fernet.generate_key()
    key_2 = ChaCha20Poly1305.generate_key()
    key_3 = AESGCM.generate_key(bit_length=128)
    key_4 = AESCCM.generate_key(bit_length=128)

    # Generate nonces
    nonce13 = os.urandom(13)
    nonce12 = os.urandom(12)

    # Process the files in the 'files' directory
    files = sorted(tools.list_dir('files'))
    for index, filename in enumerate(files):
        if index % 4 == 0:
            Algo1_extented(filename, key_1_1, key_1_2)
        elif index % 4 == 1:
            Algo2(filename, key_2, nonce12)
        elif index % 4 == 2:
            Algo3(filename, key_3, nonce12)
        else:
            Algo4(filename, key_4, nonce13)

    # Encode all keys and nonces to base64 to avoid decode errors
    secret_information = (
        base64.urlsafe_b64encode(key_1_1).decode() + ":::::" +
        base64.urlsafe_b64encode(key_1_2).decode() + ":::::" +
        base64.urlsafe_b64encode(key_2).decode() + ":::::" +
        base64.urlsafe_b64encode(key_3).decode() + ":::::" +
        base64.urlsafe_b64encode(key_4).decode() + ":::::" +
        base64.urlsafe_b64encode(nonce12).decode() + ":::::" +
        base64.urlsafe_b64encode(nonce13).decode()
    )

    # Encrypt the key information and store it
    Algo1(secret_information.encode(), key_1)

    # Write the public key to a PEM file
    with open("./key/Taale_Ki_Chabhi.pem", "wb") as public_key:
        public_key.write(key_1)

    # Clean up the 'files' folder
    tools.empty_folder('files')
