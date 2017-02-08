import requests as req
import json
import time
import OSC
from util import Util

class WidthWatcher:
    """Performs scanning and sizing of an image based on upper and lower bounds of colors."""

    def __init__(self, watcher_conf):
        self._settings = watcher_conf
        self._upper_bounds = (watcher_conf["color_upper_limit"]["blue"],
                              watcher_conf["color_upper_limit"]["green"],
                              watcher_conf["color_upper_limit"]["red"])

        self._lower_bounds = (watcher_conf["color_lower_limit"]["blue"],
                              watcher_conf["color_lower_limit"]["green"],
                              watcher_conf["color_lower_limit"]["red"])

        self._max_width = 1.0
        self._max_height = 1.0
        self._width = 0.0
        self._osc_enabled = False

        self._height = 0.0
        self._barX = 0.0
        self._barY = 0.0
        self._current_percentage = 0.0

        self._last_percentage = 0.0

    def scan(self, screen):
        """Scan an image and attempt to fit an invisible rectangle around a group of colors."""
        import cv2
        image_mask = cv2.inRange(screen, self._lower_bounds,
                                 self._upper_bounds)

        cnts = cv2.findContours(image_mask.copy(), cv2.RETR_EXTERNAL,
                                cv2.CHAIN_APPROX_SIMPLE)[-2]

        # determine which contour is furthest right (for now we assume all bars extend to the right)
        maxX = 0.0
        if (len(cnts) == 0):
            self._current_percentage = 0

        for cnt in cnts:
            cx, cy, cw, ch = cv2.boundingRect(cnt)

            if (cw - int(self._settings["min_width"])) >= 0:
                if self._max_width < cw:
                    self._max_width = float(cw)
                    self._max_height = float(ch)
                    self._barX = float(cx)
                    self._barY = float(cy)
                    Util.log("Max %s updated %d" %
                             (self._settings["name"], cw))

            # debug
            #cv2.rectangle(screen, (int(self._barX),int(self._barY)),(int(self._barX+self._max_width),int(self._barY+self._max_height)),(0,255,0),2)
            #cv2.rectangle(screen, (cx,cy), (cx + cw, cy + ch), (0,0,255), 2)
            #cv2.imshow("bar debug", screen)
            #cv2.waitKey()
            #quit()

            if (cx + cw > maxX):
                rightX = cx + cw

                # containment check
                if (self._barX <= rightX <= self._barX + self._max_width and self._barY <= cy <= self._barY + self._max_height):
                    maxX = float(rightX)

                    # update stats
                    self._current_percentage = round((maxX - self._barX) / self._max_width, 3)

        else:
            self._width = 0.0

        # detailed debug, may only want this to be uncommented if you really like logs
        #Util.log("Percentage calculated as %d / %d (%f)" % (maxX - self._barX, self._max_width, self._current_percentage))

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

        percent = self._current_percentage # round((self._width * 1.0) / (self._max_width * 1.0), 2)

        if self._last_percentage == percent:
            return

        if percent + (self._settings["change_threshold"] * 1.0 / 100) > 1.0:
            # snap to 100%
            percent = 1.0
        elif percent - (self._settings["change_threshold"] * 1.0 / 100) < 0.0:
            # snap to 0%
            percent = 0.0

        if abs(self._last_percentage - percent) < (self._settings["change_threshold"] * 1.0) / 100:
            return

        self._last_percentage = float(percent)

        if percent <= 0.0:
            Util.log("%s reached 0.0" %
                     self._settings["name"])
        else:
            Util.log("%s updated to %.2f" % (self._settings["name"], percent))

        try:
            rgb = [
                int(255 * (100 - (percent * 100)) / 100),
                int(255 * (percent * 100) / 100), 0
            ]

            settings_copy = copy.deepcopy(self._settings)

            for index, request in enumerate(settings_copy["requests"]):
                for payload, value in request["payloads"].items():
                    if value == "RGB_PLACEHOLDER":
                        settings_copy["requests"][index]["payloads"][
                            payload] = rgb
                    if value == "WIDTH_PLACEHOLDER":
                        settings_copy["requests"][index]["payloads"][
                            payload] = int(self._width)
                    if value == "PERCENT_PLACEHOLDER":
                        settings_copy["requests"][index]["payloads"][
                            payload] = int((percent * 100))
                    if value == "BRIGHTNESS_PLACEHOLDER":
                        settings_copy["requests"][index]["payloads"][
                            payload] = int((percent * 255))
                    if value == "RAW_PERCENT_PLACEHOLDER":
                        settings_copy["requests"][index]["payloads"][
                            payload] = percent

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
                    # osc streaming output
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