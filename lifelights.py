import time
import sys
import os
import itertools
from util import Util
from widthwatcher import WidthWatcher
from cdwatcher import CDWatcher
import yaml

sys.path.append(
    os.path.join(os.path.dirname(os.path.realpath(__file__)), '..'))


def main():
    """Main entrypoint for script."""
    config_file = open('lifelights_osc.yml')
    settings = yaml.safe_load(config_file)
    config_file.close()

    config_error = Util.has_valid_config(settings)

    if config_error:
        Util.log("Error found in configuration file -- %s" % config_error)
        sys.exit()

    spinner = itertools.cycle(['-', '/', '|', '\\'])

    watcher_list = [WidthWatcher(w) for w in settings["watchers"]]
    cd_watcher_list = [CDWatcher(w) for w in settings["cd_watchers"]]

    window = Util.find_window_by_title(settings["window_title"])

    if window is not None:
        window = Util.resize_capture_area(window, settings)

    while True:

        if window is None:
            sys.stdout.write("Waiting for window ... " + spinner.next() + "\r")
            sys.stdout.flush()
            window = Util.find_window_by_title(settings["window_title"])
            if window is not None:
                window = Util.resize_capture_area(window, settings)
            time.sleep(0.3)
            continue

        time.sleep(float(settings["scan_interval"]))

        screen = Util.screenshot(window)

        if not screen.any():
            continue

        for watch in watcher_list:
            watch.scan(screen)
            watch.process()

        for watch in cd_watcher_list:
            watch.scan(screen)
            watch.process()


if __name__ == '__main__':
    try:
        main()
    except (KeyboardInterrupt, SystemExit):
        print "Goodbye, hero."
