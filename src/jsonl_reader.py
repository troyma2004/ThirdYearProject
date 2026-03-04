import json
from typing import Dict, Set, Any


class JSONLDataset:
    """
    A memory-efficient dataset that builds an index of file offsets.
    Allows O(1) random access to any line in a multi-GB JSONL file.
    """
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.file = open(filepath, 'r', encoding='utf-8')
        self.offsets = []
        self.negatives: Set[str] = set()
        self._build_index()

    def _build_index(self):
        """Scans the file once to record the byte offset of every line."""
        print(f"Indexing {self.filepath}...", end="", flush=True)
        self.file.seek(0)
        while True:
            offset = self.file.tell()
            line = self.file.readline()
            if not line:
                break
            content = json.loads(line)
            negatives = content.get("negatives", [])
            self.negatives.update(negatives)
            self.offsets.append(offset)
        print(f" Done! Found {len(self.offsets)} samples.")

    def __len__(self):
        return len(self.offsets)

    def __getitem__(self, idx: int) -> Dict[str, Any]:
        """Retrieves the line at index idx instantly."""
        if idx < 0 or idx >= len(self.offsets):
            raise IndexError("Index out of bounds")

        self.file.seek(self.offsets[idx])
        line = self.file.readline()
        return json.loads(line)

    def close(self):
        self.file.close()