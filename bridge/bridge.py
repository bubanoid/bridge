from gevent import monkey
monkey.patch_all()

import sys
import os.path
import gevent
import gevent.queue
import couchdb
import couchdb.http
from time import sleep
from argparse import ArgumentParser
from ConfigParser import ConfigParser
from logging import getLogger
from logging.config import fileConfig
from sync import Sync
from datetime import datetime
from utils import create_db_url, threaded
from restkit.errors import RequestFailed, RequestError


class Bridge(object):

    def __init__(self):
        parser = ArgumentParser()
        parser.add_argument('-c')
        args = parser.parse_args()
        if not os.path.exists(args.c):
            raise Exception('Error while reading config')

        config = ConfigParser()
        config.read(args.c)
        fileConfig(args.c)
        self.Logger = getLogger(__name__)
        self.client = Sync(config)
        self.to_get_queue = gevent.queue.Queue(maxsize=500)
        self.to_put_queue = gevent.queue.Queue(maxsize=500)
        db_url = create_db_url(
            config.get('user', 'username'),
            config.get('user', 'password'),
            config.get('db', 'host'),
            config.get('db', 'port'),
        )
        self.get_db(db_url, config.get('db', 'name'))

    def get_db(self, url, name):
        try:
            server = couchdb.Server(url)
            if name not in server:
                self.db = server.create(name)
            else:
                self.db = server[name]
            self.Logger.info('Connected to db {} on {}'.format(name, url))
        except couchdb.http.Unauthorized:
            print "Can't authenticate user in config. Exiting.."
            sys.exit(2)

    @threaded
    def save_docs(self):
        while True:
            if self.to_put_queue.empty():
                sleep(1)
                continue
            for tender in self.to_put_queue:
                if tender.data.id not in self.db:
                    self.db[tender.data.id] = tender.data
                    self.Logger.info('Saving tender id={}'.format(tender.data.id))
                else:
                    doc = self.db.get(tender.data.id)
                    doc = tender.data
                    self.db.save(doc)
                    self.Logger.info('Update tender id={}'.format(tender.data.id))

    @threaded
    def get_tender(self):
        while True:
            if self.to_get_queue.empty():
                sleep(1)
                continue
            for tenders_list in self.to_get_queue:
                for tender in tenders_list:
                    if tender['id'] not in self.db:
                        self.Logger.info(
                            'Tender id={} not in database'.format(tender['id'])
                        )
                        try:
                            self.client.get_tender(
                                tender['id'], self.to_put_queue
                            )
                            self.Logger.info(
                                'Successfully got tender'
                                ' id={}'.format(tender['id'])
                            )
                        except RequestFailed, e:
                            self.Logger.info(
                                "Request falied while getting tender id={} "
                                "with error {}".format(tender['id'], e))
                        except RequestError, e:
                            self.Logger.info(
                                "RequestError {} while getting tender "
                                "id={}".format(e, tender['id'])
                            )
                        except Exception, e:
                            self.Logger.info(
                                "Error while loading feeds {}".format(e)
                            )

                    else:
                        doc = self.db.get(tender['id'])
                        if tender['dateModified'] > doc['dateModified']:
                            self.client.get_tender(
                                tender['id'], self.to_put_queue
                            )
            self.to_put_queue.put(StopIteration)

    def run(self):
        try:
            self.Logger.info('Start working at {}'.format(datetime.now()))
            jobs = [self.client.get_tenders_forward(self.to_get_queue),
                    self.client.get_tenders_backward(self.to_get_queue),
                    self.get_tender(), self.save_docs()]
            gevent.joinall(jobs)
            self.Logger.info('Finish work at {}'.format(datetime.now()))
        except KeyboardInterrupt:
            gevent.killall(jobs)


def run():
    bridge = Bridge()
    bridge.run()
