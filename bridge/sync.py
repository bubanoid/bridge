from gevent import monkey
monkey.patch_all()

from retrying import retry
from openprocurement_client.client import APIBaseClient
from utils import threaded


class Sync(APIBaseClient):

    def __init__(self, config):
        super(Sync, self).__init__(
            config.get('api', 'key'),
            config.get('api', 'host'),
            config.get('api', 'version'),
            'tenders',
            {}
        )
        self.forward_done = False
        self.backward_done = False

    @retry(stop_max_attempt_number=5)
    def get_tenders(self, params):
        if not params:
            raise ValueError
        try:
            resp = self.get(self.prefix_path, params_dict=params)
            return resp['data'], resp['next_page']
        except Exception, e:
            print e

    @threaded
    def get_tenders_forward(self, queue):
        params = {'feed': 'changes'}
        while True:
            tenders_feed, next_page = self.get_tenders(params)
            if not tenders_feed:
                self.forward_done = True
                break
            params.update(next_page)
            queue.put(tenders_feed)

    @threaded
    def get_tenders_backward(self, queue):
        params = {'feed': 'changes', 'descending': '1'}
        while True:
            tenders_feed, next_page = self.get_tenders(params)
            if not tenders_feed:
                self.backward_done = True
                break
            params.update(next_page)
            queue.put(tenders_feed)

    def get_tender(self, id, queue):
        queue.put(self._get_resource_item(
            '{}/{}'.format(self.prefix_path, id)
        ))
