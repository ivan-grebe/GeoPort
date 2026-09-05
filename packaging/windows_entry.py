"""Entry point for the standalone Windows executable."""

import multiprocessing

if __name__ == "__main__":
    multiprocessing.freeze_support()

    from geoport.__main__ import main

    main()
