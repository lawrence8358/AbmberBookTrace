from __future__ import annotations

import sys
import traceback

from .core import UserInputError


def main() -> None:
    try:
        from .webapp import launch_web_app

        launch_web_app()
    except UserInputError as error:  # Keep the console open (the launcher pauses) so the message can be read.
        print(f"BookTrace 小幫手無法啟動：{error}", file=sys.stderr)
        sys.exit(1)
    except Exception:
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
