import os
import hashlib
import requests

class MD5:
    def __init__(self, game_path, url):
        self.game_path = game_path
        self.url = url
        self.prefix_to_remove = f"files/www/{url}/unlocker/files/"
        self.hashes_url = f"https://{url}/unlocker/hashes.txt"
        self.server_hashes = self._load_server_hashes()

    def _load_server_hashes(self):
        try:
            response = requests.get(self.hashes_url, timeout=10) 
            response.raise_for_status()
            if not response.text.strip():
                print("Server hashes file is empty.")
                return None

            lines = response.text.splitlines()
            hashes = {}
            for line in lines:
                parts = line.split(None, 1)
                if len(parts) == 2:
                    server_hash, file_path = parts
                    clean_path = file_path.replace(self.prefix_to_remove, "")
                    hashes[clean_path] = server_hash
                else:
                    print(f"Warning: Malformed line in hashes.txt: {line}")
            return hashes
        except requests.exceptions.Timeout:
            print(f"Timeout while trying to load server hashes from {self.hashes_url}")
            return None
        except requests.RequestException as e:
            print(f"Error loading server hashes from {self.hashes_url}: {e}")
            return None
        except ValueError as e:
            print(f"ValueError processing server hashes: {e}")
            return None

    def calculate_md5(self, file_path):
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    def check_files(self):
        if self.server_hashes is None:
            print("Server hashes not available, cannot check for mismatched files.")
            return []

        mismatched_folders = []

        for relative_path, server_hash in self.server_hashes.items():
            local_path = os.path.join(self.game_path, relative_path)

            if os.path.isfile(local_path):
                local_hash = self.calculate_md5(local_path)
                if local_hash != server_hash:
                    print(f"MD5 mismatch: Local '{local_path}' ({local_hash}) != Server ({server_hash})")
                    folder = os.path.dirname(relative_path)
                    if folder not in mismatched_folders:
                        mismatched_folders.append(folder)

        if mismatched_folders:
            print(f"MD5 check found mismatched folders: {mismatched_folders}")
        else:
            print("MD5 check: No mismatched files found or server hashes unavailable.")
        return mismatched_folders
