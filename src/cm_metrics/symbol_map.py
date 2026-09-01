def parse_symbols_file(filepath: str) -> dict[str, str]:
    mapping: dict[str, str] = {}
    with open(filepath) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            original = line
            if "/" in line:
                base = line.split("/")[0]
            else:
                base = line
            mapping[base.strip().lower()] = original

    if not mapping:
        raise ValueError(f"No valid symbols found in {filepath}")

    return mapping
