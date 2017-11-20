# -*- coding: utf-8 -*-
#
# Copyright © Spyder Project Contributors
# Licensed under the terms of the MIT License
#

"""
File for running tests programmatically.
"""

import pytest


def main():
    """
    Run pytest tests.
    """
    errno = pytest.main(['-x', 'gwhat',  '-v', '-rw', '--durations=10',
                         '--cov=gwhat'])

    if errno != 0:
        raise SystemExit(errno)


if __name__ == '__main__':
    main()