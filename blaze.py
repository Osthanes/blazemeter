#!/usr/bin/python

import requests
import sys
import json
import time
import logging
import os

BLZ_URL = "https://a.blazemeter.com"
POLL_TIME = 30
EXEC_REPORT = BLZ_URL + "/app/printable-report/index.html?base_url=&session_id=%s"
DEBUG = os.environ.get('DEBUG')

# ascii color codes for output
LABEL_GREEN = '\033[0;32m'
LABEL_RED = '\033[0;31m'
LABEL_COLOR = '\033[0;33m'
LABEL_NO_COLOR = '\033[0m'
STARS = "**********************************************************************"

API_KEY = os.getenv('BLAZEMETER_APIKEY')
TEST_ID = os.getenv('TEST_ID')

print "TEST_URL: " + os.getenv('TEST_URL')


def request(url):
    headers = {'x-api-key': API_KEY}
    return requests.get(url, headers=headers)


def print_json(obj):
    print json.dumps(obj, indent=4, sort_keys=True)


def setup_logging():
    logger = logging.getLogger('pipeline')
    if DEBUG:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)

    # if logmet is enabled, send the log through syslog as well
    if os.environ.get('LOGMET_LOGGING_ENABLED'):
        handler = logging.handlers.SysLogHandler(address='/dev/log')
        logger.addHandler(handler)
        # don't send debug info through syslog
        handler.setLevel(logging.INFO)

    # in any case, dump logging to the screen
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    if DEBUG:
        handler.setLevel(logging.DEBUG)
    else:
        handler.setLevel(logging.INFO)
    logger.addHandler(handler)

    return logger


def test_start(test_id):
    url = (BLZ_URL + "/api/latest/tests/{0}/start").format(test_id)
    try:
        response = request(url)
        response.raise_for_status()
        return response
    except requests.exceptions.RequestException as e:
        print e
        sys.exit(1)


def test_monitor(session_id):
    url = (BLZ_URL + "/api/latest/sessions/{0}").format(session_id)
    try:
        response = request(url)
        response.raise_for_status()
        return response
        # TODO: Handle polling errors differently (i.e re-attempts)
    except requests.exceptions.RequestException as e:
        print e
        sys.exit(1)

def create_test():



# Start
# Needed to get rid of InsecureRequestWarning
logging.captureWarnings(True)
LOGGER = setup_logging()

if not API_KEY:
    print LABEL_RED + STARS
    print "Error.  No Blazemeter API key specified."
    print STARS + LABEL_NO_COLOR
    sys.exit(1)

if not TEST_ID:
    print LABEL_RED + STARS
    print "Error. No test id specified."
    print STARS + LABEL_NO_COLOR
    sys.exit(1)


LOGGER.info("Starting test.  [Test Id: %s]" % TEST_ID)

res = test_start(TEST_ID)

if res.status_code == 200:
    sessionId = res.json()["result"].get("sessionsId")[0]
    if sessionId:
        LOGGER.info("Test started successfully.  [Session Id: %s]" % sessionId)

        status = None
        while True:
            res = test_monitor(sessionId)
            res_json = res.json()
            # print_json(res_json)
            newStatus = res_json["result"].get("status")
            if newStatus != status:
                status = newStatus
                # statusCode = res_json["result"].get("statusCode")
                LOGGER.info(status)
            if status == "ENDED":
                break
            time.sleep(POLL_TIME)

    dataUrl = res_json["result"].get("dataUrl")

    print LABEL_GREEN + STARS
    print "Test completed successfully."
    print "See executive summary at: " + EXEC_REPORT % sessionId
    print "See logs and detailed reports at: " + dataUrl
    print LABEL_GREEN + STARS + LABEL_NO_COLOR
