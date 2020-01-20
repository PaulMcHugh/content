
import demistomock as demisto
from CommonServerPython import *
from CommonServerUserPython import *

''' IMPORTS '''
import ast
import json
import urllib3
import urllib.parse
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

''' GLOBALS/PARAMS '''
FETCH_TIME = demisto.params().get('fetch_time')
DATE_FORMAT = '%Y-%m-%dT%H:%M:%S.%fZ'

PROCESS_TEXT = 'Process information for process with PTID'
PARENT_PROCESS_TEXT = 'Parent process for process with PTID'
PROCESS_CHILDREN_TEXT = 'Children for process with PTID'


class Client(BaseClient):
    def __init__(self, base_url, username, password, **kwargs):
        self.username = username
        self.password = password
        self.session = ''
        super(Client, self).__init__(base_url, **kwargs)

    def do_request(self, method, url_suffix, data=None, params=None, resp_type='json'):
        if not self.session:
            self.update_session()
        res = self._http_request(method, url_suffix, headers={'session': self.session}, json_data=data,
                                 params=params, resp_type='response', ok_codes=(200, 201, 202, 204, 400, 403, 404))

        # if session expired
        if res.status_code == 403:
            self.update_session()
            res = self._http_request(method, url_suffix, headers={'session': self.session}, json_data=data,
                                     params=params, ok_codes=(200, 400, 404))
            return res

        if res.status_code == 404 or res.status_code == 400:
            if res.content:
                raise requests.HTTPError(str(res.content))
            if res.reason:
                raise requests.HTTPError(str(res.reason))
            raise requests.HTTPError(res.json().get('text'))

        if resp_type == 'json':
            return res.json()
        if resp_type == 'text':
            return res.text, res.headers.get('Content-Disposition')
        if resp_type == 'content':
            return res.text, res.headers.get('Content-Disposition')

    def update_session(self):
        body = {
            'username': self.username,
            'password': self.password
        }

        res = self._http_request('GET', '/api/v2/session/login', json_data=body, ok_codes=(200,))

        self.session = res.get('data').get('session')
        return self.session

    def login(self):
        return self.update_session()

    def alarm_to_incident(self, alarm):
        intel_doc_id = alarm.get('intelDocId', '')
        host = alarm.get('computerName', '')
        details = alarm.get('details')

        if details:
            details = json.loads(alarm['details'])
            alarm['details'] = details

        intel_doc = ''
        if intel_doc_id:
            raw_response = self.do_request('GET', f'/plugin/products/detect3/api/v1/intels/{intel_doc_id}')
            intel_doc = raw_response.get('name')

        return {
            'name': f'{host} found {intel_doc}',
            'occurred': alarm.get('alertedAt'),
            'rawJSON': json.dumps(alarm)}

    def get_intel_doc_item(self, intel_doc):
        return {
            'ID': intel_doc.get('id'),
            'Name': intel_doc.get('name'),
            'Description': intel_doc.get('description'),
            'AlertCount': intel_doc.get('alertCount'),
            'UnresolvedAlertCount': intel_doc.get('unresolvedAlertCount'),
            'CreatedAt': intel_doc.get('createdAt'),
            'UpdatedAt': intel_doc.get('updatedAt'),
            'LabelIds': intel_doc.get('labelIds')}

    def get_alert_item(self, alert):
        return {
            'ID': alert.get('id'),
            'AlertedAt': alert.get('alertedAt'),
            'ComputerIpAddress': alert.get('computerIpAddress'),
            'ComputerName': alert.get('computerName'),
            'CreatedAt': alert.get('createdAt'),
            'GUID': alert.get('guid'),
            'IntelDocId': alert.get('intelDocId'),
            'Priority': alert.get('priority'),
            'Severity': alert.get('severity'),
            'State': alert.get('state').title(),
            'Type': alert.get('type'),
            'UpdatedAt': alert.get('updatedAt')}

    def get_snapshot_items(self, raw_snapshots, limit):
        snapshots = []
        count = 0

        for host in raw_snapshots.items():
            for key in host[1].items():
                snapshots.append({
                    'DirectoryName': host[0],
                    'FileName': key[0],
                    'Started': key[1].get('started', ''),
                    'State': key[1].get('state', ''),
                    'Error': key[1].get('error', ''),
                })
                count += 1
                if count == limit:
                    return snapshots

        return snapshots

    def get_local_snapshot_items(self, raw_snapshots, limit):
        snapshots = []
        count = 0

        for host in raw_snapshots.items():
            for snapshot in host[1]:
                snapshots.append({
                    'DirectoryName': host[0],
                    'FileName': snapshot
                })
                count += 1
                if count == limit:
                    return snapshots

        return snapshots

    def get_connection_item(self, connection):
        info = connection.get('info')
        return {
            'Name': connection.get('name'),
            'State': info.get('state'),
            'CreateTime': info.get('createTime'),
            'DST': info.get('dst'),
            'Remote': info.get('remote'),
            'OsName': connection.get('osName')}

    def get_label_item(self, label):
        return {
            'ID': label.get('id'),
            'Name': label.get('name'),
            'Description': label.get('description'),
            'IndicatorCount': label.get('indicatorCount'),
            'SignalCount': label.get('signalCount'),
            'CreatedAt': label.get('createdAt'),
            'UpdatedAt': label.get('updatedAt')}

    def get_file_download_item(self, file):
        return {
            'ID': file.get('id'),
            'Host': file.get('host'),
            'Path': file.get('path'),
            'SPath': file.get('spath'),
            'Hash': file.get('hash'),
            'Size': file.get('size'),
            'Created': file.get('created'),
            'CreatedBy': file.get('created_by'),
            'CreatedByProc': file.get('created_by_proc'),
            'LastModified': file.get('last_modified'),
            'LastModifiedBy': file.get('last_modified_by'),
            'LastModifiedByProc': file.get('last_modified_by_proc'),
            'Downloaded': file.get('downloaded'),
            'Comments': file.get('comments'),
            'Tags': file.get('tags')
        }

    def get_file_item(self, file):
        file_item = {
            'Created': timestamp_to_datestring(file.get('created'), '%Y-%m-%d %H:%M:%S'),
            'Path': file.get('file-path'),
            'IsDirectory': file.get('is-directory'),
            'LastModified': timestamp_to_datestring(file.get('last-modified'), '%Y-%m-%d %H:%M:%S'),
            'Permissions': file.get('permissions'),
            'Size': file.get('size')
        }
        return {key: val for key, val in file_item.items() if val is not None}

    def get_event_item(self, raw_event, event_type):
        event = {
            'ID': raw_event.get('id'),
            'Domain': raw_event.get('domain'),
            'File': raw_event.get('file'),
            'Operation': raw_event.get('operation'),
            'ProcessID': raw_event.get('process_id'),
            'ProcessName': raw_event.get('process_name'),
            'ProcessTableID': raw_event.get('process_table_id'),
            'Timestamp': raw_event.get('timestamp'),
            'Username': raw_event.get('username'),
            'DestinationAddress': raw_event.get('destination_addr'),
            'DestinationPort': raw_event.get('destination_port'),
            'SourceAddress': raw_event.get('source_addr'),
            'SourcePort': raw_event.get('source_port'),
            'KeyPath': raw_event.get('key_path'),
            'ValueName': raw_event.get('value_name'),
            'EndTime': raw_event.get('end_time'),
            'ExitCode': raw_event.get('exit_code'),
            'ProcessCommandLine': raw_event.get('process_command_line'),
            'ProcessHash': raw_event.get('process_hash'),
            'SID': raw_event.get('sid'),
            'Hashes': raw_event.get('Hashes'),
            'ImageLoaded': raw_event.get('ImageLoaded'),
            'Signature': raw_event.get('Signature'),
            'Signed': raw_event.get('Signed'),
            'EventId': raw_event.get('event_id'),
            'EventOpcode': raw_event.get('event_opcode'),
            'EventRecordID': raw_event.get('event_record_id'),
            'EventTaskID': raw_event.get('event_task_id'),
            'Query': raw_event.get('query'),
            'Response': raw_event.get('response')
        }

        if event_type == 'combined':
            event['Type'] = raw_event.get('type')
        else:
            event['Type'] = event_type.upper() if event_type in ['dns', 'sid'] else event_type.title()

        # remove empty values from the event item
        return {k: v for k, v in event.items() if v is not None}

    def get_process_item(self, raw_process):
        return {
            'CreateTime': raw_process.get('create_time'),
            'Domain': raw_process.get('domain'),
            'ExitCode': raw_process.get('exit_code'),
            'ProcessCommandLine': raw_process.get('process_command_line'),
            'ProcessID': raw_process.get('process_id'),
            'ProcessName': raw_process.get('process_name'),
            'ProcessTableId': raw_process.get('process_table_id'),
            'SID': raw_process.get('sid'),
            'Username': raw_process.get('username')
        }

    def get_process_event_item(self, raw_event):
        return {
            'ID': raw_event.get('id'),
            'Detail': raw_event.get('detail'),
            'Operation': raw_event.get('operation'),
            'Timestamp': raw_event.get('timestamp'),
            'Type': raw_event.get('type')
        }

    def get_process_tree_item(self, raw_item, level):
        tree_item = {
            'ID': raw_item.get('id'),
            'PTID': raw_item.get('ptid'),
            'PID': raw_item.get('pid'),
            'Name': raw_item.get('name'),
            'Parent': raw_item.get('parent'),
            'Children': raw_item.get('children')
        }

        human_readable = tree_item.copy()
        del human_readable['Children']

        children = tree_item.get('Children')
        if children and level == 1:
            human_readable['ChildrenCount'] = len(children)
        if not children and level == 1:
            human_readable['ChildrenCount'] = 0
        elif children and level == 0:
            human_readable_arr = []
            output_arr = []
            for item in children:
                tree_output, human_readable_res = self.get_process_tree_item(item, level + 1)
                human_readable_arr.append(human_readable_res)
                output_arr.append(tree_output)

            human_readable['Children'] = human_readable_arr
            tree_item['Children'] = output_arr

        return tree_item, human_readable

    def get_evidence_item(self, raw_item):
        evidence_item = {
            'ID': raw_item.get('id'),
            'CreatedAt': raw_item.get('created'),
            'UpdatedAt': raw_item.get('lastModified'),
            'User': raw_item.get('user'),
            'Host': raw_item.get('host'),
            'ConnectionID': raw_item.get('connId'),
            'Type': raw_item.get('type'),
            'ProcessTableId': raw_item.get('sID'),
            'Timestamp': raw_item.get('sTimestamp'),
            'Summary': raw_item.get('summary'),
            'Comments': raw_item.get('comments'),
            'Tags': raw_item.get('tags')
        }
        return {key: val for key, val in evidence_item.items() if val is not None}

    def parse_events_by_category(self, events, category_name):
        # todo: If possible, complete method (parse). Otherwise, remove this method and pass events list as is.
        parsed_events = events
        if category_name.lower() == 'file':
            pass
        elif category_name.lower() == 'dns':
            pass
        elif category_name.lower() == 'registry':
            pass
        elif category_name.lower() == 'network':
            pass
        elif category_name.lower() == 'image':
            pass
        else:  # category_name.lower() == 'process'
            pass
        return parsed_events

    def get_process_timeline_item(self, raw_item, category_name, limit, offset):
        timeline_item = []
        for category in raw_item:
            if category['name'].lower() == category_name.lower():
                sorted_timeline_dates = sorted(category['details'].keys())
                for i in range(offset, offset + limit):
                    current_date = sorted_timeline_dates[i]
                    events_in_current_date = category['details'][current_date]
                    events_for_date_i = self.parse_events_by_category(events_in_current_date, category_name)
                    timeline_item.append({
                        'Date': sorted_timeline_dates[i],
                        'Category': category_name,
                        'Event': events_for_date_i
                    })

        return timeline_item


