"""List or extract selected members of a remote .zip over HTTP range requests (stdlib only).

Lets us take BIRD's train question file and a handful of databases without downloading the
full 8.9GB train archive: ``zipfile`` only needs random access, which a Range-capable HTTP
server provides.

    python scripts/remote_zip.py URL --list [--nested INNER.zip]
    python scripts/remote_zip.py URL --extract MEMBER [MEMBER ...] --out DIR [--nested INNER.zip]
"""

from __future__ import annotations

import argparse
import io
import shutil
import urllib.request
import zipfile
from pathlib import Path
from typing import IO


class HttpRangeFile(io.RawIOBase):
    """Seekable, read-only file object backed by HTTP Range requests."""

    def __init__(self, url: str):
        self.url = url
        self.pos = 0
        request = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(request, timeout=60) as response:
            self.size = int(response.headers["Content-Length"])

    def seekable(self) -> bool:
        return True

    def readable(self) -> bool:
        return True

    def tell(self) -> int:
        return self.pos

    def seek(self, offset: int, whence: int = io.SEEK_SET) -> int:
        base = {io.SEEK_SET: 0, io.SEEK_CUR: self.pos, io.SEEK_END: self.size}[whence]
        self.pos = base + offset
        return self.pos

    def read(self, size: int = -1) -> bytes:
        if size is None or size < 0:
            size = self.size - self.pos
        if size == 0 or self.pos >= self.size:
            return b""
        end = min(self.pos + size, self.size) - 1
        request = urllib.request.Request(self.url, headers={"Range": f"bytes={self.pos}-{end}"})
        with urllib.request.urlopen(request, timeout=300) as response:
            data: bytes = response.read()
        self.pos += len(data)
        return data

    def readinto(self, buffer: bytearray | memoryview) -> int:  # type: ignore[override]
        data = self.read(len(buffer))
        buffer[: len(data)] = data
        return len(data)


def open_archive(url: str, nested: str | None) -> zipfile.ZipFile:
    outer = zipfile.ZipFile(io.BufferedReader(HttpRangeFile(url), buffer_size=1 << 20))
    if nested is None:
        return outer
    info = outer.getinfo(nested)
    if info.compress_type != zipfile.ZIP_STORED:
        raise SystemExit(f"{nested} is compressed inside the outer zip; random access impossible")
    handle: IO[bytes] = outer.open(nested)  # stored members are seekable
    return zipfile.ZipFile(handle)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("--nested", help="Inner .zip member to open (must be stored)")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--extract", nargs="*", default=[])
    parser.add_argument("--out", type=Path, default=Path("."))
    args = parser.parse_args()
    archive = open_archive(args.url, args.nested)
    if args.list:
        for info in archive.infolist():
            method = "stored" if info.compress_type == zipfile.ZIP_STORED else "deflated"
            print(f"{info.file_size:>14,} {info.compress_size:>14,} {method:8} {info.filename}")
    for prefix in args.extract:
        for info in archive.infolist():
            if info.filename.startswith(prefix) and not info.is_dir():
                target = args.out / info.filename
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info) as source, target.open("wb") as sink:
                    shutil.copyfileobj(source, sink, 1 << 20)
                print(f"extracted {info.filename} ({info.file_size:,} bytes)")


if __name__ == "__main__":
    main()
