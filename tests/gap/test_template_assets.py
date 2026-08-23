from hashlib import sha256
from pathlib import Path


def _file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def test_canonical_template_assets_exist():
    root = Path(__file__).parents[2]
    expected_files = [
        root / "test_data/examples/wildcat-pflotran/model/TEMP-0.in",
        root / "test_data/examples/wildcat-pflotran/include/TEMP_GRD.grdecl",
        root / "test_data/examples/wildcat-pflotran/include/tops_dz.inc",
    ]

    for file_path in expected_files:
        assert file_path.exists(), f"Missing canonical template asset: {file_path}"


def test_canonical_template_assets_hashes():
    root = Path(__file__).parents[2]
    expected_hashes = {
        root / "test_data/examples/wildcat-pflotran/model/TEMP-0.in": "4b38c3d19222d4b0797b1f3b0eddb85c39d9e16bb3cf13a07607ed47a80518d8",
        root / "test_data/examples/wildcat-pflotran/include/TEMP_GRD.grdecl": "588b1004cdc5e75362208bd7ca9cda8d4f712018bf8263662d1fbdd80e5b2ce3",
        root / "test_data/examples/wildcat-pflotran/include/tops_dz.inc": "8b5a09f464d63e5579c108c94e5f52ee778dc1f204f7759d41a0ef061e7e207d",
    }

    for file_path, expected_hash in expected_hashes.items():
        assert _file_sha256(file_path) == expected_hash