''' COMMANDS + REQUESTS FUNCTIONS '''


def test_module(client, data_args):
    if client.login():
        return demisto.results('ok')
    raise ValueError('Test Tanium integration failed - please check your username and password')


def get_intel_doc(client, data_args):
    id_ = data_args.get('intel-doc-id')
    raw_response = client.do_request('GET', f'/plugin/products/detect3/api/v1/intels/{id_}')
    intel_doc = client.get_intel_doc_item(raw_response)

    context = createContext(intel_doc, removeNull=True)
    outputs = {'Tanium.IntelDoc(val.ID && val.ID === obj.ID)': context}

    intel_doc['LabelIds'] = str(intel_doc['LabelIds']).strip('[]')
    human_readable = tableToMarkdown('Intel Doc information', intel_doc)
    return human_readable, outputs, raw_response


def get_intel_docs(client, data_args):
    limit = int(data_args.get('limit'))
    raw_response = client.do_request('GET', '/plugin/products/detect3/api/v1/intels/', params={'limit': limit})

    intel_docs = []
    for item in raw_response:
        intel_doc = client.get_intel_doc_item(item)
        intel_docs.append(intel_doc)

    context = createContext(intel_docs, removeNull=True)
    outputs = {'Tanium.IntelDoc(val.ID && val.ID === obj.ID)': context}

    for item in intel_docs:
        item['LabelIds'] = str(item['LabelIds']).strip('[]')

    human_readable = tableToMarkdown('Intel docs', intel_docs)
    return human_readable, outputs, raw_response


