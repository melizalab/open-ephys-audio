# -*- coding: utf-8 -*-
# -*- mode: python -*-

import logging

import sounddevice as sd
import zmq

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
        random.seed(shuffle)
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


class OpenEphysControl:
    """ A class to control open-ephys data acquisition over a zmq socket

    url: the address of the host socket
    timeout: timeout for reply from host

    """
    socket = None

    def __init__(self, url, timeout=1.0):
        if url is None:
            log.info("open-ephys: dummy mode (no connection)")
            return
        context = zmq.Context()
        self.socket = context.socket(zmq.REQ)
        self.socket.RCVTIMEO = int(timeout * 1000)
        log.info("open-ephys: connecting to %s", url)
        self.socket.connect(url)

    def _send(self, message, expected=None):
        # req sockets have to be read after each message
        if self.socket is None:
            return "N/A"
        else:
            self.socket.send_string(message)
            ret = self.socket.recv_string()
            if expected is not None and ret != expected:
                log.error(" - unexpected reply: %s", ret)
                raise RuntimeError("open-ephys replied '%s', expecting '%s'" % (ret, expected))
            log.debug(" - reply: %s", ret)
            return ret

    def start_acquisition(self):
        log.info("open-ephys: starting acquisition")
        self._send("StartAcquisition", "StartedAcquisition")

    def stop_acquisition(self):
        log.info("open-ephys: stopping acquisition")
        self._send("StopAcquisition", "StoppedAcquisition")

    def start_recording(self, rec_dir, prepend="", append=""):
        cmd = "StartRecord RecDir={} PrependText={} AppendText={}".format(rec_dir, prepend, append)
        log.info("open-ephys: starting recording")
        self._send(cmd, "StartedRecording")
        rec_path = self._send("GetRecordingPath")
        log.info(" - recording path: %s", rec_path)

    def stop_recording(self):
        log.info("open-ephys: stopping recording")
        self._send("StopRecord", "StoppedRecording")

    def message(self, text):
        """ Log a timestampped message in the recording """
        log.info("open-ephys: sent '%s'", text)
        self._send(text)
