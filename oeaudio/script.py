# -*- coding: utf-8 -*-
# -*- mode: python -*-

import argparse
import logging

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

    p.add_argument("--shuffle", "-S", help="shuffle order of presentation", action="store_true")
    p.add_argument("--loop", "-l", help="loop endlessly", action="store_true")
    p.add_argument("--repeats", "-r", help="default number of repetitions", type=int, default=1)
    p.add_argument("--gap", "-g", help="minimum gap between stimuli (s)", type=float, default=2.0)
    p.add_argument("stim", help="stimulus