def get_alerts(client, data_args):
    limit = int(data_args.get('limit'))
    offset = data_args.get('offset')
    ip_address = data_args.get('computer-ip-address')
    computer_name = data_args.get('computer-name')
    scan_config_id = data_args.get('scan-config-id')
    intel_doc_id = data_args.get('intel-doc-id')
    severity = data_args.get('severity')
    priority = data_args.get('priority')
    type_ = data_args.get('type')
    state = data_args.get('state')

    params = {'type': type_,
              'priority': priority,
              'severity': severity,
              'intelDocId': intel_doc_id,
              'scanConfigId': scan_config_id,
              'computerName': computer_name,
              'computerIpAddress': ip_address,
              'limit': limit,
              'offset': offset}
    if state:
        params['state'] = state.lower()

    raw_response = client.do_request('GET', '/plugin/products/detect3/api/v1/alerts/', params=params)

    alerts = []
    for item in raw_response:
        alert = client.get_alert_item(item)
        alerts.append(alert)

    context = createContext(alerts, removeNull=True)
    outputs = {'Tanium.Alert(val.ID && val.ID === obj.ID)': context}
    human_readable = tableToMarkdown('Alerts', alerts)
    return human_readable, outputs, raw_response


def get_alert(client, data_args):
    alert_id = data_args.get('alert-id')
    raw_response = client.do_request('GET', f'/plugin/products/detect3/api/v1/alerts/{alert_id}')
    alert = client.get_alert_item(raw_response)

    context = createContext(alert, removeNull=True)
    outputs = {'Tanium.Alert(val.ID && val.ID === obj.ID)': context}
    human_readable = tableToMarkdown('Alert information', alert)
    return human_readable, outputs, raw_response


