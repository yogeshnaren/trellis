"""Stream a zip nested (deflated) inside a remote zip, extracting chosen members sequentially.

BIRD's train.zip deflates train_databases.zip inside it, so random access is impossible; but a
zip can be read front-to-back via its local file headers. Stopping once every wanted database
has been extracted means only the archive *prefix* up to the last wanted database is fetched.
Note: in BIRD's train archive the per-database description CSVs come much later than the
.sqlite files, so ``--want`` stops after each wanted database's .sqlite file.
Handles macOS-style entries whose sizes live in a trailing data descriptor.

    python scripts/stream_inner_zip.py URL INNER --list-until-bytes N
    python scripts/stream_inner_zip.py URL INNER --want DIR/ [DIR/ ...] --out DIR

``URL`` may be ``-`` to read the *outer* zip sequentially from stdin, e.g. piped from one
fast ``curl`` download instead of many slow range requests. With ``--until-end`` the whole
inner archive is scanned (needed when wanted files, like BIRD's description CSVs, sit late),
and ``--listing FILE`` records every member's offset and size for later selective fetches.

    curl -sfL URL | python scripts/stream_inner_zip.py - INNER --until-end \\
        --want DIR/ ... --out DIR --listing listing.tsv
"""

from __future__ import annotations

import argparse
import io
import struct
import sys
import zipfile
import zlib
from pathlib import Path
from typing import IO, BinaryIO

sys.path.insert(0, str(Path(__file__).parent))
from remote_zip import HttpRangeFile

LOCAL_HEADER = b"PK\x03\x04"
DESCRIPTOR = b"PK\x07\x08"
CHUNK = 4 << 20


class PushbackStream:
    """Sequential reader with an unread buffer, counting consumed bytes."""

    def __init__(self, raw: IO[bytes]):
        self.raw = raw
        self.buffer = b""
        self.consumed = 0

    def read(self, n: int) -> bytes:
        if len(self.buffer) < n:
            self.buffer += self.raw.read(max(n - len(self.buffer), CHUNK))
        data, self.buffer = self.buffer[:n], self.buffer[n:]
        self.consumed += len(data)
        return data

    def read_exact(self, n: int) -> bytes:
        data = self.read(n)
        if len(data) != n:
            raise EOFError
        return data

    def unread(self, data: bytes) -> None:
        self.buffer = data + self.buffer
        self.consumed -= len(data)


ZIP64_MARKER = 0xFFFFFFFF


def zip64_sizes(extra: bytes, csize: int, usize: int) -> tuple[int, int, bool]:
    """Resolve 0xFFFFFFFF size placeholders from a local header's ZIP64 extra field.

    Members over 4GB (e.g. BIRD's bike_share_1.sqlite) store their real sizes in extra
    block 0x0001 (uncompressed then compressed, 8 bytes each); trusting the placeholder
    desynchronises the stream.
    """
    offset = 0
    while offset + 4 <= len(extra):
        block_id, size = struct.unpack_from("<HH", extra, offset)
        if block_id == 0x0001:
            data = extra[offset + 4 : offset + 4 + size]
            values = [struct.unpack_from("<Q", data, i)[0] for i in range(0, len(data) - 7, 8)]
            if usize == ZIP64_MARKER and values:
                usize = values.pop(0)
            if csize == ZIP64_MARKER and values:
                csize = values.pop(0)
            return csize, usize, True
        offset += 4 + size
    return csize, usize, False


def copy_member(
    stream: PushbackStream,
    method: int,
    flags: int,
    csize: int,
    sink: BinaryIO | None,
    zip64: bool = False,
) -> None:
    """Consume one member's data (and descriptor), writing decompressed bytes to sink."""
    if not flags & 0x08:
        decompressor = zlib.decompressobj(-15) if method == 8 else None
        remaining = csize
        while remaining:
            chunk = stream.read_exact(min(remaining, CHUNK))
            remaining -= len(chunk)
            if sink:
                sink.write(decompressor.decompress(chunk) if decompressor else chunk)
        if sink and decompressor:
            sink.write(decompressor.flush())
        return
    if method != 8:
        raise SystemExit("stored entry with data descriptor: unsupported")
    decompressor = zlib.decompressobj(-15)
    while not decompressor.eof:
        chunk = stream.read(CHUNK)
        if not chunk:
            raise EOFError
        out = decompressor.decompress(chunk)
        if sink:
            sink.write(out)
    stream.unread(decompressor.unused_data)
    head = stream.read_exact(4)
    sizes = 16 if zip64 else 8  # two 8-byte sizes for ZIP64 members, else two 4-byte ones
    # [signature] crc, csize, usize; without the optional signature, ``head`` was the crc.
    stream.read_exact(4 + sizes if head == DESCRIPTOR else sizes)


