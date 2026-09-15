from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "samples"


def sample_frames(label: str) -> list[Path]:
    return sorted((SAMPLES / label).glob("*.png"))
