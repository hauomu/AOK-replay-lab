"""Exact-first decoder selection with corpus-validated compatibility mappings."""

# Paired-decoder evidence: docs/protocol_compatibility_validation.json.
COMPATIBLE_PROTOCOLS = {
    39576: 51702, 47185: 51702, 48258: 51702,
    94137: 93333, 95841: 95299, 96826: 95299, 96883: 95299,
}


class UnsupportedReplayBuild(ImportError):
    """No decoder for this replay's base build: s2protocol needs an update."""

    def __init__(self, base_build: int):
        super().__init__(f"protocol{base_build}")
        self.base_build = base_build


def select_protocol(versions, base_build: int):
    """Return (decoder, decoder build); callers must disclose mapped decoding."""
    base_build = int(base_build)
    try:
        return versions.build(base_build), base_build
    except ImportError as exc:
        expected = f"protocol{base_build}"
        missing = str(exc) == expected or getattr(exc, "name", None) in {
            expected, f"s2protocol.versions.{expected}",
        }
        target = COMPATIBLE_PROTOCOLS.get(base_build)
        if not missing:
            raise
        if target is None:
            raise UnsupportedReplayBuild(base_build) from exc
        return versions.build(target), target