def alert_update_state(client, data_args):
    alert_id = data_args.get('alert-id')
    state = data_args.get('state')

    body = {"state": state.lower()}
    raw_response = client.do_request('PUT', f'/plugin/products/detect3/api/v1/alerts/{alert_id}', data=body)
    alert = client.get_alert_item(raw_response)

    context = createContext(alert, removeNull=True)
    outputs = {'Tanium.Alert(val.ID && val.ID === obj.ID)': context}
    human_readable = tableToMarkdown(f'Alert state updated to {state}', alert)
    return human_readable, outputs, raw_response


def get_snapshots(client, data_args):
    limit = int(data_args.get('limit'))
    raw_response = client.do_request('GET', '/plugin/products/trace/snapshots/')
    snapshots = client.get_snapshot_items(raw_response, limit)
    context = createContext(snapshots, removeNull=True)
    outputs = {'Tanium.Snapshot(val.FileName && val.FileName === obj.FileName)': context}
    human_readable = tableToMarkdown('Snapshots', snapshots)
    return human_readable, outputs, raw_response


def create_snapshot(client, data_args):
    con_id = data_args.get('connection-id')
    client.do_request('POST', f'/plugin/products/trace/conns/{con_id}/snapshots', resp_type='content')
    return f"Initiated snapshot creation request for {con_id}.", {}, {}


def delete_snapshot(client, data_args):
    con_id = data_args.get('connection-id')
    snapshot_id = data_args.get('snapshot-id')
    client.do_request('DELETE', f'/plugin/products/trace/conns/{con_id}/snapshots/{snapshot_id}', resp_type='content')
    return f"Snapshot {snapshot_id} deleted successfully.", {}, {}


def get_local_snapshots(client, data_args):
    limit = int(data_args.get('limit'))
    raw_response = client.do_request('GET', '/plugin/products/trace/locals/')
    snapshots = client.get_local_snapshot_items(raw_response, limit)
    context = createContext(snapshots, removeNull=True)
    outputs = {'Tanium.LocalSnapshot.DirectoryName(val.FileName && val.FileName === obj.FileName)': context}
    human_readable = tableToMarkdown('Local snapshots', snapshots)
    return human_readable, outputs, raw_response


def delete_local_snapshot(client, data_args):
    directory_name = data_args.get('directory-name')
    file_name = data_args.get('file-name')
    client.do_request('DELETE', f'/plugin/products/trace/locals/{directory_name}/{file_name}', resp_type='content')
    return f"Local snapshot from Directory {directory_name} and File {file_name} is deleted successfully.", {}, {}


def get_connections(client, data_args):
    limit = int(data_args.get('limit'))
    raw_response = client.do_request('GET', '/plugin/products/trace/conns')
    connections = []

    for conn in raw_response[:limit]:
        connections.append(client.get_connection_item(conn))

    context = createContext(connections, removeNull=True)
    outputs = {'Tanium.Connection(val.Name && val.Name === obj.Name)': context}
    human_readable = tableToMarkdown('Connections', connections)
    return human_readable, outputs, raw_response


def get_connection(client, data_args):
    conn_name = data_args.get('connection-name')
    raw_response = client.do_request('GET', '/plugin/products/trace/conns')
    connection_raw_response = {}
    found = False
    for conn in raw_response:
        if conn.get('name') and conn['name'] == conn_name:
            connection_raw_response = conn
            found = True
            break

    if not found:
        return 'Connection not found.', {}, {}

    connection = client.get_connection_item(connection_raw_response)

    context = createContext(connection, removeNull=True)
    outputs = {'Tanium.Connection(val.Name && val.Name === obj.Name)': context}
    human_readable = tableToMarkdown('Connection information', connection)
    return human_readable, outputs, connection_raw_response


def create_connection(client, data_args):
    remote = bool(data_args.get('remote'))
    dst_type = data_args.get('destination-type')
    dst = data_args.get('destination')
    conn_timeout = data_args.get('connection-timeout')

    body = {
        "remote": remote,
        "dst": dst,
        "dstType": dst_type,
        "connTimeout": conn_timeout}

    if conn_timeout:
        body['connTimeout'] = int(data_args.get('connection-timeout'))

    client.do_request('POST', f'/plugin/products/trace/conns/', data=body, resp_type='content')
    return f"Initiated connection request to {dst}.", {}, {}


def delete_connection(client, data_args):
    conn_name = data_args.get('connection-name')
    client.do_request('DELETE', f'/plugin/products/trace/conns/{conn_name}', resp_type='text')
    return f"Connection {conn_name} deleted successfully.", {}, {}


def get_labels(client, data_args):
    limit = int(data_args.get('limit'))
    raw_response = client.do_request('GET', '/plugin/products/detect3/api/v1/labels/', params={'limit': limit})

    labels = []
    for item in raw_response:
        label = client.get_label_item(item)
        labels.append(label)

    context = createContext(labels, removeNull=True)
    outputs = {'Tanium.Label(val.ID && val.ID === obj.ID)': context}
    human_readable = tableToMarkdown('Labels', labels)
    return human_readable, outputs, raw_response


