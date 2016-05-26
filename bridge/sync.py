from gevent import monkey
monkey.patch_all()

from restkit.errors import RequestFailed, RequestError
from retrying import retry
from openprocurement_client.client import APIBaseClient
from utils import threaded
from logging import getLogger
from simplejson import loads


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
        self.Logger = getLogger(__name__)

    @retry(stop_max_attempt_number=5)
    def get_tenders(self, params):
        if not params:
            raise ValueError
        try:
            resp = self.get(self.prefix_path, params_dict=params).body_string()
            tender_list = loads(resp)
            return tender_list['data'], tender_list['next_page']
        except RequestFailed, e:
            self.Logger.info("Request falied with error {}".format(e))
        except RequestError, e:
            self.Logger.info(
                "Error {}  with request params {}".format(e, params)
            )
        except Exception, e:
            self.Logger.info("Error while loading feeds {}".format(e))

    @threaded
    def get_tenders_forward(self, queue, initial_params=None):
        params = initial_params or {'feed': 'changes'}
        while True:
            tenders_feed, next_page = self.get_tenders(params)
            if not tenders_feed:
                self.forward_done = True
                break
            self.Logger.info('Got feed page. Client params {}'.format(params))
            params.update(next_page)
            queue.put(tenders_feed)

    @threaded
    def get_tenders_backward(self, queue, initial_params=None):
        params = initial_params or {'feed': 'changes', 'descending': '1'}
        while True:
            tenders_feed, next_page = self.get_tenders(params)
            if not tenders_feed:
                self.backward_done = True
                break
            self.Logger.info('Got feed page. Client params {}'.format(params))
            params.update(next_page)
            queue.put(tenders_feed)

    def get_tender(self, id, queue):
        queue.put(self._get_resource_item(
            '{}/{}'.format(self.prefix_path, id)
        ))
