import os
import sys
from pathlib import Path

from cryptography.fernet import Fernet


def decrypt_env_files(encrypted_folder="environments", key_file="secret.key"):
    # Paths
    encrypted_folder = Path(encrypted_folder)
    decrypted_folder = (
        encrypted_folder / "decrypted"
    )  # Create decrypted folder inside encrypted folder
    key_file = Path(key_file)

    # Check if directories exist
    if not encrypted_folder.exists():
        print("ERROR: Encrypted folder does not exist.")
        sys.exit(1)
    if not key_file.exists():
        print("ERROR: Key file (secret.key) is missing.")
        sys.exit(1)

    # Load the decryption key
    with key_file.open("rb") as key_fp:
        key = key_fp.read()
    cipher = Fernet(key)

    # Create decrypted folder inside encrypted folder if it doesn't exist
    decrypted_folder.mkdir(exist_ok=True, parents=True)

    # Decrypt each .env.enc file
    for file in encrypted_folder.glob("*.env.enc"):
        try:
            # Read the encrypted .env.enc file
            with file.open("rb") as f:
                encrypted_data = f.read()

            # Decrypt the data
            decrypted_data = cipher.decrypt(encrypted_data)

            # Save to decrypted_env/ folder without .enc extension
            decrypted_file = decrypted_folder / file.stem
            with decrypted_file.open("wb") as f:
                f.write(decrypted_data)

            print(f"SUCCESS: Decrypted {file.name} -> {decrypted_file.name}")
        except Exception as e:
            print(f"ERROR: Failed to decrypt {file.name}: {str(e)}")
            sys.exit(1)


if __name__ == "__main__":
    decrypt_env_files()
