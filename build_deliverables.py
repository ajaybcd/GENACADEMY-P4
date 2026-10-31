"""Compatibility command for finalizing participant-approved deliverables."""
from pathlib import Path
import runpy

if __name__ == '__main__':
    runpy.run_path(str(Path(__file__).with_name('finalize_submission.py')), run_name='__main__')
