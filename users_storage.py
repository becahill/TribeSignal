import hashlib
import os

class UserHashTable:
    def __init__(self, capacity=10):
        self.capacity = capacity
        self.size = 0
        # Initialize buckets with empty lists to handle collisions
        self.buckets = [[] for _ in range(self.capacity)]

    def _hash(self, username: str) -> int:
        """Custom hash function using polynomial rolling hash algorithm."""
        hash_value = 0
        prime = 31
        for char in username:
            hash_value = (hash_value * prime + ord(char)) % self.capacity
        return hash_value

    def _hash_password(self, password: str, salt: bytes = None) -> tuple[str, str]:
        """Hashes a password using SHA-256 and a random salt."""
        if salt is None:
            salt = os.urandom(16)  # Generate 16-byte salt
        
        # Combine salt and password, then hash
        pwd_hash = hashlib.pbkdf2_hmac(
            'sha256', 
            password.encode('utf-8'), 
            salt, 
            100000
        )
        return pwd_hash.hex(), salt.hex()

    def register(self, username: str, password: str) -> bool:
        """Adds a username and hashed password. Returns False if user exists."""
        index = self._hash(username)
        bucket = self.buckets[index]

        # Check if username already exists in the bucket
        for item in bucket:
            if item['username'] == username:
                return False  # Username already taken

        # Hash password and store in bucket
        pwd_hash, salt = self._hash_password(password)
        bucket.append({
            'username': username,
            'password_hash': pwd_hash,
            'salt': salt
        })
        self.size += 1
        return True

    def authenticate(self, username: str, password: str) -> bool:
        """Verifies if the provided username and password match."""
        index = self._hash(username)
        bucket = self.buckets[index]

        for item in bucket:
            if item['username'] == username:
                # Retrieve salt and re-hash entered password to check for match
                salt = bytes.fromhex(item['salt'])
                pwd_hash, _ = self._hash_password(password, salt)
                return pwd_hash == item['password_hash']

        return False  # User not found

    def delete(self, username: str) -> bool:
        """Removes a user from the hash table."""
        index = self._hash(username)
        bucket = self.buckets[index]

        for i, item in enumerate(bucket):
            if item['username'] == username:
                del bucket[i]
                self.size -= 1
                return True
        return False