from abc import ABC
from lxml.etree import cleanup_namespaces
from lxml.etree import tostring
from lxml.objectify import deannotate
from lxml.objectify import fromstring
from lxml.objectify import Element

class TriasResponse(ABC):

    def __init__(self):
        nsmap = {None: 'http://www.vdv.de/trias', 'siri': 'http://www.siri.org.uk/siri'}
        self.Trias = Element('Trias', nsmap=nsmap, version='1.1')

    def xml(self) -> str:
        deannotate(self.Trias)
        cleanup_namespaces(self.Trias)
        
        return tostring(self.Trias, pretty_print=True, xml_declaration=True, encoding='UTF-8')

class StopEventResponse(TriasResponse):

    def __init__(self):
        super().__init__()


def xml2trias_response(xml: str) -> TriasResponse:
    response = TriasResponse()
    response.Trias = fromstring(xml)

    return response