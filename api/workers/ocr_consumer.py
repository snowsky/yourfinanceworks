"""OCR Consumer — entry point delegating to api/workers/ocr/ subpackage."""
from workers.ocr import *  # noqa: F401, F403
from workers.ocr.consumer import main, main_async  # noqa: F401

if __name__ == "__main__":
    import sys
    sys.exit(main())
