"""A gzip of a tar of a gzip of a tar of the flag. Unwrap each layer. The outer layer is gzip
so the tar padding compresses away and the embedded blob stays small."""

import base64
import gzip
import io
import tarfile

DESCRIPTION = "An archive within an archive within an archive. Unwrap them and find the flag."


def make(flag: str) -> str:
    # innermost tar holding flag.txt
    inner = io.BytesIO()
    with tarfile.open(fileobj=inner, mode="w") as tf:
        d = flag.encode()
        ti = tarfile.TarInfo("flag.txt")
        ti.size = len(d)
        tf.addfile(ti, io.BytesIO(d))

    gz1 = gzip.compress(inner.getvalue())

    # middle tar holding inner.gz
    mid = io.BytesIO()
    with tarfile.open(fileobj=mid, mode="w") as tf:
        ti = tarfile.TarInfo("inner.gz")
        ti.size = len(gz1)
        tf.addfile(ti, io.BytesIO(gz1))

    # outer layer: gzip of the middle tar (compresses the tar record padding away)
    blob = gzip.compress(mid.getvalue())
    return f"{DESCRIPTION}\n\nfile (base64) = {base64.b64encode(blob).decode()}"
