"""Run GeoPort from source or as a standalone executable."""

import multiprocessing

if __name__ == "__main__":
    multiprocessing.freeze_support()

    from geoport.__main__ import main

    main()
