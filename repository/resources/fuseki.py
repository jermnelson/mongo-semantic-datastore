__author__ = "Jeremy Nelson"

import falcon
import json
import rdflib
import re
import requests

PREFIX = """PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>"""

DEDUP_SPARQL = """{}
SELECT ?subject
WHERE {{{{
    ?subject <{{}}> "{{}}"^^xsd:string .
    ?subject rdf:type <{{}}> .
}}}}""".format(PREFIX)

SAME_AS_SPARQL = """{}
SELECT DISTINCT ?subject
WHERE {{{{
  ?subject owl:sameAs {{}} .
}}}}""".format(PREFIX)

UPDATE_TRIPLESTORE_SPARQL = """{}
INSERT DATA {{{{
   {{}}
}}}}""".format(PREFIX)

URL_CHECK_RE = re.compile(
    r'^(?:http|ftp)s?://' # http:// or https://
    r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|' # domain...
    r'localhost|' # localhost...
    r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}|' # ...or ipv4
    r'\[?[A-F0-9]*:[A-F0-9:]+\]?)' # ...or ipv6
    r'(?::\d+)?' # optional port
    r'(?:/?|[/?]\S+)$', re.IGNORECASE)


class TripleStore(object):

    def __init__(self, config):
        url = "http://{}:{}".format(
                config["FUSEKI"]["host"],
                config["FUSEKI"]["port"])
        datastore = config["FUSEKI"]["datastore"]
        self.update_url = "/".join([url, datastore, "update"])
        self.query_url = "/".join([url, datastore, "query"])

    def __match__(self, **kwargs):
        """Internal method attempts to match an existing subject
        in the triple-store based on the subject's type and a 
        string or hash value

	Keyword arguments:
            predicate -- rdflib Predicate
            object -- rdflib Object
            type -- RDF type to restrict query on
        """
        predicate = kwargs.get('predicate')
        object_ = kwargs.get('object')
        type_ = kwargs.get('type')
          
        result = requests.post(
            self.query_url,
            data={"query": DEDUP_SPARQL.format(
                               predicate, 
                               object_, 
                               type_),
                  "output": "json"})
        if result.status_code < 400:
            bindings = result.json().get('results').get('bindings')
            if len(bindings) > 0:
                return bindings[0]['subject']['value']
        else:
            raise falcon.HTTPInternalServerError(
                "Failed to match query in Fuseki",
                "Predicate={} Object={} Type={}\nError:\n{}".format(
                    predicate,
                    object_,
                    type_,
                    result.text))

    def __load__(self, rdf):
        fuseki_result = requests.post(self.update_url,
            data={"update": UPDATE_TRIPLESTORE_SPARQL.format(
                             rdf.serialize(format='nt').decode())})
        if fuseki_result.status_code > 399:
            raise falcon.HTTPInternalServerError(
                "Failed to load RDF into {}".format(self.update_url),
                "Error:\n{}\nRDF:\n{}".format(
                    fuseki_result.text,
                    rdf))

    def __sameAs__(self, url):
        """Internal method takes a url and attempts to retrieve any existing
        subjects with the equivalent owl:sameAs 

        Args:
            url -- Subject URL
        """
        if URL_CHECK_RE.search(url):
            object_str = "<{}>".format(url)
        else: # Test as a string literal
            object_str = """"{}"^^xsd:string""".format(url)        
        result = requests.post(
            self.query_url, 
            data={"query": SAME_AS_SPARQL.format(object_str), 
                  "output": "json"})
        if result.status_code < 400:
            result_json = result.json()
            if len(result_json.get('results').get('bindings')) > 0:
                return result_json['results']['bindings'][0]['subject']['value']
        else:
             raise falcon.HTTPInternalServerError(
                "Failed to run sameAs query in Fuseki",
                "URL={}\nError {}:\n{}".format(url, result.status_code, result.text))
       

    def on_put(self, req, resp):
        rdf = req.get_param('rdf') or None
        if rdf:
            self.__load__(self. rdf)
            msg = "Successfully loaded RDF into Fuseki"
        else:
            msg = "No RDF to load into Fuseki"
        resp.status = falcon.HTTP_200
        resp.body = json.dumps({"message": msg})

