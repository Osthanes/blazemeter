#!/usr/bin/python

import requests
import sys
import json
import time
import logging
import os
import urllib2
from prettytable import PrettyTable

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
APP_URL = os.getenv('APP_URL')
APP_NAME = os.getenv('APP_NAME')
EXT_DIR = os.getenv('EXT_DIR', ".")


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


def get_tests():
    url = (BLZ_URL + "/api/latest/tests")
    try:
        response = request(url)
        response.raise_for_status()
        return response
    except requests.exceptions.RequestException as e:
        print e
        sys.exit(1)


def create_test():
    url = (BLZ_URL + "/api/latest/tests")
    headers = {'x-api-key': API_KEY}
    print APP_URL
    try:
        with open(EXT_DIR + '/blazemeter-test.json') as data_file:
            test_data = json.load(data_file)
            test_data["configuration"].get("plugins").get("http").get("pages")[0]["url"] = "http://%s" % APP_URL
        response = requests.post(url, data=json.dumps(test_data), headers=headers)
        response.raise_for_status()
        return response
    except requests.exceptions.RequestException as e:
        print e
        sys.exit(1)


def get_logs(session_id):
    url = (BLZ_URL + "/api/latest/sessions/{0}/reports/logs/").format(session_id)
    try:
        response = request(url)
        response.raise_for_status()
        return response
    except requests.exceptions.RequestException as e:
        print e
        sys.exit(1)


def get_summary(session_id):
    url = (BLZ_URL + "/api/latest/sessions/{0}/reports/main/summary").format(session_id)
    try:
        response = request(url)
        response.raise_for_status()
        return response
    except requests.exceptions.RequestException as e:
        print e
        sys.exit(1)


def create_summary_table(session_id):
    response = get_summary(session_id)
    response_json = response.json()
    fields = response_json["result"].get("availableFields")

    labels = ["Label", "# Samples", "Avg. Latency", "Avg. Response Time", "Geo. Mean Response Time",
              "StDev", "90% Line", "95% Line", "99% Line", "Min", "Max", "Avg. Bandwidth",
              "Avg. Throughput", "Error %", "Duration"]

    table = PrettyTable(labels)
    table.align["Label"] = "l"

    for summary_data in response_json["result"].get("summary"):
        row_data = []
        for field in fields:
            if field == "id":
                field = "lb"
            if field != "bytesGeoMean":
                row_data.append(str(summary_data.get(field)))
        table.add_row(row_data)

    return table


def print_summary(session_id):
    print
    print LABEL_GREEN + STARS + STARS
    print "Test completed successfully."
    print
    print create_summary_table(sessionId)
    print
    print "See executive summary at: " + EXEC_REPORT % sessionId
    print LABEL_GREEN + STARS + STARS + LABEL_NO_COLOR


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
    LOGGER.info("No test id specified.  Looking for existing test in Blazemeter project.")
    res = get_tests();
    tests = res.json()["result"]
    for test in tests:
        if test.get("projectId") == "bluemix-devops":
            LOGGER.info("Existing test found.")
            TEST_ID = test.get("id")
            break

if not TEST_ID:
    LOGGER.info("No existing test found in Blazemeter project.  Creating sample test.")
    res = create_test();
    TEST_ID = res.json()["result"].get("id")

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
            newStatus = res_json["result"].get("status")
            if newStatus != status:
                status = newStatus
                LOGGER.info(status)
            if status == "ENDED":
                break
            time.sleep(POLL_TIME)

    LOG_ZIP = "jtls_and_more.zip"
    res = get_logs(sessionId)
    res_json = res.json()
    for data in res_json["result"].get("data"):
        if data['filename'] == LOG_ZIP:
            dataUrl = data["dataUrl"]
            break

    if dataUrl:
        open(LOG_ZIP, 'wb').write(urllib2.urlopen(dataUrl).read())
        LOGGER.info("Log files downloaded successfully.")

    print_summary(sessionId)
