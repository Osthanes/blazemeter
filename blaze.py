import requests
import sys
import json
import time

BLZ_URL = "https://a.blazemeter.com"
API_KEY = "e30010e6a8f498ffc4fd"
TEST_ID = "5085122"
POLL_TIME = 30
EXEC_REPORT = BLZ_URL + "/app/printable-report/index.html?base_url=&session_id=%s"


def request(url):
    headers = {'x-api-key': API_KEY}
    return requests.get(url, headers=headers)


def print_json(obj):
    print json.dumps(obj, indent=4, sort_keys=True)


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
print "Starting test.  [Test Id: %s]" % TEST_ID
res = test_start(TEST_ID)

if res.status_code == 200:
    sessionId = res.json()["result"].get("sessionsId")[0]
    if sessionId:
        print "Test started successfully.  [Session Id: %s]\n" % sessionId

        status = None
        while True:
            res = test_monitor(sessionId)
            res_json = res.json()
            # print_json(res_json)
            newStatus = res_json["result"].get("status")
            if newStatus != status:
                status = newStatus
                statusCode = res_json["result"].get("statusCode")
                print "Status: %s, Status-Code: %s" % (status, statusCode)
            if status == "ENDED":
                break
            time.sleep(POLL_TIME)

    dataUrl = res_json["result"].get("dataUrl")
    print "\nTest completed."
    print "See executive summary at: " + EXEC_REPORT % sessionId
    print "See logs and detailed reports at: " + dataUrl

