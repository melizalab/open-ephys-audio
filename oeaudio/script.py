# -*- coding: utf-8 -*-
# -*- mode: python -*-
"""Presents acoustic stimuli for open-ephys experiments

Stimuli are read from sound files (e.g. wave format) with 1 or 2 channels. The
second channel is typically used as a synchronization signal. For one-channel
files, by default a click is added to the second channel at the start of each
stimulus.

"""

import os
import argparse
import logging
import queue
import threading
import time
import json
import yaml
import ctypes
import sounddevice as sd

from oeaudio import __version__

log = logging.getLogger("oe-audio")  # root logger


def setup_log(log, debug=False):
    ch = logging.StreamHandler()
    formatter = logging.Formatter("%(message)s")
    loglevel = logging.DEBUG if debug else logging.INFO
    log.setLevel(loglevel)
    ch.setLevel(loglevel)
    ch.setFormatter(formatter)
    log.addHandler(ch)


def positivefloat_or_none(arg):
    """ Parses arg as a positive float, otherwise None """
    try:
        value = float(arg)
    except ValueError:
        return None
    if value > 0:
        return value


class ParseKeyVal(argparse.Action):
    """ Custom action that parses arguments formed as key=value pair """

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
        if not arg.count("=") == 1:
            raise ValueError("-k %s argument badly formed; needs key=value" % arg)
        else:
            key, val = arg.split("=")
            kv[key] = self.parse_value(val)
        setattr(namespace, self.dest, kv)


