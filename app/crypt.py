from cryptography.fernet import Fernet

# Password Encryption Functions

def generate_key():
    key = Fernet.generate_key()
    with open("secret.key", "wb") as key_file:
        key_file.write(key)

def load_key():
    return open("secret.key", "rb").read()

def encrypt(password):
    key = load_key()
    encoded_pass = password.encode()
    return Fernet(key).encrypt(encoded_pass).decode()

def decrypt(password):
    key = load_key()
    return Fernet(key).decrypt(password.encode()).decode()