#!/usr/bin/env python
# -*- coding: utf-8 -*-
# -*- mode: python -*-
import sys
from setuptools import setup

if sys.version_info[:2] < (3, 6):
    raise RuntimeError("Python version 3.6 or greater required.")

setup(
    entry_points={'console_scripts': ['oeaudio-present = oeaudio.script:main']},
)
