#!/usr/bin/env python
# encoding: utf-8

import sys

from caller import Caller

if __name__ == "__main__":

    caller = Caller()
    while True:
        sys.stdout.write("Provide sip id: or q to exit")
        line = sys.stdin.readline().strip()
        if line == "q":
            break
        caller.call(line)
        sys.stdout.write("enter to end the call")
        sys.stdin.readline()
        caller.cancel_call()

    sys.exit(0)
