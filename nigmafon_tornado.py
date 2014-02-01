#!/usr/bin/python

import pwd
import os
import os.path
import time
import random
import string
import base64
import uuid

import tornado.auth
import tornado.httpserver
import tornado.ioloop
import tornado.options
import tornado.web
import RPi.GPIO as GPIO

from intercom import Intercom


def random_word(length):
        return ''.join(random.choice(string.lowercase) for _ in range(length))


class NigmafonWebApp(tornado.web.Application):
    def __init__(self, intercom, allowed_users):
        handlers = [
            (r"/auth/login", AuthLoginHandler),
            (r"/auth/logout", AuthLogoutHandler),
            (r"/([^/]*)", TickerHandler),
        ]
        settings = dict(
            site_title=u"Nigmafon",
            template_path=os.path.join(os.path.dirname(__file__), "templates"),
            static_path=os.path.join(os.path.dirname(__file__), "static"),
            xsrf_cookies=True,
            cookie_secret=base64.b64encode(uuid.uuid4().bytes +
                                           uuid.uuid4().bytes),
            login_url="/auth/login",
            debug=True,
        )
        tornado.web.Application.__init__(self, handlers, **settings)

        self.intercom = intercom
        self.allowed_users = allowed_users


class BaseHandler(tornado.web.RequestHandler):

    @property
    def intercom(self):
        return self.application.intercom

    @property
    def allowed_users(self):
        return self.application.allowed_users

    def get_current_user(self):
        user_id = self.get_secure_cookie("user")
        if not user_id:
            return None
        return user_id


class AuthLoginHandler(BaseHandler, tornado.auth.GoogleMixin):
    @tornado.web.asynchronous
    def get(self):
        if self.get_argument("openid.mode", None):
            self.get_authenticated_user(self.async_callback(self._on_auth))
            return
        self.authenticate_redirect()

    def _on_auth(self, user):
        if not user:
            raise tornado.web.HTTPError(500, "Google auth failed")
        author_id = str(user["email"])
        self.set_secure_cookie("user", str(author_id))
        self.redirect(self.get_argument("next", "/"))


class AuthLogoutHandler(BaseHandler):
    def get(self):
        self.clear_cookie("user")
        self.redirect(self.get_argument("next", "/"))


class TickerHandler(BaseHandler):

    @tornado.web.authenticated
    def get(self, rhash):
        if self.get_current_user() in self.allowed_users:
            if self.check_rhash(rhash):
                self.write("""<html>
                    <head>
                        <meta http-equiv="refresh" content="3">
                    </head>
                    <body>
                        <h1>TICK!<h2>
                    </body>
                </html>""")
                self.recompute_rhash()
                self.intercom.open_door()
            else:
                self.write(
                """<form action="%s" method="get">
                    <input type="submit" value="tickme"
                    style="height: 20%%; width: 100%%; font-size: 4em;">
                    </form>
                """ % self.rhash)
        else:
            raise tornado.web.HTTPError(403,
                                        "Not privileged user %s" % str(
                                                    self.get_current_user()
                                                    )
                                        )

    def initialize(self):
        self.recompute_rhash()

    def check_rhash(self, rhash):
        return rhash == self.rhash

    def recompute_rhash(self):
        self.rhash = random_word(6)

if __name__ == "__main__":
    uid = pwd.getpwnam("pi")[2]
    #os.setuid(uid)

    #enable during debug, but can throw warning on first gpio use
    GPIO.setwarnings(False)

    tornado.options.define("port", default=8888,
                           help="run on the given port", type=int)
    tornado.options.define("config", default="nigmafon.config",
                           help="config file", type=str)
    tornado.options.define("allowed_users", default=[],
                           help="list of users", type=str)

    tornado.options.define("gpio_mode", default="bcm",
                           help="select GPIO numbering mode (bcm or board)",
                           type=str)

    tornado.options.define("led_red_channel", default=0,
                           help="select gpio channel", type=int)
    tornado.options.define("led_green_channel", default=0,
                           help="select gpio channel", type=int)
    tornado.options.define("doors_channel", default=0,
                           help="select gpio channel", type=int)
    tornado.options.define("btn_call_channel", default=0,
                           help="select gpio channel", type=int)
    tornado.options.define("snd_dev_capture", default="default",
                           help="select sound device", type=str)
    tornado.options.define("snd_dev_playback", default="default",
                           help="select sound device", type=str)
    tornado.options.define("sipid", default="sip:localhost",
                           help="", type=str)

    tornado.options.parse_command_line()
    if tornado.options.options.config:
        if os.path.exists(tornado.options.options.config):
            tornado.options.parse_config_file(tornado.options.options.config)

    options = tornado.options.options

    if options.gpio_mode.lower() == "bcm":
        GPIO.setmode(GPIO.BCM)
    elif options.gpio_mode.lower() == "board":
        GPIO.setmode(GPIO.BOARD)

    intercom = Intercom(
                         led_red_channel=options.led_red_channel,
                         led_green_channel=options.led_green_channel,
                         doors_channel=options.doors_channel,
                         btn_call_channel=options.btn_call_channel,
                         snd_dev_capture=options.snd_dev_capture,
                         snd_dev_playback=options.snd_dev_playback
                        )
    intercom.selected_sipid = options.sipid
    app = NigmafonWebApp(intercom,
                      options.allowed_users)
    http_server = tornado.httpserver.HTTPServer(app)
    http_server.listen(options.port)
    tornado.ioloop.IOLoop.instance().start()
