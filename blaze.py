#!/usr/bin/python

import requests
import sys
import json
import time
import logging
import os

BLZ_URL = "https://a.blazemeter.com"
API_KEY = "e30010e6a8f498ffc4fd"
TEST_ID = "5085122"
POLL_TIME = 30
EXEC_REPORT = BLZ_URL + "/app/printable-report/index.html?base_url=&session_id=%s"
DEBUG = os.environ.get('DEBUG')


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


# Start
# Needed to get rid of InsecureRequestWarning
logging.captureWarnings(True)
LOGGER = setup_logging()
LOGGER.info("Starting test.  [Test Id: %s]" % TEST_ID)

print "Can you see this?"

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
    LOGGER.info("Test completed.")
    LOGGER.info("See executive summary at: " + EXEC_REPORT % sessionId)
    LOGGER.info("See logs and detailed reports at: " + dataUrl)
