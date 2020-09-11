# -*- coding: utf-8 -*-
# -*- mode: python -*-

__version__ = "0.1.0"

import logging

import sounddevice as sd

log = logging.getLogger('oe-audio')   # root logger


def set_device(index):
    """ Set the default device """
    sd.default.device = index


def device_index():
    """ Returns the numerical index of the current default (playback) device """
    return sd.default.device[1]


def device_properties():
    """Returns properties of the current device"""
    return sd.query_devices()[device_index()]


def repeat_and_shuffle(seq, repeats=1, shuffle=False):
    """ For a sequence, generate a (shuffled) list with each item repeated a fixed number of times."""
    import random

    seq = [s for f in seq for s in (f,) * repeats]
    if shuffle:
        random.shuffle(seq)
    return seq




class StimulusQueue:
    """ An object that manages a queue of stimuli with repetition, shuffling, and looping

    The stimulus files are opened (but not read) on initialization. A RuntimeError is raised if
    files do not exist, are unreadable, or do not have the same number of channels.
    """

    def __init__(self, files, repeats=1, shuffle=False, loop=False):
        import soundfile as sf
        assert (len(files) > 0), "No stimuli!"
        assert (repeats > 0), "Number of repeats must be a positive integer"
        self.repeats = repeats
        self.shuffle = shuffle
        self.loop = loop
        data = []
        for fname in files:
            f = sf.SoundFile(fname)
            log.info(" - %s: %.2f s (channels=%d, samplerate=%d)",
                     f.name, f.frames / f.samplerate, f.channels, f.samplerate)
            data.append(f)

        self.samplerate = data[0].samplerate
        self.channels = data[0].channels
        if not all(f.samplerate == self.samplerate for f in data):
            raise RuntimeError("sampling rate is not the same in all files")
        if not all(f.channels == self.channels for f in data):
            raise RuntimeError("channel count is not the same in all files")
        self.stimuli = data

    def __iter__(self):
        self.stimlist = repeat_and_shuffle(self.stimuli, self.repeats, self.shuffle)
        self.index = 0
        return self

    def __next__(self):
        import random
        if self.index >= len(self.stimlist):
            if not self.loop:
                raise StopIteration
            log.debug("Reshuffling stimulus list")
            random.shuffle(self.stimlist)
            self.index = 0
        s = self.stimlist[self.index]
        # move the pointer to the start of the file
        s.seek(0)
        self.index += 1
        return s
