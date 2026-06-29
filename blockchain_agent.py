# blockchain_agent.py
# Generates cryptographic hashes for document verification

import hashlib

def generate_document_hash(file_bytes):
    """
    Generates a SHA-256 digital fingerprint (hash) of the file.
    If even one pixel changes, this hash will be completely different.
    """
    try:
        # Create a new SHA-256 hash object
        sha256_hash = hashlib.sha256()
        
        # Feed the file bytes into the hash function
        sha256_hash.update(file_bytes)
        
        # Return the hexadecimal representation of the hash
        return sha256_hash.hexdigest()
    except Exception as e:
        return f"Error generating hash: {str(e)}"

if __name__ == "__main__":
    # Quick test if run directly
    print("Blockchain Hashing Agent Ready.")