def main(argv=None):

    p = argparse.ArgumentParser(
        description="present acoustic stimuli for open-ephys experiments"
    )
    p.add_argument(
        "-v", "--version", action="version", version="%(prog)s " + __version__
    )
    p.add_argument("--debug", help="show verbose log messages", action="store_true")

    p.add_argument(
        "--list-devices",
        "-L",
        help="list available sound devices and exit",
        action="store_true",
    )
    p.add_argument(
        "--device",
        "-D",
        help="set index of output sound device (use -L to see default)",
        type=int,
    )
    p.add_argument(
        "--block-size",
        "-b",
        type=int,
        default=8192,
        help="block size (default: %(default)s)",
    )
    p.add_argument(
        "--buffer-size",
        type=int,
        default=20,
        help="buffer size (in blocks; default: %(default)s)",
    )

    p.add_argument(
        "--shuffle",
        "-S",
        help="shuffle order of presentation (w/ optional random seed)",
        nargs="?",
        default=None,
        metavar="SEED",
    )
    p.add_argument("--loop", "-l", help="loop endlessly", action="store_true")
    p.add_argument(
        "--repeats",
        "-r",
        help="default number of time to repeat each stimulus",
        type=int,
        default=1,
    )
    p.add_argument(
        "--gap",
        "-g",
        help="minimum gap between stimuli (default: %(default)s s)",
        type=float,
        default=2.0,
    )
    p.add_argument(
        "--warmup",
        help="pause between starting acquisition and recording (default: %(default)s s)",
        type=float,
        default=5.0,
    )
    p.add_argument(
        "--click-duration",
        "-c",
        help="for 1-channel stimuli, sets the duration (in ms)"
        " of the click added to the second (sync) channel (set to 0 to disable)",
        default=2.0,
        type=positivefloat_or_none,
    )

    p.add_argument(
        "--open-ephys-address", "-a", metavar="URL", help="open-ephys zmq socket"
    )
    p.add_argument(
        "--open-ephys-directory",
        "-d",
        metavar="DIR",
        default=os.environ["HOME"],
        help="open-ephys recording directory (default: %(default)s)",
    )
    p.add_argument(
        "-k",
        help="specify metadata for the recording (use multiple -k for multiple fields). "
        "Note: 'animal' and 'experiment' are prepended and appended to the recording name",
        action=ParseKeyVal,
        default=dict(),
        metavar="KEY=VALUE",
        dest="metadata",
    )

    p.add_argument(
        "--load-config",
        "-C",
        metavar="FILE",
        help="TODO: load configuration values from file in yaml format",
    )
    p.add_argument(
        "--save-config",
        metavar="FILE",
        help="TODO: save configuration values to a yaml file",
    )

    p.add_argument(
        "stimfiles",
        nargs="*",
        metavar="stim",
        help="sound files containing an acoustic stimulus. All stimuli must have the same samplerate and number of channels",
    )

    args = p.parse_args(argv)
    setup_log(log, args.debug)

    from oeaudio import core

    if args.list_devices:
        print("Available sound devices:")
        print(core.sd.query_devices())
        p.exit(0)

    # TODO load config from file
    log.info("Configuration: ")
    log.info(" - block size: %d samples", args.block_size)
    log.info(" - buffer size: %d blocks", args.buffer_size)
    log.info(" - gap: %3.2f s", args.gap)
    log.info(" - warmup pause: %3.2f s", args.warmup)
    log.info(" - repeats: %d", args.repeats)
    log.info(" - loop? %s", args.loop)
    if args.shuffle:
        log.info(" - shuffling with random seed %s", args.shuffle)
    if args.click_duration:
        log.info(" - will add %3.2f s click to sync channel", args.click_duration)

    # display info about the device
    if args.device is not None:
        core.set_device(args.device)
    device_info = core.device_properties()
    if args.debug:
        log.debug(" - playback device:")
        log.debug(yaml.dump(device_info))
    else:
        log.info(" - playback device: %(name)s", device_info)

    log.info("Loading stimuli:")
    if not args.stimfiles:
        p.exit(0)
    stim_queue = core.StimulusQueue(
        args.stimfiles, args.repeats, args.shuffle, args.loop, args.click_duration
    )

    controller = core.OpenEphysControl(args.open_ephys_address)
    controller.start_acquisition()
    time.sleep(args.warmup)

    # create a sample queue and a semaphore. The sample queue can contain data
    # buffers, messages, or None
    sample_queue = queue.Queue(maxsize=args.buffer_size + 1)
    evt = threading.Event()
    buffer_size = args.block_size * stim_queue.channels * ctypes.sizeof(ctypes.c_float)

    def _process(outdata, frames, time, status):
        """ Callback function for output stream thread """
        assert frames == args.block_size, "frame count doesn't match buffer block size"
        if status.output_underflow:
            log.error("Output underflow: increase blocksize?")
            raise sd.CallbackAbort
        assert not status
        try:
            data = sample_queue.get_nowait()
            if data is None:
                raise sd.CallbackStop
            elif isinstance(data, str):
                controller.message(data)
            else:
                assert len(data) <= len(outdata), "block has too much data"
                outdata[: len(data)] = data
                outdata[len(data) :] = b"\x00" * (len(outdata) - len(data))
        except queue.Empty:
            # if the queue is empty, we just zero out the buffer
            outdata[:] = b"\x00"

    # The main thread sends data into the queue from files in the stimulus
    # queue. Between stimuli, it sends blocks of zeros. To stop the stream
    # thread, we send None.

    # We first need to prefill the queue so that the buffer starts full.
    stimiter = iter(stim_queue)
    stim = next(stimiter)
    log.debug(" - prebuffering %d frames from %s", args.block_size, stim.name)
    sample_queue.put_nowait("start %s" % stim.name)
    for _ in range(args.buffer_size):
        samples = stim.read(args.block_size)
        sample_queue.put_nowait(samples)
        if len(samples) < buffer_size:
            break

    controller.start_recording(
        args.open_ephys_directory,
        args.metadata.get("animal", ""),
        args.metadata.get("experiment", ""),
    )
    controller.message("metadata: %s" % json.dumps(args.metadata))

    # pause for a gap before the first stimulus
    time.sleep(args.gap)

    # then open the stream for writing
    stream = sd.RawOutputStream(
        device=args.device,
        blocksize=args.block_size,
        samplerate=stim_queue.samplerate,
        channels=stim_queue.channels,
        dtype="float32",
        callback=_process,
        finished_callback=evt.set,
    )
    try:
        with stream:
            timeout = args.block_size * args.buffer_size / stim_queue.samplerate
            while samples is not None:
                samples = stim.read(args.block_size)
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
    except KeyboardInterrupt:
        log.info("experiment interrupted by user")
        controller.message("experiment interrupted by user")
    except queue.Full:
        # A timeout occurred, i.e. there was an error in the callback
        log.error("buffer overrun")
        controller.message("buffer overrun error during stimulus playback")
    except Exception as e:
        controller.message("unhandled exception during stimulus playback")
        log.error(type(e).__name__ + ": " + str(e))
    finally:
        controller.stop_recording()
        time.sleep(args.gap)
        controller.stop_acquisition()
