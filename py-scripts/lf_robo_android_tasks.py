"""Shared Android task API client. No SLAM movement commands or token logging."""
import re
from urllib.parse import urlsplit, quote
import requests

TERMINAL = {'completed', 'failed', 'cancelled', 'interrupted'}


class TaskAPIError(Exception):
    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


class AndroidTasks:
    def __init__(self, base_url, token, session=None):
        parsed = urlsplit(base_url)
        if (parsed.scheme not in ('http', 'https') or not parsed.hostname or
                parsed.username or parsed.password or parsed.query or parsed.fragment or
                parsed.path not in ('', '/')):
            raise ValueError('Enter an HTTP(S) address with port, without a path or credentials')
        # Reject malformed port at configuration time.
        parsed.port
        if not re.fullmatch(r'[A-Za-z0-9_-]{8,128}', token or ''):
            raise ValueError('Token must contain 8–128 letters, digits, underscores or hyphens')
        self.base_url = base_url.rstrip('/')
        self.token = token
        self.session = session or requests.Session()

    def request(self, method, path, body=None):
        try:
            response = self.session.request(method, self.base_url + path,
                                            headers={'Authorization': 'Bearer ' + self.token}, json=body,
                                            timeout=(5, 15), allow_redirects=False)
        except requests.RequestException:
            raise TaskAPIError('Robot connection unavailable; outcome may be uncertain') from None
        try:
            result = response.json()
        except ValueError:
            raise TaskAPIError('Robot returned a non-JSON response', response.status_code) from None
        if not 200 <= response.status_code < 300:
            message = result.get('error', 'Robot rejected request') if isinstance(result, dict) else 'Robot rejected request'
            raise TaskAPIError(str(message), response.status_code)
        return result

    def status(self):
        return self.request('GET', '/reeman/status')

    def maps(self):
        return self.request('GET', '/reeman/maps')

    def points(self, alias):
        return self.request('GET', '/reeman/maps/' + quote(str(alias), safe='') + '/points')

    def submit(self, request_id, alias, point):
        return self.request('POST', '/cmd/task', {'requestId': request_id, 'mapAlias': alias, 'point': point})

    def task(self, task_id):
        return self.request('GET', '/cmd/task/' + quote(task_id, safe=''))

    def cancel(self, task_id):
        return self.request('POST', '/cmd/task/' + quote(task_id, safe='') + '/cancel', {})


def lift_display(stage):
    """Never infer physical elevator floor from the target map or elapsed time."""
    if stage in ('switching_map', 'localizing', 'elevator_apply_map', 'elevator_init_pose'):
        return 'Map transition / locating robot'
    if stage == 'elevator_leave_elevator_ack':
        return 'Exiting lift'
    if stage == 'elevator_leave_elevator_complete':
        return 'Lift exit confirmed'
    if stage in ('elevator_enter_elevator_complete', 'elevator_enter_elevator_check_door_state',
                 'elevator_call_elevator_inside', 'elevator_call_elevator_inside_success'):
        return 'Inside lift — destination requested'
    if stage == 'elevator_enter_elevator_ack':
        return 'Entering lift'
    if stage and stage.startswith('elevator_'):
        return stage.removeprefix('elevator_').replace('_', ' ').capitalize()
    return (stage or 'Waiting').replace('_', ' ').capitalize()
