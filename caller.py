import sys
import time
import pjsua

pjlib = pjsua.Lib()


def log_cb(level, string, length):
    print(level, string)


class Player(object):
    def __init__(self, filename, loop=False):
        global pjlib
        self.player_id = pjlib.create_player(filename, loop=loop)

    def play(self):
        global pjlib
        player_slot = pjlib.player_get_slot(self.player_id)
        pjlib.conf_connect(player_slot, 0)

    def stop(self):
        global pjlib
        player_slot = pjlib.player_get_slot(self.player_id)
        pjlib.conf_disconnect(player_slot, 0)

    def __del__(self):
        global pjlib
        pjlib.player_destroy(self.player_id)


class CallerCallCallback(pjsua.CallCallback):

    def __init__(self, call=None):
        pjsua.CallCallback.__init__(self, call)
        self.ringer = Player("media/ring.wav", loop=True)
        self.sfx = None

    # Notification when call state has changed
    def on_state(self):
        print(self.call.info().state_text)
        if self.ringer is not None:
            if self.call.info().state in (pjsua.CallState.CALLING,
                                          pjsua.CallState.INCOMING):
                self.ringer.play()
            elif self.call.info().state in (pjsua.CallState.CONFIRMED,
                                            pjsua.CallState.DISCONNECTED):
                self.ringer.stop()
                self.ringer = None

                sound_filename = None
                if self.call.info().state == pjsua.CallState.CONFIRMED:
                    sound_filename = "media/call_connected.wav"
                elif self.call.info().state == pjsua.CallState.DISCONNECTED:
                    sound_filename = "media/call_disconnected.wav"
                self.sfx = Player(sound_filename)
                self.sfx.play()

    # Notification when call's media state has changed.
    def on_media_state(self):
        global pjlib
        call_slot = self.call.info().conf_slot
        if self.call.info().media_state == pjsua.MediaState.ACTIVE:
            pjlib.conf_connect(call_slot, 0)
            pjlib.conf_connect(0, call_slot)

            print("sound connected",
                  pjlib.conf_get_signal_level(call_slot),
                  pjlib.conf_get_signal_level(0))
        else:
            pjlib.conf_disconnect(call_slot, 0)
            pjlib.conf_disconnect(0, call_slot)

    def on_dtmf_digit(self, digits):
        print(digits)

    def on_pager(self, mime_type, body):
        print(mime_type, body)


class Caller(object):

    def __init__(self,
                 playback_dev_name="default",
                 capture_dev_name="default"):

        ua_cfg = pjsua.UAConfig()
        ua_cfg.max_calls = 4

        # Init library with default config
        global pjlib
        pjlib.init(log_cfg=pjsua.LogConfig(level=3, callback=log_cb),
                   ua_cfg=ua_cfg)

        self.__snd_dev(capture_dev_name, playback_dev_name)

        # Create UDP transport which listens to any available port
        self.transport = pjlib.create_transport(pjsua.TransportType.UDP)

        pjlib.start()

        self.acc = pjlib.create_account_for_transport(self.transport)

        self.current_call = None
        self.sfx = None

    def __snd_dev(self, capture_dev_name, playback_dev_name):
        global pjlib

        if "null" in (capture_dev_name.lower(), playback_dev_name.lower()):
            pjlib.set_null_snd_dev()
        else:
            capture = playback = dev_id = 0
            for dev in pjlib.enum_snd_dev():
                if dev.name == capture_dev_name:
                    capture = dev_id
                if dev.name == playback_dev_name:
                    playback = dev_id
                dev_id += 1
            pjlib.set_snd_dev(capture, playback)

    def call(self, sipid):
        if self.current_call is None or not self.current_call.is_valid():
            try:
                self.current_call = self.acc.make_call(sipid,
                                                       cb=CallerCallCallback())
            except pjsua.Error:
                self.sfx = Player("media/error.wav")
                self.sfx.play()

    def cancel_call(self):
        if self.current_call is not None:
            if self.current_call.is_valid():
                self.current_call.hangup()

    def __del__(self):
        self.cancel_call()
        self.current_call = None

        global pjlib
        pjlib.destroy()
        del pjlib
