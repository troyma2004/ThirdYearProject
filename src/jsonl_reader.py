import json
from typing import Dict, Any


class JSONLDataset:
    """
    A memory-efficient dataset that builds an index of file offsets.
    Allows O(1) random access to any line in a multi-GB JSONL file.
    """
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.offsets = []
        self._file_handle = None

        self._build_index()    # Populate the offsets.

    def _build_index(self):
        """Scans the file once to record the byte offset of every valid line."""
        with open(self.filepath, mode="rb") as file:
            print(f"Indexing {self.filepath}...", end="", flush=True)
            file.seek(0)
            while True:
                offset = file.tell()
                line_bytes = file.readline()
                if not line_bytes:    # We break out of the loop if we've reached the EOF.
                    break

                if not line_bytes.strip():    # We skip the line if it's empty, i.e., '\n'.
                    continue

                self.offsets.append(offset)

        print(f" Done! Found {len(self.offsets)} samples.")

    def close(self):
        """Close the file handle when it's done."""
        if self._file_handle is not None:
            self._file_handle.close()
            self._file_handle = None


    def __len__(self):
        return len(self.offsets)

    def __getitem__(self, idx: int) -> Dict[str, Any]:
        """
        Retrieves the line at index idx instantly.
        Guarded with a read-forward fallback. In the case of reading a malformed JSON line,
        we skip that line and try to read the next line.
        """

        # Support negative indexing.
        if idx < 0:
            idx = len(self.offsets) + idx

        if idx < 0 or idx >= len(self.offsets):
            raise IndexError("Index out of bounds")

        if self._file_handle is None:
            self._file_handle = open(self.filepath, mode="rb")

        # Skip the problem if its JSON syntax was broken for some reason.
        original_index = idx
        while idx < len(self.offsets):
            try:
                self._file_handle.seek(self.offsets[idx])
                line_bytes = self._file_handle.readline()
                line = line_bytes.decode("utf-8")
                return json.loads(line)
            except (UnicodeDecodeError, json.JSONDecodeError):
                # Line is corrupted. Step forward to the next index.
                idx += 1

        raise RuntimeError(f"Could not find any valid JSON line from index {original_index} to EOF.")

    def __enter__(self):
        """Allows the dataset to be used in a 'with' statement"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Allows the dataset to be used in a 'with' statement"""
        self.close()

    def __del__(self):
        """Ensure the file handle is closed during garbage collection."""
        if self._file_handle is not None:
            self._file_handle.close()
            self._file_handle = None
