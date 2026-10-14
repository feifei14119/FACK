"""Content-addressed assembly snapshots for tuning evidence (no GPU work)."""
import hashlib
import os
import tempfile


def save_assembly(text: str, out_store: str):
    data = text.encode("utf-8")
    digest = hashlib.sha256(data).hexdigest()
    directory = os.path.join(out_store, "artifacts")
    os.makedirs(directory, exist_ok=True)
    path = os.path.abspath(os.path.join(directory, digest + ".s"))
    if os.path.exists(path):
        with open(path, "rb") as f:
            if f.read() != data:
                raise ValueError("assembly archive digest mismatch: " + path)
    else:
        fd, temporary = tempfile.mkstemp(prefix=".assembly-", dir=directory)
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(data)
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    return {"path": path, "sha256": digest, "size_bytes": len(data)}
