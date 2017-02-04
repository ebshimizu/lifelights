import requests as req
import json
import time
import OSC
from util import Util

class CDWatcher:
    """Performs scanning and sizing of an image based on upper and lower bounds of colors."""

    def __init__(self, watcher_conf):
        self._settings = watcher_conf
        self._target_region = (watcher_conf["target_region"]["x"],
                               watcher_conf["target_region"]["y"],
                               watcher_conf["target_region"]["width"],
                               watcher_conf["target_region"]["height"])

        self._min_threshold = watcher_conf["min_threshold"]
        self._current_brightness = 1.0
        self._max_brightness = 0
        self._last_brightness = 0.0

        self._osc_enabled = False

    def scan(self, screen):
        """Monitor the target region of interest for changes in brightness"""
        import cv2
        target = screen[self._target_region[1]:self._target_region[1] + self._target_region[3], self._target_region[0]:self._target_region[0] + self._target_region[2]]

        # calculate means
        means = cv2.mean(target)

        self._last_brightness = self._current_brightness
        self._current_brightness = sum(means) / 3

        if (self._current_brightness > self._max_brightness):
            self._max_brightness = self._current_brightness

        # detailed debug, may only want this to be uncommented if you really like logs
        # Util.log("Brightness update: %d -> %d (Max %d)" % (self._last_brightness, self._current_brightness, self._max_brightness))

    def sendOSC(self, address, port, msg):
        if not self._osc_enabled:
            self._osc_client = OSC.OSCClient()
            self._osc_client.connect((address, int(port)))
            self._osc_enabled = True

            Util.log("Started OSC client streaming to %s:%i" % (address, port))

        self._osc_client.send(msg)
        #Util.log("Sent message %s to %s:%i" % (msg, address, port))

    def process(self):
        """Execute RESTful API calls based on the results of an image scan."""
        import copy
        
        # on = 1 if (self._current_brightness >= self._max_brightness * (1 - self._settings["tolerance"])) else 0
        on = 1 if (self._current_brightness >= self._min_threshold) else 0

        # Util.log("%s updated to %.2f" % (self._settings["name"], on))

        try:
            settings_copy = copy.deepcopy(self._settings)

            for index, request in enumerate(settings_copy["requests"]):
                for payload, value in request["payloads"].items():
                    if value == "IS_ON_PLACEHOLDER":
                        settings_copy["requests"][index]["payloads"][
                            payload] = on

                if request["method"].upper() == "POST":
                    # print json.dumps(request["payloads"])
                    api_call = req.post(
                        request["endpoint"],
                        data=json.dumps(request["payloads"]))
                if request["method"].upper() == "GET":
                    api_call = req.get(
                        request["endpoint"],
                        data=request["payloads"])
                if request["method"].upper() == "OSC":
                    # osc streaming output of the current bar percentage to the specified endpoint
                    # The intended use of OSC is to enable other devices to access game info
                    msg = OSC.OSCMessage()
                    msg.append(request["payloads"])
                    msg.setAddress("/" + settings_copy["name"])
                    self.sendOSC(request["endpoint"], request["port"], msg)
                    api_call = None

                if api_call:
                    Util.log("RESTful response %s" % api_call)

                time.sleep(float(request["delay"]))

        except Exception, exc:
            Util.log("Error firing an event for %s, event: %s" %
                     (self._settings["name"], exc))

    def name(self):
        return self.watcher_conf["name"]