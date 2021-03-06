############################################################################
#                                                                          #
# Copyright 2014 Prelert Ltd                                               #
#                                                                          #
# Licensed under the Apache License, Version 2.0 (the "License");          #
# you may not use this file except in compliance with the License.         #
# You may obtain a copy of the License at                                  #
#                                                                          #
#    http://www.apache.org/licenses/LICENSE-2.0                            #
#                                                                          #
# Unless required by applicable law or agreed to in writing, software      #
# distributed under the License is distributed on an "AS IS" BASIS,        #
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. #
# See the License for the specific language governing permissions and      #
# limitations under the License.                                           #
#                                                                          #
############################################################################
"""
A simple HTTP client to the Prelert Engine REST API
"""

import httplib
import urllib
import json
import logging

class EngineApiClient:


    def __init__(self, host, base_url, port=8080):
        """
        Create a HTTP connection to host:port
        host is the host machine
        base_url is the API URl this should contain the version number
          e.g. /engine/v1
        The default port is 8080
        """
        self.host = host

        # ensure the base url starts with "/"
        if not base_url.startswith("/"):
            base_url = "/" + base_url

        logging.info("Connecting to Engine REST API at {0}:{1}{2}".format(host,
            port, base_url))
        self.base_url = base_url
        self.connection = httplib.HTTPConnection(host, port)


    def getJob(self, job_id):
        """
        Get the job for id.
        Returns a (http_status_code, response) tuple, if http_status_code != 200
        response is an error message
        """

        self.connection.connect()

        self.connection.request("GET", self.base_url + "/jobs/" + job_id)
        response = self.connection.getresponse();

        if response.status != 200:
            logging.error("Get job response = " + str(response.status) + " "
                + response.reason)
        else:
            logging.debug("Get job response = " + str(response.status))

        data = response.read()
        if data:
            job = json.loads(data)
        else:
            job = dict()

        self.connection.close()

        return (response.status, job)


    def getJobs(self, skip=0, take=100):
        '''
        Get the first page of jobs in the system.
        Defaults to the first 100 jobs use the skip and take parameters
        to get further pages.
        skip the first N jobs
        take a maxium of this number of jobs
        Returns a (http_status_code, response) tuple, if http_status_code != 200
        response is an error message
        '''

        url = self.base_url + "/jobs?skip={0}&take={1}".format(skip, take)

        self.connection.connect()
        self.connection.request("GET", self.base_url + "/jobs")
        response = self.connection.getresponse();

        if response.status != 200:
            logging.error("Get jobs response = " + str(response.status) + " "
                + response.reason)
        else:
            logging.debug("Get jobs response = " + str(response.status))

        data = response.read()
        if data:
            jobs = json.loads(data)
        else:
            jobs = dict()


        self.connection.close()

        return (response.status, jobs)


    def createJob(self, payload):
        """
        Create a new job.  Payload is the Json format job creation string.
        Returns a (http_status_code, json) tuple.  If http_status_code == 201
        the JSON result doc will have an 'id' field set to the newly created
        job id else json will be an error document.
        """
        headers = {'Content-Type':'application/json'}

        self.connection.connect()
        self.connection.request("POST", self.base_url + "/jobs", payload, headers)

        response = self.connection.getresponse();

        if response.status != 201:
            logging.error("Create job response = " + str(response.status) + " "
                + response.reason)
        else:
            logging.debug("Create job response = " + str(response.status))

        data = response.read()
        if data:
            doc = json.loads(data)
        else:
            doc = dict()

        self.connection.close()

        return (response.status, doc)


    def upload(self, job_id, data, gzipped=False):
        """
        Upload data to the jobs data endpoint.
        Data can be a string or an open file object.
        If the data is gzipped compressed set gzipped to True

        Returns a (http_status_code, response_data) tuple, if
        http_status_code != 202 response_data is an error message.
        """
        headers = {}
        if gzipped:
            headers['Content-Encoding'] = 'gzip'

        url = self.base_url + "/data/" + job_id

        self.connection.connect()
        self.connection.request("POST", url, data, headers)
        response = self.connection.getresponse();
        if response.status != 202:
            logging.error("Upload file response = " + str(response.status)
                + " " + response.reason)
        else:
            logging.debug("Upload response = " + str(response.status))

        # read all of the response before another request can be made
        data = response.read()
        if data:
            doc = json.loads(data)
        else:
            doc = dict()

        self.connection.close()

        return (response.status, doc)


    def stream(self, job_id, data, gzipped=False):
        """
        A Generator co-routine for uploading data in an *almost* asynchronous
        manner using chunked transfer encoding. This function uses the yield
        statment to receive a data record then chunk encodes the record and
        writes it into the open upload stream.

        First the generator must be initialised by calling send(None)
        this runs the code up to the first yield statement

            consumer = engineApiClient.stream(job_id, first_line_of_data)
            consumer.send(None)  # init generator, runs code up to first yield

        After this data can be sent iteratively by repeatedly calling the send
        method with new data. CSV records must end in a newline character.

            for record in data:
                consumer.send(record + '\n')

        When all the data is sent call send with an empty string and the
        respone is returned.

            (http_status, response) = consumer.send('')

        """

        url = self.base_url + "/data/" + job_id

        self.connection.connect()

        self.connection.putrequest("POST", url)
        self.connection.putheader("Connection", "Keep-Alive")
        self.connection.putheader("Transfer-Encoding", "chunked")
        self.connection.putheader("Content-Type", "application/x-www-form-urlencoded")
        if gzipped:
            self.connection.putheader('Content-Encoding', 'gzip')
        self.connection.endheaders()

        while data:
            # Send in chunked transfer encoding format. Write the hexidecimal
            # length of the data message followed by '\r\n' followed by the
            # data and another '\r\n'

            # strip the '0x' of the hex string
            data_len = hex(len(data))[2:]
            msg = data_len + '\r\n' + data + '\r\n'

            self.connection.send(msg)
            data = yield

        # End chunked transfer encoding by sending the zero length message
        msg = '0\r\n\r\n'
        self.connection.send(msg)

        response = self.connection.getresponse();
        if response.status != 202:
            logging.error("Upload file response = " + str(response.status)
                + " " + response.reason)
        else:
            logging.debug("Upload response = " + str(response.status))


        # read all of the response before another request can be made
        data = response.read()
        if data:
            doc = json.loads(data)
        else:
            doc = dict()

        self.connection.close()

        yield (response.status, doc)


    def close(self, job_id):
        """
        Close the job once data has been streamed
        Returns a (http_status_code, response_data) tuple, if
        http_status_code != 202 response_data is an error object.
        """

        url = self.base_url + "/data/" + job_id + "/close"

        self.connection.connect()
        self.connection.request("POST", url)
        response = self.connection.getresponse()
        if response.status != 202:
            logging.error("Close response = " + str(response.status) + " "
                + response.reason)
        else:
            logging.debug("Close response data = " + response.read())

        # read all of the response before another request can be made
        data = response.read()
        if data:
            msg = json.loads(data)
        else:
            msg = dict()

        self.connection.close()

        return (response.status, msg)

    def flush(self, job_id, calc_interim=False):
        """
        Flush the job, such that when this call returns no data is
        being held in buffers.
        If calc_interim is set to True then interim results for the
        most recent incomplete bucket will be calculated.
        Returns a (http_status_code, response_data) tuple, if
        http_status_code != 200 response_data is an error object.
        """

        url = self.base_url + "/data/" + job_id + "/flush"
        if calc_interim:
            url += "?calcInterim=true"

        self.connection.connect()
        self.connection.request("POST", url)
        response = self.connection.getresponse()
        if response.status != 200:
            logging.error("Flush response = " + str(response.status) + " "
                + response.reason)
        else:
            logging.debug("Flush response data = " + response.read())

        # read all of the response before another request can be made
        data = response.read()
        if data:
            msg = json.loads(data)
        else:
            msg = dict()

        self.connection.close()

        return (response.status, msg)

    def getBucket(self, job_id, bucket_id, include_records=False,
                  include_interim=False):
        '''
        Get the individual result bucket for the job and bucket id
        If include_records is True the anomaly records are nested in the
        resulting dictionary.
        If include_interim is True then interim results will be returned as
        well as final results.

        Returns a (http_status_code, bucket) tuple if successful else
        if http_status_code != 200 (http_status_code, error_doc) is
        returned
        '''

        query_char = '?'
        query = ''
        if include_records:
            query = query_char + 'expand=true'
            query_char = '&'
        if include_interim:
            query += query_char + 'includeInterim=true'
            query_char = '&'

        headers = {'Content-Type':'application/json'}
        url = self.base_url + "/results/{0}/{1}{2}".format(job_id, bucket_id, query)

        self.connection.connect()
        self.connection.request("GET", url)
        response = self.connection.getresponse();

        if response.status != 200:
            logging.error("Get bucket response = " + str(response.status) + " " + response.reason)
        else:
            logging.debug("Get bucket response = " + str(response.status))

        # read all of the response
        data = response.read()
        if data:
            msg = json.loads(data)
        else:
            msg = dict()

        self.connection.close()

        return (response.status, msg)

    def getBuckets(self, job_id, skip=0, take=100, include_records=False,
                normalized_probability_filter_value=None, anomaly_score_filter_value=None,
                include_interim=False):
        '''
        Return a page of the job's buckets results.
        skip the first N buckets
        take a maximum of this number of buckets
        include_records Anomaly records are included in the buckets.
        normalized_probability_filter_value If not none return only the records with
            a normalizedProbability >= normalized_probability_filter_value
        anomaly_score_filter_value If not none return only the records with
            an anomalyScore >= anomaly_score_filter_value
        include_interim Should interim results be returned as well as final results?

        Returns a (http_status_code, buckets) tuple if successful else
        if http_status_code != 200 a (http_status_code, error_doc) is
        returned
        '''

        query = ''
        if include_records:
            query = '&expand=true'

        if include_interim:
            query += '&includeInterim=true'

        if normalized_probability_filter_value:
            query += '&normalizedProbability=' + str(normalized_probability_filter_value)

        if anomaly_score_filter_value:
            query += '&anomalyScore=' + str(anomaly_score_filter_value)

        headers = {'Content-Type':'application/json'}
        url = self.base_url + "/results/{0}/buckets?skip={1}&take={2}{3}".format(
            job_id, skip, take, query)

        self.connection.connect()
        self.connection.request("GET", url)
        response = self.connection.getresponse();

        if response.status != 200:
            logging.error("Get buckets response = " + str(response.status) + " " + response.reason)
        else:
            logging.debug("Get buckets response = " + str(response.status))

        # read all of the response
        data = response.read()
        if data:
            msg = json.loads(data)
        else:
            msg = dict()

        self.connection.close()

        return (response.status, msg)


    def getBucketsByDate(self, job_id, start_date, end_date, include_records=False,
            normalized_probability_filter_value=None, anomaly_score_filter_value=None,
            include_interim=False):
        """
        Return all the job's buckets results between 2 dates.  If there is more
        than one page of results for the given data range this function will
        get them all appending the buckets in a list. A list of buckets is
        returned.

        start_date, end_date Must either be an epoch time or ISO 8601 format
        strings see the Prelert Engine API docs for help.
        include_records Anomaly records are included in the buckets
        normalized_probability_filter_value If not none return only the records with
            a normalizedProbability >= normalized_probability_filter_value
        anomaly_score_filter_value If not none return only the records with
            an anomalyScore >= anomaly_score_filter_value
        include_interim Should interim results be returned as well as final results?

        Returns a (http_status_code, buckets) tuple if successful else
        if http_status_code != 200 a (http_status_code, error_doc) is
        returned
        """

        skip = 0
        take = 100
        expand = ''
        if include_records:
            expand = '&expand=true'

        start_arg = ''
        if start_date:
            start_arg = '&start=' + urllib.quote(start_date)

        end_arg = ''
        if end_date:
            end_arg = '&end=' + urllib.quote(end_date)

        score_filter = ''
        if normalized_probability_filter_value:
            score_filter = '&normalizedProbability=' + str(normalized_probability_filter_value)

        if anomaly_score_filter_value:
            score_filter += '&anomalyScore=' + str(anomaly_score_filter_value)

        include_interim_arg = ''
        if include_interim:
            include_interim_arg = '&includeInterim=true'

        headers = {'Content-Type':'application/json'}
        url = self.base_url + "/results/{0}/buckets?skip={1}&take={2}{3}{4}{5}{6}{7}".format(job_id,
            skip, take, expand, start_arg, end_arg, score_filter, include_interim_arg)

        self.connection.connect()
        self.connection.request("GET", url)
        response = self.connection.getresponse();

        if response.status != 200:
            logging.error("Get buckets by date response = " + str(response.status) + " " + response.reason)
            response_data = json.load(response)
            return (response.status, response_data)
        else:
            logging.debug("Get buckets by date response = " + str(response.status))


        result = json.load(response)
        buckets = result['documents']

        # is there another page of results
        while result['nextPage']:
            skip += take
            url = self.base_url + "/results/{0}/buckets?skip={1}&take={2}{3}{4}{5}".format(job_id,
                                skip, take, expand, start_arg, end_arg)
            self.connection.request("GET", url)
            response = self.connection.getresponse();
            if response.status != 200:
                logging.error("Get buckets by date response = " + str(response.status) + " " + response.reason)
                message = json.load(response)

                if message:
                    message = json.loads(message)

                self.connection.close()
                return (response.status, message)

            result = json.load(response)
            buckets.extend(result['documents'])

        self.connection.close()

        return (200, buckets)


    def getAllBuckets(self, job_id, include_records=False,
                normalized_probability_filter_value=None, anomaly_score_filter_value=None,
                include_interim=False):
        """
        Return all the job's buckets results.  If more than 1
        page of buckets are available continue to with the next
        page until all results have been read. An array of buckets is
        returned.

        include_records Anomaly records are included in the buckets
        normalized_probability_filter_value If not none return only the records with
            a normalizedProbability >= normalized_probability_filter_value
        anomaly_score_filter_value If not none return only the records with
            an anomalyScore >= anomaly_score_filter_value
        include_interim Should interim results be returned as well as final results?

        Returns a (http_status_code, buckets) tuple if successful else
        if http_status_code != 200 a (http_status_code, error_doc) tuple
        is returned
        """

        skip = 0
        take = 100
        expand = ''
        if include_records:
            expand = '&expand=true'

        score_filter = ''
        if normalized_probability_filter_value:
            score_filter = '&normalizedProbability=' + str(normalized_probability_filter_value)

        if anomaly_score_filter_value:
            score_filter += '&anomalyScore=' + str(anomaly_score_filter_value)

        include_interim_arg = ''
        if include_interim:
            include_interim_arg = '&includeInterim=true'

        headers = {'Content-Type':'application/json'}
        url = self.base_url + "/results/{0}/buckets?skip={1}&take={2}{3}{4}{5}".format(
            job_id, skip, take, expand, score_filter, include_interim_arg)


        self.connection.connect()
        self.connection.request("GET", url)
        response = self.connection.getresponse();

        if response.status != 200:
            logging.error("Get all buckets response = " + str(response.status) + " " + response.reason)
            response_data = json.load(response)
            return (response.status, response_data)
        else:
            logging.debug("Get all buckets response = " + str(response.status))


        result = json.load(response)
        buckets = result['documents']

        # is there another page of results
        while result['nextPage']:
            skip += take
            url = self.base_url + "/results/{0}/buckets?skip={1}&take={2}{3}{4}".format(
                job_id, skip, take, expand, score_filter)

            self.connection.request("GET", url)
            response = self.connection.getresponse();
            if response.status != 200:
                logging.error("Get all buckets response = " + str(response.status) + " " + response.reason)

                message = json.load(response)
                if message:
                    message = json.loads(message)

                self.connection.close()
                return (response.status, message)

            result = json.load(response)
            buckets.extend(result['documents'])

        self.connection.close()

        return (200, buckets)


    def getRecords(self, job_id, skip=0, take=100, start_date=None,
            end_date=None, sort_field=None, sort_descending=True,
            normalized_probability_filter_value=None, anomaly_score_filter_value=None,
            include_interim=False):
        """
        Get a page of the job's anomaly records.
        Records can be filtered by start & end date parameters and the scores.

        skip the first N buckets
        take a maxium of this number of buckets
        include_records Anomaly records are included in the buckets.
        start_date, end_date Must either be an epoch time or ISO 8601 format
            see the Prelert Engine API docs for help
        sort_field The field to sort the results by, ignored if None
        sort_descending If sort_field is not None then sort records
            in descending order if True else sort ascending
        normalized_probability_filter_value If not none return only the records with
            a normalizedProbability >= normalized_probability_filter_value
        anomaly_score_filter_value If not none return only the records with
            an anomalyScore >= anomaly_score_filter_value
        include_interim Should interim results be returned as well as final results?

        Returns a (http_status_code, records) tuple if successful else
        if http_status_code != 200 a (http_status_code, error_doc) is
        returned
        """

        start_arg = ''
        if start_date:
            start_arg = '&start=' + urllib.quote(start_date)

        end_arg = ''
        if end_date:
            end_arg = '&end=' + urllib.quote(end_date)

        sort_arg = ''
        if sort_field:
            sort_arg = "&sort=" + urllib.quote(sort_field) + '&desc=' + ('true' if sort_descending else 'false')

        filter_arg = ''
        if normalized_probability_filter_value:
            filter_arg = '&normalizedProbability=' + str(normalized_probability_filter_value)

        if anomaly_score_filter_value:
            filter_arg += '&anomalyScore=' + str(anomaly_score_filter_value)

        include_interim_arg = ''
        if include_interim:
            include_interim_arg = '&includeInterim=true'

        headers = {'Content-Type':'application/json'}
        url = self.base_url + "/results/{0}/records?skip={1}&take={2}{3}{4}{5}{6}{7}".format(
            job_id, skip, take, start_arg, end_arg, sort_arg, filter_arg, include_interim_arg)

        self.connection.connect()
        self.connection.request("GET", url)
        response = self.connection.getresponse();

        if response.status != 200:
            logging.error("Get records response = " + str(response.status) + " " + response.reason)
        else:
            logging.debug("Get records response = " + str(response.status))

        # read all of the response
        data = response.read()
        if data:
            msg = json.loads(data)
        else:
            msg = dict()

        self.connection.close()

        return (response.status, msg)


    def alerts_longpoll(self, job_id, normalized_probability_threshold=None,
        anomaly_score_threshold=None, timeout=None):
        """
        Subscribe to the long poll alerts endpoint. Alerts are fired when
        a bucket has an anomaly score >= anomaly_score_threshold or the
        bucket has records with normalised probability >=
        normalized_probability_threshold.

        Returns a (http_status_code, alert) tuple if successful else
        if http_status_code != 200 a (http_status_code, error_doc) is
        returned

        If the long poll times out an alert object is returned but the
        'timeout' field will be set true.
        """

        query_char = '?'

        prob_arg = ''
        if normalized_probability_threshold:
            prob_arg = query_char + 'probability=' + str(normalized_probability_threshold)
            query_char = '&'

        score_arg = ''
        if anomaly_score_threshold:
            score_arg = query_char + 'score=' + str(anomaly_score_threshold)
            query_char = '&'

        timeout_arg = ''
        if timeout:
            timeout_arg = query_char + 'timeout=' + str(timeout)

        url = self.base_url + "/alerts_longpoll/{0}/{1}{2}{3}".format(
            job_id, prob_arg, score_arg, timeout_arg)

        self.connection.connect()
        self.connection.request("GET", url)
        response = self.connection.getresponse();

        # read all of the response
        data = response.read()
        if data:
            msg = json.loads(data)
        else:
            msg = dict()

        if response.status != 200:
            logging.error("Subscribe alerts response = " + str(response.status))
        else:
            logging.debug("Subscribe alerts response = " + str(response.status))

        self.connection.close()

        return (response.status, msg)


    def delete(self, job_id):
        """
        Delete a job.
        Returns a (http_status_code, response_data) tuple, if
        http_status_code != 200 response_data is an error object.
        """

        url = self.base_url + "/jobs/" + job_id
        self.connection.connect()
        self.connection.request("DELETE", url)

        response = self.connection.getresponse()
        if response.status != 200:
            logging.error("Delete response = " + str(response.status) + " "
                + response.reason)

        data = response.read()
        if data:
            msg = json.loads(data)
        else:
            msg = dict()

        self.connection.close()

        return (response.status, msg)

    def getZippedLogs(self, job_id):
        """
        Download the zipped log files and
        return a tuple of (http_status_code, zip_data) if http_status_code
        == 200 else the error is read into a json document and
        returns (http_status_code, error_doc)
        """

        self.connection.connect()
        self.connection.request("GET", self.base_url + "/logs/" + job_id)
        response = self.connection.getresponse();

        if response.status != 200:
            logging.error("Get logs response = " + str(response.status) + " " + response.reason)
            response_data = response.read()
            if response_data:
                response_data = json.loads(response_data)
        else:
            logging.debug("Get zipped logs response = " + str(response.status))
            response_data = response.read()

        self.connection.close()

        return (response.status, response_data)