class InflatingReader:
    """File-like view of one deflated zip member read sequentially from a stream."""

    def __init__(self, source: PushbackStream):
        self.source = source
        self.decompressor = zlib.decompressobj(-15)
        self.pending = b""

    def read(self, n: int) -> bytes:
        while len(self.pending) < n and not self.decompressor.eof:
            chunk = self.source.read(CHUNK)
            if not chunk:
                break
            self.pending += self.decompressor.decompress(chunk)
        data, self.pending = self.pending[:n], self.pending[n:]
        return data


def open_inner_from_stdin(inner: str) -> IO[bytes] | InflatingReader:
    """Walk the outer zip on stdin to the named member and return a stream of its bytes."""
    outer = PushbackStream(sys.stdin.buffer)
    while True:
        if outer.read(4) != LOCAL_HEADER:
            raise SystemExit(f"{inner} not found in outer archive")
        _, flags, method, _, _, _, csize, _usize, name_len, extra_len = struct.unpack(
            "<HHHHHIIIHH", outer.read_exact(26)
        )
        name = outer.read_exact(name_len).decode("utf-8", "replace")
        outer.read_exact(extra_len)
        if name == inner:
            if method != 8:
                raise SystemExit(f"{inner}: expected a deflated member")
            return InflatingReader(outer)
        copy_member(outer, method, flags, csize, None)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("inner")
    parser.add_argument("--list-until-bytes", type=int)
    parser.add_argument("--want", nargs="*", default=[])
    parser.add_argument("--out", type=Path, default=Path("."))
    parser.add_argument("--until-end", action="store_true", help="Scan the whole archive")
    parser.add_argument("--listing", type=Path, help="Write offset/size/name of every member")
    args = parser.parse_args()

    if args.url == "-":
        stream = PushbackStream(open_inner_from_stdin(args.inner))  # type: ignore[arg-type]
    else:
        outer = zipfile.ZipFile(io.BufferedReader(HttpRangeFile(args.url), buffer_size=CHUNK))
        stream = PushbackStream(outer.open(args.inner))
    pending = list(args.want)
    listing = args.listing.open("w") if args.listing else None
    while True:
        if args.list_until_bytes and stream.consumed > args.list_until_bytes:
            break
        if stream.read(4) != LOCAL_HEADER:
            break  # central directory reached
        _, flags, method, _, _, _, csize, usize, name_len, extra_len = struct.unpack(
            "<HHHHHIIIHH", stream.read_exact(26)
        )
        name = stream.read_exact(name_len).decode("utf-8", "replace")
        csize, usize, zip64 = zip64_sizes(stream.read_exact(extra_len), csize, usize)
        if listing and not name.startswith("__MACOSX"):
            listing.write(f"{stream.consumed}\t{usize}\t{name}\n")
            listing.flush()
        match = next((p for p in pending if name.startswith(p)), None)
        wanted = (
            match is not None
            and not name.endswith("/")
            and "__MACOSX" not in name
            and not name.endswith(".DS_Store")
        )
        if not name.startswith("__MACOSX"):
            print(f"{stream.consumed / 1e9:6.2f}GB {name}{'  <- extract' if wanted else ''}",
                  flush=True)
        if wanted:
            target = args.out / name
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("wb") as sink:
                copy_member(stream, method, flags, csize, sink, zip64)
            # Directory listings precede file data in this archive, so "done" means the
            # database file itself has been extracted, not that its directory was passed.
            if match and name.endswith(".sqlite") and not args.until_end:
                pending.remove(match)
                if not pending:
                    break
        else:
            copy_member(stream, method, flags, csize, None, zip64)


if __name__ == "__main__":
    main()