def get_label(client, data_args):
    label_id = data_args.get('label-id')
    raw_response = client.do_request('GET', f'/plugin/products/detect3/api/v1/labels/{label_id}')
    label = client.get_label_item(raw_response)

    context = createContext(label, removeNull=True)
    outputs = {'Tanium.Label(val.ID && val.ID === obj.ID)': context}
    human_readable = tableToMarkdown('Label information', label)
    return human_readable, outputs, raw_response


def get_file_downloads(client, data_args):
    data_args = {key: val for key, val in data_args.items() if val is not None}
    raw_response = client.do_request('GET', '/plugin/products/trace/filedownloads/', params=data_args)

    files = []
    for item in raw_response:
        file = client.get_file_download_item(item)
        files.append(file)

    context = createContext(files, removeNull=True)
    outputs = {'Tanium.FileDownload(val.ID && val.ID === obj.ID)': context}
    human_readable = tableToMarkdown('File downloads', files)
    return human_readable, outputs, raw_response


def get_downloaded_file(client, data_args):
    file_id = data_args.get('file-id')
    file_content, content_desc = client.do_request('GET', f'/plugin/products/trace/filedownloads/{file_id}', resp_type='text')

    filename = re.findall(r"filename\*=UTF-8\'\'(.+)", content_desc)[0]

    demisto.results(fileResult(filename, file_content))


def filter_to_tanium_api_syntax(filter_str):
    filter_dict = {}
    try:
        if filter_str:
            filter_expressions = ast.literal_eval(filter_str)
            for i, expression in enumerate(filter_expressions):
                filter_dict['f' + str(i)] = expression[0]
                filter_dict['o' + str(i)] = expression[1]
                filter_dict['v' + str(i)] = expression[2]
        return filter_dict
    except IndexError:
        raise ValueError('Invalid filter argument.')


