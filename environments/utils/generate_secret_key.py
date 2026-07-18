from pathlib import Path

from cryptography.fernet import Fernet


def generate_key(key_path="secret.key"):
    """
    Generates a secret key and saves it to a file.

    Args:
        key_path (str): The file path where the secret key will be saved.
    """
    key = Fernet.generate_key()  # Generate a new secret key
    key_file_path = Path(key_path)

    # Check if the key file already exists to avoid accidental overwrites
    if key_file_path.exists():
        print(
            f"Error: {key_path} already exists. Delete or rename the file and try again."
        )
        return

    # Save the key securely
    try:
        with key_file_path.open("wb") as key_file:
            key_file.write(key)
        print(f"Secret key successfully generated and saved to {key_path}")
    except Exception as e:
        print(f"Error: Failed to save the secret key. {str(e)}")


if __name__ == "__main__":
    generate_key()
