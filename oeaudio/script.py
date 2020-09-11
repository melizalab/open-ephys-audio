# -*- coding: utf-8 -*-
# -*- mode: python -*-
"""Presents acoustic stimuli for open-ephys experiments

Stimuli are read from sound files (e.g. wave format) with 1 or 2 channels. The
second channel is typically used as a synchronization signal. For one-channel
files, there is an option to add a click to the second channel at the start of
each stimulus.
"""

import argparse
import logging

from oeaudio.core import __version__

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
                   version="%(prog)s " + __version__)
    p.add_argument('--debug', help="show verbose log messages", action="store_true")

    p.add_argument("--device", "-d", help="output sound device")
    p.add_argument("--block-size", "-b", type=int, default=2048,
                   help="block size (default: %(default)s)")
    p.add_argument("--buffer-size", "-q", type=int, default=20,
                   help="buffer size (in blocks; default: %(default)s)")

    p.add_argument("--shuffle", "-S", help="shuffle order of presentation", action="store_true")
    p.add_argument("--loop", "-l", help="loop endlessly", action="store_true")
    p.add_argument("--repeats", "-r", help="default number of time to repeat each stimulus",
                   type=int, default=1)
    p.add_argument("--gap", "-g", help="minimum gap between stimuli (s)", type=float, default=2.0)
    p.add_argument("--socket", "-s", help="open-ephys zmq socket", default="tcp://127.0.0.1:5556")
    p.add_argument("-k", help="specify metadata for the recording (use multiple -k for multiple fields)",
                   action=ParseKeyVal, default=dict(), metavar="KEY=VALUE", dest='metadata')
    p.add_argument("--load-config", "-c", help="load configuration values from file in toml format")
    p.add_argument("--save-config", help="save configuration values to a toml file")

    p.add_argument("stim",
                   help="Sound files containing acoustic stimuli. May have 1 or 2 channels", nargs="*")

    args = p.parse_args(argv)
    setup_log(log, args.debug)
