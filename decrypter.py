import tools
import base64
from cryptography.fernet import Fernet, MultiFernet
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305, AESGCM, AESCCM
import os
from flask import jsonify

def Algo1(key):
    try:
        # Ensure key is in the correct format
        if isinstance(key, str):
            key = key.encode()
            
        # If key is not in PEM format, try to decode it as base64
        if not key.startswith(b'-----BEGIN'):
            try:
                # Add padding if needed
                padding = 4 - (len(key) % 4)
                if padding != 4:
                    key = key + b'=' * padding
                # First try to decode as base64
                decoded_key = base64.urlsafe_b64decode(key)
                # Then encode it back to ensure it's in the correct format
                key = base64.urlsafe_b64encode(decoded_key)
            except:
                # If decoding fails, try to encode the original key
                key = base64.urlsafe_b64encode(key)
        
        # Verify key length
        if len(base64.urlsafe_b64decode(key)) != 32:
            raise ValueError("Invalid key length. Key must be 32 bytes when decoded.")
        
        f = Fernet(key)
        with open("raw_data/store_in_me.enc", "rb") as target_file:
            secret_data = target_file.read()
        data = f.decrypt(secret_data)
        return data
    except Exception as e:
        raise ValueError(f"Decryption failed: {str(e)}")

def Algo1_extented(filename, key1, key2):
    try:
        # Ensure keys are in the correct format
        if isinstance(key1, str):
            key1 = key1.encode()
        if isinstance(key2, str):
            key2 = key2.encode()
            
        # If keys are not in PEM format, try to decode them as base64
        if not key1.startswith(b'-----BEGIN'):
            try:
                decoded_key1 = base64.urlsafe_b64decode(key1)
                key1 = base64.urlsafe_b64encode(decoded_key1)
            except:
                key1 = base64.urlsafe_b64encode(key1)
                
        if not key2.startswith(b'-----BEGIN'):
            try:
                decoded_key2 = base64.urlsafe_b64decode(key2)
                key2 = base64.urlsafe_b64encode(decoded_key2)
            except:
                key2 = base64.urlsafe_b64encode(key2)
            
        f = MultiFernet([Fernet(key1), Fernet(key2)])
        source_filename = 'encrypted/' + filename
        target_filename = 'files/' + filename

        with open(source_filename, 'rb') as file:
            raw = file.read()
        secret_data = f.decrypt(raw)
        
        with open(target_filename, 'wb') as target_file:
            target_file.write(secret_data)
    except Exception as e:
        raise ValueError(f"Decryption failed for {filename}: {str(e)}")

def Algo2(filename, key, nonce):
    try:
        aad = b"authenticated but unencrypted data"
        chacha = ChaCha20Poly1305(key)
        source_filename = 'encrypted/' + filename
        target_filename = 'files/' + filename

        with open(source_filename, 'rb') as file:
            raw = file.read()
        secret_data = chacha.decrypt(nonce, raw, aad)

        with open(target_filename, 'wb') as target_file:
            target_file.write(secret_data)
    except Exception as e:
        raise ValueError(f"Decryption failed for {filename}: {str(e)}")

def Algo3(filename, key, nonce):
    try:
        aad = b"authenticated but unencrypted data"
        aesgcm = AESGCM(key)
        source_filename = 'encrypted/' + filename
        target_filename = 'files/' + filename

        with open(source_filename, 'rb') as file:
            raw = file.read()
        secret_data = aesgcm.decrypt(nonce, raw, aad)

        with open(target_filename, 'wb') as target_file:
            target_file.write(secret_data)
    except Exception as e:
        raise ValueError(f"Decryption failed for {filename}: {str(e)}")

def Algo4(filename, key, nonce):
    try:
        aad = b"authenticated but unencrypted data"
        aesccm = AESCCM(key)
        source_filename = 'encrypted/' + filename
        target_filename = 'files/' + filename

        with open(source_filename, 'rb') as file:
            raw = file.read()
        secret_data = aesccm.decrypt(nonce, raw, aad)

        with open(target_filename, 'wb') as target_file:
            target_file.write(secret_data)
    except Exception as e:
        raise ValueError(f"Decryption failed for {filename}: {str(e)}")

def decrypter():
    try:
        tools.empty_folder('files')

        # Load encrypted key data from key/ directory
        list_directory = tools.list_dir('key')
        if not list_directory:
            raise ValueError("No key file found in key directory")
            
        filename = './key/' + list_directory[0]
        with open(filename, "rb") as public_key:
            key_1 = public_key.read()

        # Ensure key is in the correct format
        if not key_1.startswith(b'-----BEGIN'):
            try:
                decoded_key = base64.urlsafe_b64decode(key_1)
                key_1 = base64.urlsafe_b64encode(decoded_key)
            except:
                key_1 = base64.urlsafe_b64encode(key_1)

        # Decrypt the key information
        try:
            secret_information = Algo1(key_1)
        except Exception as e:
            raise ValueError(f"Failed to decrypt key information: {str(e)}")

        try:
            list_information = secret_information.split(b':::::')
        except Exception as e:
            raise ValueError(f"Failed to parse key information: {str(e)}")

        if len(list_information) != 7:
            raise ValueError("Invalid key information format")

        try:
            # Decode base64 values back into original binary keys and nonces
            key_1_1 = base64.urlsafe_b64decode(list_information[0])
            key_1_2 = base64.urlsafe_b64decode(list_information[1])
            key_2   = base64.urlsafe_b64decode(list_information[2])
            key_3   = base64.urlsafe_b64decode(list_information[3])
            key_4   = base64.urlsafe_b64decode(list_information[4])
            nonce12 = base64.urlsafe_b64decode(list_information[5])
            nonce13 = base64.urlsafe_b64decode(list_information[6])
        except Exception as e:
            raise ValueError(f"Failed to decode key components: {str(e)}")

        files = sorted(tools.list_dir('encrypted'))
        if not files:
            raise ValueError("No encrypted files found")

        for index in range(len(files)):
            try:
                if index % 4 == 0:
                    Algo1_extented(files[index], key_1_1, key_1_2)
                elif index % 4 == 1:
                    Algo2(files[index], key_2, nonce12)
                elif index % 4 == 2:
                    Algo3(files[index], key_3, nonce12)
                else:
                    Algo4(files[index], key_4, nonce13)
            except Exception as e:
                raise ValueError(f"Failed to decrypt file {files[index]}: {str(e)}")
                
        # Clean the key directory before saving the new key
        for f in os.listdir(app.config['UPLOAD_KEY']):
            safe_remove_file(os.path.join(app.config['UPLOAD_KEY'], f))

        key_path = os.path.join(app.config['UPLOAD_KEY'], 'received.key')
        try:
            if not key_1:
                raise Exception("No key data provided")
            
            key_data = base64.b64decode(key_1)
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
                
    except Exception as e:
        raise ValueError(f"Decryption process failed: {str(e)}")
