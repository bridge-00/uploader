"""
VikingFile Uploader — Custom version for TORVIKING
Handles uploads with proper User-Agent headers to avoid 403 blocks.
"""

import sys
import os
import json
import mimetypes
import time
from urllib import request, error
from uuid import uuid4

# Use a browser-like User-Agent to avoid 403 blocks
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"


def format_size(size_in_bytes):
    if size_in_bytes < 1024:
        return f"{size_in_bytes} B"
    elif size_in_bytes < 1024**2:
        return f"{size_in_bytes / 1024:.1f} KB"
    elif size_in_bytes < 1024**3:
        return f"{size_in_bytes / 1024**2:.1f} MB"
    else:
        return f"{size_in_bytes / 1024**3:.1f} GB"


def display_progress(uploaded, total, start_time):
    if total == 0:
        return
    percent = uploaded / total
    elapsed = time.monotonic() - start_time
    speed = uploaded / elapsed if elapsed > 0 else 0
    eta = (total - uploaded) / speed if speed > 0 else 0
    bar_len = 30
    filled = int(bar_len * percent)
    bar = "█" * filled + "░" * (bar_len - filled)
    sys.stdout.write(
        f"\rUploading |{bar}| {percent:6.1%}  "
        f"{format_size(uploaded)}/{format_size(total)}  "
        f"@ {format_size(speed)}/s  ETA: {int(eta)}s"
    )
    sys.stdout.flush()


def get_upload_server():
    """Gets the upload server URL with proper headers."""
    url = "https://vikingfile.com/api/get-server"
    req = request.Request(url)
    req.add_header("User-Agent", USER_AGENT)
    req.add_header("Accept", "application/json, text/plain, */*")
    req.add_header("Referer", "https://vikingfile.com/")
    req.add_header("Origin", "https://vikingfile.com")

    try:
        with request.urlopen(req, timeout=30) as response:
            if response.status != 200:
                print(f"ERROR: Failed to get upload server (Status: {response.status})")
                return None
            data = json.load(response)
            server = data.get("server")
            print(f"Upload server: {server}")
            return server
    except error.HTTPError as e:
        print(f"ERROR: VikingFile API returned HTTP {e.code}: {e.reason}")
        try:
            body = e.read().decode("utf-8", "ignore")[:500]
            print(f"Response body: {body}")
        except Exception:
            pass
        return None
    except error.URLError as e:
        print(f"ERROR: Cannot connect to VikingFile API: {e.reason}")
        return None
    except Exception as e:
        print(f"ERROR: Unexpected error getting server: {e}")
        return None


def calculate_total_size(fields, files, boundary):
    total_size = 0
    for name, value in fields.items():
        total_size += len(f"--{boundary}\r\n".encode())
        total_size += len(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        total_size += len(f"{value}\r\n".encode())
    for name, filepath in files.items():
        filename = os.path.basename(filepath)
        mimetype = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        total_size += len(f"--{boundary}\r\n".encode())
        total_size += len(f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'.encode())
        total_size += len(f"Content-Type: {mimetype}\r\n\r\n".encode())
        total_size += os.path.getsize(filepath)
        total_size += len("\r\n".encode())
    total_size += len(f"--{boundary}--\r\n".encode())
    return total_size


def multipart_body_generator(fields, files, boundary, progress_callback=None):
    total_uploaded = 0
    for name, value in fields.items():
        header = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
            f"{value}\r\n"
        )
        yield header.encode()
    for name, filepath in files.items():
        filename = os.path.basename(filepath)
        mimetype = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        header = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'
            f"Content-Type: {mimetype}\r\n\r\n"
        )
        yield header.encode()
        file_size = os.path.getsize(filepath)
        with open(filepath, "rb") as f:
            while True:
                chunk = f.read(65536)  # 64KB chunks for faster upload
                if not chunk:
                    break
                yield chunk
                total_uploaded += len(chunk)
                if progress_callback:
                    progress_callback(total_uploaded, file_size)
        yield "\r\n".encode()
    yield f"--{boundary}--\r\n".encode()


def upload_file(file_path, user_hash="", path=""):
    """Uploads a file to VikingFile and returns the download link."""
    if not os.path.exists(file_path):
        print(f"ERROR: File not found: {file_path}")
        return None

    file_size = os.path.getsize(file_path)
    print(f"File: {os.path.basename(file_path)} ({format_size(file_size)})")

    upload_server_url = get_upload_server()
    if not upload_server_url:
        return None

    fields = {"user": user_hash, "path": path}
    files = {"file": file_path}

    boundary = f"----------{uuid4().hex}"
    content_type = f"multipart/form-data; boundary={boundary}"
    content_length = calculate_total_size(fields, files, boundary)

    start_time = time.monotonic()
    last_update = 0

    def progress_callback(uploaded, total):
        nonlocal last_update
        now = time.monotonic()
        if now - last_update > 0.1:
            display_progress(uploaded, total, start_time)
            last_update = now

    body_gen = multipart_body_generator(fields, files, boundary, progress_callback)

    req = request.Request(upload_server_url, data=body_gen)
    req.add_header("Content-Type", content_type)
    req.add_header("Content-Length", str(content_length))
    req.add_header("User-Agent", USER_AGENT)
    req.add_header("Accept", "application/json, text/plain, */*")
    req.add_header("Referer", "https://vikingfile.com/")
    req.add_header("Origin", "https://vikingfile.com")

    try:
        with request.urlopen(req, timeout=600) as response:
            display_progress(file_size, file_size, start_time)
            print()  # newline after progress bar
            if response.status == 200:
                raw = response.read().decode("utf-8")
                print(f"API response: {raw[:500]}")
                upload_info = json.loads(raw)
                url = upload_info.get("url")
                if url:
                    print(f"DOWNLOAD_LINK:{url}")
                    return url
                else:
                    print(f"ERROR: No 'url' field in response: {upload_info}")
                    return None
            else:
                print(f"ERROR: Upload failed with status {response.status}")
                return None
    except error.HTTPError as e:
        print(f"\nERROR: HTTP {e.code} during upload: {e.reason}")
        try:
            print(f"Response: {e.read().decode('utf-8', 'ignore')[:500]}")
        except Exception:
            pass
        return None
    except error.URLError as e:
        print(f"\nERROR: Connection failed during upload: {e.reason}")
        return None
    except Exception as e:
        print(f"\nERROR: Unexpected error during upload: {e}")
        return None


if __name__ == "__main__":
    file_to_upload = ""
    user_hash_arg = ""
    path_arg = ""

    if len(sys.argv) > 1:
        file_to_upload = sys.argv[1]
        if len(sys.argv) > 2:
            user_hash_arg = sys.argv[2]
        if len(sys.argv) > 3:
            path_arg = sys.argv[3]
    else:
        print("Usage: python upload.py <file_path> [user_hash] [folder]")
        sys.exit(1)

    if not file_to_upload.strip():
        print("ERROR: No file path provided.")
        sys.exit(1)

    download_link = upload_file(
        file_to_upload.strip(),
        user_hash_arg.strip(),
        path_arg.strip()
    )

    if download_link:
        print(f"\n✅ Upload successful!")
        print(f"📎 Link: {download_link}")
        sys.exit(0)
    else:
        print(f"\n❌ Upload failed!")
        sys.exit(1)
