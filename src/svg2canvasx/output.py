import json
from pathlib import Path
import tempfile


def write_json_file(path, data, pretty=False):
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=str(output_path.parent),
        delete=False,
    ) as handle:
        json.dump(
            data,
            handle,
            ensure_ascii=True,
            indent=2 if pretty else None,
            sort_keys=False,
        )
        handle.write("\n")
        temp_path = Path(handle.name)
    temp_path.replace(output_path)