def get_events_by_connection(client, data_args):
    limit = int(data_args.get('limit'))
    offset = data_args.get('offset')
    connection = data_args.get('connection-name')
    sort = data_args.get('sort')
    fields = data_args.get('fields')
    event_type = data_args.get('event-type').lower()
    filter_dict = filter_to_tanium_api_syntax(data_args.get('filter'))
    match = data_args.get('match')

    g1 = ','.join([str(i) for i in range(len(filter_dict)//3)])  # A weird param that must be passed

    params = {
        'limit': limit,
        'offset': offset,
        'sort': sort,
        'fields': fields,
        'gm1': match,
        'g1': g1
    }
    params.update(filter_dict)

    raw_response = client.do_request('GET', f'/plugin/products/trace/conns/{connection}/{event_type}/events/',
                                     params=params)

    events = []
    for item in raw_response:
        event = client.get_event_item(item, event_type)
        events.append(event)

    context = createContext(events, removeNull=True)
    outputs = {'Tanium.Event(val.ID && val.ID === obj.ID)': context}
    human_readable = tableToMarkdown(f'Events for {connection}', events)
    return human_readable, outputs, raw_response


def get_file_download_info(client, data_args):
    if not data_args.get('path') and not data_args.get('id'):
        raise ValueError('At least one of the arguments `path` or `id` must be set.')

    data_args = {key: val for key, val in data_args.items() if val is not None}

    raw_response = client.do_request('GET', f'/plugin/products/trace/filedownloads/', params=data_args)
    if not raw_response:
        raise ValueError('File download does not exist.')

    file = client.get_file_download_item(raw_response[0])
    context = createContext(file, removeNull=True)
    outputs = {'Tanium.FileDownload(val.ID && val.ID === obj.ID)': context}
    human_readable = tableToMarkdown(f'File download metadata for file `{file["Path"]}`', file)
    return human_readable, outputs, raw_response


def get_process_info(client, data_args):
    conn_name = data_args.get('connection-name')
    ptid = data_args.get('ptid')
    raw_response = client.do_request('GET', f'/plugin/products/trace/conns/{conn_name}/processes/{ptid}')
    process = client.get_process_item(raw_response)

    context = createContext(process, removeNull=True)
    outputs = {'Tanium.Process(val.ProcessID && val.ProcessID === obj.ProcessID)': context}
    human_readable = tableToMarkdown(f'{PROCESS_TEXT} {ptid}', process)
    return human_readable, outputs, raw_response


def get_events_by_process(client, data_args):
    limit = int(data_args.get('limit'))
    conn_name = data_args.get('connection-name')
    ptid = data_args.get('ptid')
    raw_response = client.do_request('GET', f'/plugin/products/trace/conns/{conn_name}/processevents/{ptid}',
                                     params={'limit': limit})

    events = []
    for item in raw_response:
        event = client.get_process_event_item(item)
        events.append(event)

    context = createContext(events, removeNull=True)
    outputs = {'Tanium.ProcessEvent(val.ID && val.ID === obj.ID)': context}
    human_readable = tableToMarkdown(f'Events for process {ptid}', events)
    return human_readable, outputs, raw_response


def get_process_children(client, data_args):
    conn_name = data_args.get('connection-name')
    ptid = data_args.get('ptid')
    raw_response = client.do_request('GET', f'/plugin/products/trace/conns/{conn_name}/processtrees/{ptid}/children')

    children = []
    children_human_readable = []
    for item in raw_response:
        child, readable_output = client.get_process_tree_item(item, 1)
        children.append(child)
        children_human_readable.append(readable_output)

    context = createContext(children, removeNull=True)
    outputs = {'Tanium.ProcessChildren(val.ID && val.ID === obj.ID)': context}
    human_readable = tableToMarkdown(f'{PROCESS_CHILDREN_TEXT} {ptid}', children_human_readable)
    return human_readable, outputs, raw_response


def get_parent_process(client, data_args):
    conn_name = data_args.get('connection-name')
    ptid = data_args.get('ptid')
    raw_response = client.do_request('GET', f'/plugin/products/trace/conns/{conn_name}/parentprocesses/{ptid}')
    process = client.get_process_item(raw_response)

    context = createContext(process, removeNull=True)
    outputs = {'Tanium.ParentProcess(val.ProcessID && val.ProcessID === obj.ProcessID)': context}
    human_readable = tableToMarkdown(f'{PROCESS_TEXT} {ptid}', process)
    return human_readable, outputs, raw_response


def get_parent_process_tree(client, data_args):
    conn_name = data_args.get('connection-name')
    ptid = data_args.get('ptid')
    raw_response = client.do_request('GET', f'/plugin/products/trace/conns/{conn_name}/parentprocesstrees/{ptid}')

    if not raw_response:
        raise ValueError('Failed to parse tanium-tr-get-parent-process-tree response.')

    tree, readable_output = client.get_process_tree_item(raw_response[0], 0)

    children_item = readable_output.get('Children')

    if children_item:
        process_tree = readable_output.copy()
        del process_tree['Children']
        human_readable = tableToMarkdown(f'{PARENT_PROCESS_TEXT} {ptid}', process_tree)
        human_readable += tableToMarkdown(f'Processes with the same parent', children_item)
    else:
        human_readable = tableToMarkdown(f'{PARENT_PROCESS_TEXT} {ptid}', readable_output)

    context = createContext(tree, removeNull=True)
    outputs = {'Tanium.ParentProcessTree(val.ID && val.ID === obj.ID)': context}

    return human_readable, outputs, raw_response


def get_process_tree(client, data_args):
    conn_name = data_args.get('connection-name')
    ptid = data_args.get('ptid')
    raw_response = client.do_request('GET', f'/plugin/products/trace/conns/{conn_name}/processtrees/{ptid}')

    if not raw_response:
        raise ValueError('Failed to parse tanium-tr-get-process-tree response.')

    tree, readable_output = client.get_process_tree_item(raw_response[0], 0)

    children_item = readable_output.get('Children')

    if children_item:
        process_tree = readable_output.copy()
        del process_tree['Children']
        human_readable = tableToMarkdown(f'Process information for process with PTID {ptid}', process_tree)
        human_readable += tableToMarkdown(f'{PROCESS_CHILDREN_TEXT} {ptid}', children_item)
    else:
        human_readable = tableToMarkdown(f'{PROCESS_TEXT} {ptid}', readable_output)

    context = createContext(tree, removeNull=True)
    outputs = {'Tanium.ProcessTree(val.ID && val.ID === obj.ID)': context}

    return human_readable, outputs, raw_response


def list_evidence(client, data_args):
    limit = int(data_args.get('limit'))
    offset = int(data_args.get('offset'))
    sort = data_args.get('sort')
    params = {
        'sort': sort,
        'limit': limit,
        'offset': offset
    }
    raw_response = client.do_request('GET', '/plugin/products/trace/evidence', params=params)

    evidences = []
    for item in raw_response:
        pass
        evidence = client.get_evidence_item(item)
        evidences.append(evidence)

    context = createContext(evidences, removeNull=True)
    outputs = {'Tanium.Evidence(val.ID && val.ID === obj.ID)': context}
    human_readable = tableToMarkdown('Evidences', evidences)
    return human_readable, outputs, raw_response


def get_evidence(client, data_args):
    evidence_id = data_args.get('evidence-id')
    raw_response = client.do_request('GET', f'/plugin/products/trace/evidence/{evidence_id}')
    evidence = client.get_evidence_item(raw_response)

    context = createContext(evidence, removeNull=True)
    outputs = {'Tanium.Evidence(val.ID && val.ID === obj.ID)': context}
    human_readable = tableToMarkdown('Label information', evidence)
    return human_readable, outputs, raw_response


def create_evidence(client, data_args):
    conn_name = data_args.get('connection-name')
    host = data_args.get('host')
    ptid = data_args.get('ptid')

    params = {'match': 'all', 'f1': 'process_table_id', 'o1': 'eq', 'v1': ptid}
    process_data = client.do_request('GET', f'/plugin/products/trace/conns/{conn_name}/process/events', params=params)

    if not process_data:
        raise ValueError('Invalid connection-name or ptid.')

    data = {
        'host': host,
        'user': client.username,
        'data': process_data[0],
        'connId': conn_name,
        'type': 'ProcessEvent',
        'sTimestamp': process_data[0].get('create_time'),
        'sId': ptid
    }

    client.do_request('POST', '/plugin/products/trace/evidence', data=data, resp_type='content')
    return "Evidence have been created.", {}, {}


def delete_evidence(client, data_args):
    evidence_id = data_args.get('evidence-id')
    client.do_request('DELETE', f'/plugin/products/trace/evidence/{evidence_id}', resp_type='content')
    return f"Evidence {evidence_id} has been deleted successfully.", {}, {}


def request_file_download(client, data_args):
    con_id = data_args.get('connection-id')
    path = data_args.get('path')

    # context object will help us to verify the request has succeed in the download file playbook.
    context = {
        'Host': con_id,
        'Path': path,
        'Downloaded': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S.%f')
    }
    outputs = {'Tanium.FileDownload(val.Path === obj.Path && val.Host === obj.Host)': context}

    data = {
        'path': path,
        'connId': con_id
    }
    client.do_request('POST', f'/plugin/products/trace/filedownloads', data=data, resp_type='text')
    filename = os.path.basename(path)
    return f"Download request of file {filename} has been sent successfully.", outputs, {}


def get_file_download_request_status(client, data_args):
    downloaded = data_args.get('request-date')
    host = data_args.get('host')
    path = data_args.get('path')
    params = {'downloaded>': downloaded}
    if host:
        params['host'] = host
    if path:
        params['path'] = path

    raw_response = client.do_request('GET', f'/plugin/products/trace/filedownloads', params=params)
    if raw_response:
        file_id = raw_response[0].get('id')
        status = 'Completed'
        downloaded = raw_response[0].get('downloaded')
    else:
        file_id = None
        status = 'Not found'

    file_download_request = {
        'ID': file_id,
        'Host': host,
        'Path': path,
        'Status': status,
        'Downloaded': downloaded
    }

    context = createContext(file_download_request, removeNull=True)
    outputs = {'Tanium.FileDownload(val.Path === obj.Path && val.Host === obj.Host)': context}
    human_readable = tableToMarkdown('File download request status', file_download_request)
    return human_readable, outputs, raw_response


def delete_file_download(client, data_args):
    file_id = data_args.get('file-id')
    client.do_request('DELETE', f'/plugin/products/trace/filedownloads/{file_id}', resp_type='text')
    return f"Delete request of file with ID {file_id} has been sent successfully.", {}, {}


def list_files_in_dir(client, data_args):
    con_id = data_args.get('connection-id')
    dir_path = urllib.parse.quote(data_args.get('path'))
    limit = int(data_args.get('limit'))
    offset = int(data_args.get('offset'))

    raw_response = client.do_request('GET', f'/plugin/products/trace/filedownloads/{con_id}/list/{dir_path}')

    files = []
    for file in raw_response[offset:offset + limit]:
        files.append(client.get_file_item(file))

    context = createContext(files, removeNull=True)
    outputs = {'Tanium.File(val.ID && val.ID === obj.ID)': context}
    human_readable = tableToMarkdown(f'Files in directory `{dir_path}`', files)
    return human_readable, outputs, raw_response


def get_file_info(client, data_args):
    con_id = data_args.get('connection-id')
    path = data_args.get('path')

    raw_response = client.do_request('GET', f'/plugin/products/trace/conns/{con_id}/fileinfo/{path}')
    fileinfo = client.get_file_item(raw_response)

    context = createContext(fileinfo, removeNull=True)
    outputs = {'Tanium.File(val.ID && val.ID === obj.ID)': context}
    human_readable = tableToMarkdown(f'Information for file `{path}`', fileinfo)
    return human_readable, outputs, raw_response


def delete_file_from_endpoint(client, data_args):
    con_id = data_args.get('connection-id')
    path = urllib.parse.quote(data_args.get('path'))
    client.do_request('DELETE', f'/plugin/products/trace/filedownloads/{con_id}/{path}', resp_type='text')
    return f"Delete request of file {path} from endpoint {con_id} has been sent successfully.", {}, {}


def get_process_timeline(client, data_args):
    con_id = data_args.get('connection-id')
    ptid = data_args.get('ptid')
    category = data_args.get('category')
    limit = int(data_args.get('limit'))
    offset = int(data_args.get('offset'))

    raw_response = client.do_request('GET', f'/plugin/products/trace/conns/{con_id}/eprocesstimelines/{ptid}')
    timeline = client.get_process_timeline_item(raw_response, category, limit, offset)

    context = createContext(timeline, removeNull=True)
    outputs = {'Tanium.ProcessTimeline(val.ProcessTableID && val.ProcessTableID === obj.ProcessTableID)': context}
    human_readable = tableToMarkdown(f'Timeline data for process with PTID `{ptid}`', timeline)
    return human_readable, outputs, raw_response


def fetch_incidents(client):
    """
    Fetch events from this integration and return them as Demisto incidents

    returns:
        Demisto incidents
    """
    # demisto.getLastRun() will returns an obj with the previous run in it.
    last_run = demisto.getLastRun()
    # Get the last fetch time and data if it exists
    last_fetch = last_run.get('time')

    # Handle first time fetch, fetch incidents retroactively
    if not last_fetch:
        last_fetch, _ = parse_date_range(FETCH_TIME, date_format=DATE_FORMAT)

    last_fetch = datetime.strptime(last_fetch, DATE_FORMAT)
    current_fetch = last_fetch
    raw_response = client.do_request('GET', '/plugin/products/detect3/api/v1/alerts')

    # convert the data/events to demisto incidents
    incidents = []
    for alarm in raw_response:
        incident = client.alarm_to_incident(alarm)
        temp_date = datetime.strptime(incident.get('occurred'), DATE_FORMAT)

        # update last run
        if temp_date > last_fetch:
            last_fetch = temp_date + timedelta(seconds=1)

        # avoid duplication due to weak time query
        if temp_date > current_fetch:
            incidents.append(incident)

    demisto.setLastRun({'time': datetime.strftime(last_fetch, DATE_FORMAT)})
    return demisto.incidents(incidents)


''' COMMANDS MANAGER / SWITCH PANEL '''


def main():
    params = demisto.params()
    username = params.get('credentials').get('identifier')
    password = params.get('credentials').get('password')

    # Remove trailing slash to prevent wrong URL path to service
    server = params['url'].strip('/')
    # Should we use SSL
    use_ssl = not params.get('insecure', False)

    # Remove proxy if not set to true in params
    handle_proxy()
    command = demisto.command()
    client = Client(server, username, password, verify=use_ssl)
    demisto.info(f'Command being called is {command}')

    commands = {
        f'test-module': test_module,
        f'tanium-tr-get-intel-doc-by-id': get_intel_doc,
        f'tanium-tr-list-intel-docs': get_intel_docs,
        f'tanium-tr-list-alerts': get_alerts,
        f'tanium-tr-get-alert-by-id': get_alert,
        f'tanium-tr-alert-update-state': alert_update_state,
        f'tanium-tr-list-snapshots': get_snapshots,
        f'tanium-tr-create-snapshot': create_snapshot,
        f'tanium-tr-delete-snapshot': delete_snapshot,
        f'tanium-tr-list-local-snapshots': get_local_snapshots,
        f'tanium-tr-delete-local-snapshot': delete_local_snapshot,
        f'tanium-tr-list-connections': get_connections,
        f'tanium-tr-get-connection-by-name': get_connection,
        f'tanium-tr-create-connection': create_connection,
        f'tanium-tr-delete-connection': delete_connection,
        f'tanium-tr-list-labels': get_labels,
        f'tanium-tr-get-label-by-id': get_label,
        f'tanium-tr-list-events-by-connection': get_events_by_connection,
        f'tanium-tr-get-process-info': get_process_info,
        f'tanium-tr-get-events-by-process': get_events_by_process,
        f'tanium-tr-get-process-children': get_process_children,
        f'tanium-tr-get-parent-process': get_parent_process,
        f'tanium-tr-get-parent-process-tree': get_parent_process_tree,
        f'tanium-tr-get-process-tree': get_process_tree,
        f'tanium-tr-list-evidence': list_evidence,
        f'tanium-tr-get-evidence-by-id': get_evidence,
        f'tanium-tr-create-evidence': create_evidence,
        f'tanium-tr-delete-evidence': delete_evidence,
        f'tanium-tr-list-file-downloads': get_file_downloads,
        f'tanium-tr-get-file-download-info': get_file_download_info,
        f'tanium-tr-request-file-download': request_file_download,
        f'tanium-tr-get-download-file-request-status': get_file_download_request_status,
        f'tanium-tr-delete-file-download': delete_file_download,
        f'tanium-tr-list-files-in-directory': list_files_in_dir,
        f'tanium-tr-get-file-info': get_file_info,
        f'tanium-tr-delete-file-from-endpoint': delete_file_from_endpoint,
        f'tanium-tr-get-process-timeline': get_process_timeline
    }

    try:
        if command == 'fetch-incidents':
            return fetch_incidents(client)
        if command == 'tanium-tr-get-downloaded-file':
            return get_downloaded_file(client, demisto.args())

        if command in commands:
            human_readable, outputs, raw_response = commands[command](client, demisto.args())
            return_outputs(readable_output=human_readable, outputs=outputs, raw_response=raw_response)
        # Log exceptions
    except Exception as e:
        import traceback
        if command == 'fetch-incidents':
            LOG(traceback.format_exc())
            LOG.print_log()
            raise

        else:
            return_error('Error in Tanium v2 Integration: {}'.format(str(e)), traceback.format_exc())


if __name__ in ('__builtin__', 'builtins', '__main__'):
    main()