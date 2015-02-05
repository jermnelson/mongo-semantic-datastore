__author__ = "Jeremy Nelson"

import os
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
with open(os.path.join(BASE_DIR, "VERSION")) as version:
    __version__ = version.read().strip()

import configparser
import falcon

from elasticsearch import Elasticsearch


from repository import Info, Search
from repository.resources.fedora import Resource, Transaction
from repository.resources.fedora3 import FedoraObject
from repository.utilities.migrating.foxml import FoxmlContentHandler

config = configparser.ConfigParser()
config.read(os.path.join(BASE_DIR, 'server.cfg'))
if len(config) == 1: # Empty or nonexistent configuration, loads default
    config.read(os.path.join(BASE_DIR,'default.cfg'))

from werkzeug.serving import run_simple
api = application = falcon.API()

api.add_route("/info", Info(config))
api.add_route("/search",
    Search(config))
api.add_route("/Resource/{id}", Resource(config))
api.add_route("/Transaction", Transaction(config))

if 'FEDORA3' in config:
    api.add_route("/migrate/foxml", FoxmlContentHandler(config))
    api.add_route("/Object/{pid}", FedoraObject(config))

def main():
    run_simple(
        config.get('DEFAULT', 'host'),
        config.getint('DEFAULT', 'port'),
        application,
        use_reloader=True)


if __name__ == '__main__':
    main()

