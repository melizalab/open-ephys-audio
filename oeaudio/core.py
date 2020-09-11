# -*- coding: utf-8 -*-
# -*- mode: python -*-

__version__ = "0.1.0"

import sounddevice as sd
import logging

log = logging.getLogger('oe-audio')   # root logger


def device_index():
    """ Returns the numerical index of the current default device """
    return sd.default.device[0]


def device_properties():
    """Returns properties of the current device"""
    return sd.query_devices()[device_index()]


def open_stimuli(files):
    """Opens a sequence of sound files.

    Throws a RuntimeError if a file does not exist or if sampling rates and
    channel counts are not identical

    """
    import soundfile as sf
    log.info("Loading stimuli:")
    data = []
    for fname in files:
        f = sf.SoundFile(fname)
        log.info(" - %s: %.2f s (channels=%d, samplerate=%d)",
                 f.name, f.frames / f.samplerate, f.channels, f.samplerate)
        data.append(f)

    if data:
        samplerate = data[0].samplerate
        channels = data[0].channels
        if not all(f.samplerate == samplerate for f in data):
            raise RuntimeError("sampling rate is not the same in all files")
        if not all(f.channels == channels for f in data):
            raise RuntimeError("channel count is not the same in all files")
    return data


def repeat_and_shuffle(stimuli, repeats=1, shuffle=False):
    """ For a sequence, generate a (shuffled) list with each stimulus repeated a fixed number of times."""
    import random

    seq = [s for f in stimuli for s in (f,) * repeats]
    if shuffle:
        random.shuffle(seq)
    return seq
