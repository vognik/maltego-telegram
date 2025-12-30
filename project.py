import sys
import io

import transforms
from extensions import registry
from maltego_trx.handler import handle_run
from maltego_trx.registry import register_transform_classes
from maltego_trx.server import app as application

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

register_transform_classes(transforms)

registry.write_transforms_config(include_output_entities=True)
registry.write_settings_config()
registry.write_local_mtz(
    mtz_path="./telegram.mtz",
    working_dir=".",
    command=r"python",
    params="project.py",
    debug=True,
)

if __name__ == "__main__":
    handle_run(__name__, sys.argv, application)
