# -*- coding: utf-8 -*-
# -*- mode: python -*-
"""Presents acoustic stimuli for open-ephys experiments

Stimuli are read from sound files (e.g. wave format) with 1 or 2 channels. The
second channel is typically used as a synchronization signal. For one-channel
files, there is an option to add a click to the second channel at the start of
each stimulus.

Note that stimulus files are read into memory, so the total
"""

import argparse
import logging
import queue
import threading
import time
import json
import yaml
import ctypes
import sounddevice as sd

from oeaudio import core

log = logging.getLogger('oe-audio')   # root logger


def setup_log(log, debug=False):
    ch = logging.StreamHandler()
    formatter = logging.Formatter("%(message)s")
    loglevel = logging.DEBUG if debug else logging.INFO
    log.setLevel(loglevel)
    ch.setLevel(loglevel)
    ch.setFormatter(formatter)
    log.addHandler(ch)


class ParseKeyVal(argparse.Action):

    def parse_value(self, value):
        import ast
        try:
            return ast.literal_eval(value)
        except (ValueError, SyntaxError):
            return value

    def __call__(self, parser, namespace, arg, option_string=None):
        kv = getattr(namespace, self.dest)
        if kv is None:
            kv = dict()
        if not arg.count('=') == 1:
            raise ValueError(
                "-k %s argument badly formed; needs key=value" % arg)
        else:
            key, val = arg.split('=')
            kv[key] = self.parse_value(val)
        setattr(namespace, self.dest, kv)


def main(argv=None):

    p = argparse.ArgumentParser(description='present acoustic stimuli for open-ephys experiments')
    p.add_argument('-v', '--version', action="version",
                   version="%(prog)s " + core.__version__)
    p.add_argument('--debug', help="show verbose log messages", action="store_true")

    p.add_argument("--list-devices", "-L", help="list available sound devices and exit", action="store_true")
    p.add_argument("--device", "-D", help="output sound device", type=int, default=core.device_index())
    p.add_argument("--block-size", "-b", type=int, default=2048,
                   help="block size (default: %(default)s)")
    p.add_argument("--buffer-size", "-sample_queue", type=int, default=20,
                   help="buffer size (in blocks; default: %(default)s)")

    p.add_argument("--shuffle", "-S", help="shuffle order of presentation (argument specifies random seed)",
                   nargs='?', default=None)
    p.add_argument("--loop", "-l", help="loop endlessly", action="store_true")
    p.add_argument("--repeats", "-r", help="default number of time to repeat each stimulus",
                   type=int, default=1)
    p.add_argument("--gap", "-g", help="minimum gap between stimuli (s)", type=float, default=2.0)

    p.add_argument("--open-ephys-address", "-a", help="open-ephys zmq socket")
    p.add_argument("--open-ephys-directory", "-d", help="open-ephys recording directory")
    p.add_argument("-k", help="specify metadata for the recording (use multiple -k for multiple fields)",
                   action=ParseKeyVal, default=dict(), metavar="KEY=VALUE", dest='metadata')

    p.add_argument("--load-config", "-c", help="load configuration values from file in yaml format")
    p.add_argument("--save-config", help="save configuration values to a yaml file")

    p.add_argument(
        "stimfiles",
        nargs="*",
        metavar="stim",
        help="sound files containing an acoustic stimulus. All stimuli must have the same samplerate and number of channels"
    )

    args = p.parse_args(argv)
    setup_log(log, args.debug)

    if args.list_devices:
        print("Available sound devices:")
        print(core.sd.query_devices())
        p.exit(0)

    # TODO load config from file

    # display info about the device
    core.set_device(args.device)
    device_info = core.device_properties()
    if args.debug:
        log.debug("Playback device:")
        log.debug(yaml.dump(device_info))
    else:
        log.info("Playback device: %(name)s", device_info)

    log.info("Loading stimuli:")
    if not args.stimfiles:
        p.exit(0)
    stim_queue = core.StimulusQueue(args.stimfiles, args.repeats, args.shuffle, args.loop)

    controller = core.OpenEphysControl(args.open_ephys_address)
    controller.start_acquisition()

    # create a sample queue and a semaphore. The sample queue can contain data
    # buffers, messages, or None
    sample_queue = queue.Queue(maxsize=args.buffer_size + 1)
    evt = threading.Event()
    buffer_size = args.block_size * stim_queue.channels * ctypes.sizeof(ctypes.c_float)

    def _process(outdata, frames, time, status):
        """ Callback function for output stream thread """
        assert frames == args.block_size, "frame count doesn't match buffer block size"
        if status.output_underflow:
            log.error('Output underflow: increase blocksize?')
            raise sd.CallbackAbort
        assert not status
        try:
            data = sample_queue.get_nowait()
            if data is None:
                raise sd.CallbackStop
            elif isinstance(data, str):
                controller.message(data)
            else:
                assert (len(data) <= len(outdata)), "block has too much data"
                outdata[:len(data)] = data
                outdata[len(data):] = b'\x00' * (len(outdata) - len(data))
        except queue.Empty:
            # if the queue is empty, we just zero out the buffer
            outdata[:] = b'\x00'

    # The main thread sends data into the queue from files in the stimulus
    # queue. Between stimuli, it sends blocks of zeros. To stop the stream
    # thread, we send None.

    # We first need to prefill the queue so that the buffer starts full.
    stimiter = iter(stim_queue)
    stim = next(stimiter)
    log.debug(" - prebuffering %d frames from %s", args.block_size, stim.name)
    sample_queue.put_nowait("start %s" % stim.name)
    for _ in range(args.buffer_size):
        samples = stim.buffer_read(args.block_size, dtype='float32')
        sample_queue.put_nowait(samples)
        if len(samples) < buffer_size:
            break

    controller.start_recording(args.open_ephys_directory,
                               args.metadata.get("animal", ""),
                               args.metadata.get("experiment", ""))
    controller.message("metadata: %s" % json.dumps(args.metadata))

    # then open the stream for writing
    stream = sd.RawOutputStream(
        device=args.device,
        blocksize=args.block_size,
        samplerate=stim_queue.samplerate,
        channels=stim_queue.channels,
        dtype='float32',
        callback=_process,
        finished_callback=evt.set)
    try:
        with stream:
            timeout = args.block_size * args.buffer_size / stim_queue.samplerate
            while samples is not None:
                samples = stim.buffer_read(args.block_size, dtype='float32')
                sample_queue.put(samples, timeout=timeout)
                if len(samples) < buffer_size:
                    sample_queue.put("stop %s" % stim.name, timeout=timeout)
                    gap_frames = int(args.gap * stim_queue.samplerate)
                    for _ in range(0, gap_frames, args.block_size):
                        samples = ctypes.create_string_buffer(buffer_size)
                        sample_queue.put(samples, timeout=timeout)
                    try:
                        stim = next(stimiter)
                    except StopIteration:
                        break
                    sample_queue.put("start %s" % stim.name)
            sample_queue.put(None)
            evt.wait()
            controller.stop_recording()
            time.sleep(args.gap)
            controller.stop_acquisition()
    except KeyboardInterrupt:
        p.exit('\nInterrupted by user')
    except queue.Full:
        # A timeout occurred, i.e. there was an error in the callback
        p.exit(1)
    except Exception as e:
        p.exit(type(e).__name__ + ': ' + str(e))
