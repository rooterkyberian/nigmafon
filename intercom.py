'''

@author: rooter
'''

import time
from threading import Thread, Event

import RPi.GPIO as GPIO

from caller import Caller
from caller import SimpleCallCallback


class BlinkWorker(Thread):
    def __init__(self, onoffdev, blink_duration=0.5):
        self.onoffdev = onoffdev
        self.blink_duration = blink_duration

    def run(self):
        while not self.onoffdev.blinker_event_off.is_set():
            if not self.onoffdev.blinker_event_off.wait(self.blink_duration):
                self.onoffdev.toggle()
            else:
                break


class OnOffDevice(object):
    """Simplest output device with two states.

    Personal note: make sure that your chosen GPIO channel has correct state
    on boot, or you will end up with open garage doors every time power-cycle
    happens."""

    def __init__(self, gpio, invert=False):
        self.channel = gpio
        self.invert = invert
        GPIO.setup(self.channel, GPIO.OUT, initial=False ^ self.invert)
        self.blinker_event_off = Event()

    def set(self, on):
        self.stop_blinking()
        GPIO.output(self.channel, on ^ self.invert)

    def get(self):
        return bool(GPIO.input(self.channel)) ^ self.invert

    def toggle(self):
        GPIO.output(self.channel, not GPIO.input(self.channel))

    def start_blinking(self, blink_duration):
        self.stop_blinking()
        self.worker = BlinkWorker(self, blink_duration)
        self.worker.start()

    def stop_blinking(self):
        self.blinker_event_off.set()
        self.worker = None

    def is_blinking(self):
        return not self.blinker_event_off.is_set()


class Button(object):
    """Button implementation with simple debouncing code.

    High input is interpreted as button press. The fnc function must be thread
    safe.
    """

    def __init__(self, channel, fnc):
        self.channel = channel
        self.fnc = fnc
        self.p = Thread(target=self.target_f)
        GPIO.setup(self.channel, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

    def target_f(self):
        while True:
            counter = 0
            while counter < 4:
                if GPIO.input(self.channel) == GPIO.HIGH:
                    if counter > 0:
                        counter -= 1
                else:
                    counter += 1
                time.sleep(0.05)
            GPIO.wait_for_edge(self.channel, GPIO.RISING)
            self.fnc()

    def start(self):
        self.p.start()

    def join(self):
        self.p.join()


class Intercom(object):

    def __init__(self,
                 led_red_channel,
                 led_green_channel,
                 doors_channel,
                 btn_call_channel,
                 snd_dev_capture="default",
                 snd_dev_playback="default"):

        self.selected_sipid = "sip:localhost"

        self.led_red = OnOffDevice(led_red_channel)
        self.led_green = OnOffDevice(led_green_channel)
        self.doors = OnOffDevice(doors_channel)
        self.caller = Caller(snd_dev_capture, snd_dev_playback,
                             simple_callback_factory=self._callback_factory)
        self.buttonCall = Button(btn_call_channel, self.call)

    def _callback_factory(self):
        intercom = self

        class _IntercomCallCallback(SimpleCallCallback):
            def on_connecting(self):
                intercom.led_green.start_blinking(0.5)

            def on_connected(self):
                intercom.led_green.set(True)

            def on_disconnected(self):
                intercom.led_green.set(False)

        return _IntercomCallCallback()

    def call(self):
        self.caller.call(self.selected_sipid)

    def cancel_call(self):
        self.caller.cancel_call()

    def open_door(self, duration=5):
        self.doors.set(True)
        time.sleep(duration)
        self.doors.set(False)
