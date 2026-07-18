import os
import sys
from pathlib import Path

from cryptography.fernet import Fernet


def encrypt_env_files(
    decrypted_folder="environments/decrypted",
    encrypted_folder="environments",
    key_file="secret.key",
):
    # Paths
    decrypted_folder = Path(decrypted_folder)
    encrypted_folder = Path(encrypted_folder)
    key_file = Path(key_file)

    # Check if directories exist
    if not decrypted_folder.exists():
        print("ERROR: Decrypted folder does not exist.")
        sys.exit(1)
    if not key_file.exists():
        print("ERROR: Key file (secret.key) is missing.")
        sys.exit(1)

    # Load the encryption key
    with key_file.open("rb") as key_fp:
        key = key_fp.read()
    cipher = Fernet(key)

    # Create encrypted folder if it doesn't exist
    encrypted_folder.mkdir(exist_ok=True)

    # Encrypt each .env file
    for file in decrypted_folder.glob("*.env"):
        try:
            # Read the decrypted .env file
            with file.open("rb") as f:
                data = f.read()

            # Encrypt the data
            encrypted_data = cipher.encrypt(data)

            # Save to encrypted/ folder with .enc extension
            encrypted_file = encrypted_folder / f"{file.stem}.env.enc"
            with encrypted_file.open("wb") as f:
                f.write(encrypted_data)

            print(f"SUCCESS: Encrypted {file.name} -> {encrypted_file.name}")
        except Exception as e:
            print(f"ERROR: Failed to encrypt {file.name}: {str(e)}")
            sys.exit(1)


if __name__ == "__main__":
    encrypt_env_files()
