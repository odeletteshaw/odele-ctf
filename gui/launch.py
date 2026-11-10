"""Open the supervision console.

    python -m gui.launch                     # empty console; press ＋ to add sessions
    python -m gui.launch web sqli_login      # open with one session already running
    python -m gui.launch crypto rsa_wiener

Each session runs the solve in its own subprocess. Needs DEEPSEEK_API_KEY (see .env).
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gui.app import ConsoleApp  # noqa: E402
from gui.manager import Manager  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("category", nargs="?", choices=["web", "crypto"])
    parser.add_argument("challenge", nargs="?")
    args = parser.parse_args()

    manager = Manager()
    app = ConsoleApp(manager)
    if args.category and args.challenge:
        spec = {"kind": "benchmark", "category": args.category, "name": args.challenge}
        app.add_session(manager.new_session(spec, args.challenge, args.category))
    app.run()


if __name__ == "__main__":
    main()
