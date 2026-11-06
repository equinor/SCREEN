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
        root / "test_data/examples/wildcat-pflotran/model/TEMP-0.in": "a709723d98d939bd0efc7a12b8728849d219ea5a03396b2196f8c53670535086",
        root / "test_data/examples/wildcat-pflotran/include/TEMP_GRD.grdecl": "d4aabda9f7f87a2dd4dfa42f21cceb3be87877a39b084321291ee3a0cd53ca5c",
        root / "test_data/examples/wildcat-pflotran/include/tops_dz.inc": "8b5a09f464d63e5579c108c94e5f52ee778dc1f204f7759d41a0ef061e7e207d",
    }

    for file_path, expected_hash in expected_hashes.items():
        assert _file_sha256(file_path) == expected_hash
