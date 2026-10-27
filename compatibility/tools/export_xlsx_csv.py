"""Legacy-named entry for the shared, manifest-driven CSV exporter."""
from pathlib import Path
import argparse
import runpy

if __name__ == '__main__':
    argparse.ArgumentParser(description=__doc__).parse_args()
    runpy.run_path(str(Path(__file__).with_name('export_xlsx.py')), run_name='__main__')
