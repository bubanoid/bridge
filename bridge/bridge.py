from gevent import monkey
monkey.patch_all()

import os.path
import gevent
import gevent.queue
import couchdb
from argparse import ArgumentParser
from ConfigParser import ConfigParser
from logging import getLogger
from logging.config import fileConfig
from sync import Sync
from utils import create_db_url, threaded


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
        self.to_get_queue = gevent.queue.Queue()
        self.to_put_queue = gevent.queue.Queue()
        db_url = create_db_url(
            config.get('user', 'username'),
            config.get('user', 'password'),
            config.get('db', 'host'),
            config.get('db', 'port'),
        )
        print db_url
        self.get_db(db_url, config.get('db', 'name'))

    def get_db(self, url, name):
        server = couchdb.Server(url)
        if name not in server:
            self.db = server.create(name)
        else:
            self.db = server[name]

    @threaded
    def save_docs(self):
        while True:
            tender = self.to_put_queue.get()
            if not tender:
                continue
            if tender.id not in self.db:
                self.db[tender.id] = tender.data
            else:
                doc = self.db.get(tender.id)
                doc = tender
                self.db.save(doc)

    @threaded
    def get_tender(self):
        while True:
            tenders_list = self.to_get_queue.get()
            if not tenders_list:
                continue
            for tender in tenders_list:
                if tender['id'] not in self.db:
                    self.client.get_tender(
                        tender.id, self.to_put_queue
                    )
                else:
                    doc = self.db.get(tender['id'])
                    if tender['dateModified'] > doc['dateModified']:
                        self.client.get_tender(
                            tender.id, self.to_put_queue
                        )

    def run(self):
        try:
            jobs = [self.client.get_tenders_forward(self.to_get_queue),
                    self.client.get_tenders_backward(self.to_get_queue),
                    self.get_tender(), self.save_docs()]
            gevent.joinall(jobs)
        except KeyboardInterrupt:
            gevent.killall(jobs)


def run():
    bridge = Bridge()
    bridge.run()
