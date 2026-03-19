import datetime

from abc import ABC
from lxml.etree import cleanup_namespaces
from lxml.etree import tostring
from lxml.etree import SubElement
from lxml.objectify import deannotate
from lxml.objectify import fromstring
from lxml.objectify import Element

class TriasRequest(ABC):

    def __init__(self):
        nsmap = {None: 'http://www.vdv.de/trias', 'siri': 'http://www.siri.org.uk/siri'}
        self.Trias = Element('Trias', nsmap=nsmap, version='1.1')

    def xml(self) -> str:
        deannotate(self.Trias)
        cleanup_namespaces(self.Trias)
        
        return tostring(self.Trias, xml_declaration=True, encoding='UTF-8')

class ServiceRequest(TriasRequest):

    def __init__(self, requestor_ref: str) -> None:
        super().__init__()

        self.Trias.ServiceRequest = Element('ServiceRequest')

        #self.Trias.ServiceRequest.RequestTimestamp = 
        siri_request_timestamp = SubElement(self.Trias.ServiceRequest, '{http://www.siri.org.uk/siri}RequestTimestamp')
        siri_request_timestamp._setText(_timestamp())
        #self.Trias.ServiceRequest.RequestTimestamp

        #self.Trias.ServiceRequest.RequestorRef = 
        siri_requestor_ref = SubElement(self.Trias.ServiceRequest, '{http://www.siri.org.uk/siri}RequestorRef')
        siri_requestor_ref._setText(requestor_ref)
        #self.Trias.ServiceRequest.RequestorRef.text = requestor_ref

class StopEventRequest(ServiceRequest):

    def __init__(self, requestor_ref: str, stop_point_ref: str, dep_arr_time: str, num_results: int = 20) -> None:
        super().__init__(requestor_ref)

        self.Trias.ServiceRequest.RequestPayload = Element('RequestPayload')
        self.Trias.ServiceRequest.RequestPayload.StopEventRequest = Element('StopEventRequest')
        self.Trias.ServiceRequest.RequestPayload.StopEventRequest.Location = Element('Location')
        self.Trias.ServiceRequest.RequestPayload.StopEventRequest.Location.LocationRef = Element('LocationRef')
        self.Trias.ServiceRequest.RequestPayload.StopEventRequest.Location.LocationRef.StopPointRef = stop_point_ref
        
        self.Trias.ServiceRequest.RequestPayload.StopEventRequest.DepArrTime = dep_arr_time

        self.Trias.ServiceRequest.RequestPayload.StopEventRequest.Params = Element('Params')
        self.Trias.ServiceRequest.RequestPayload.StopEventRequest.Params.NumberOfResults = str(20)
        self.Trias.ServiceRequest.RequestPayload.StopEventRequest.Params.StopEventType = 'departure'
        self.Trias.ServiceRequest.RequestPayload.StopEventRequest.Params.IncludeRealtimeData = str(True).lower()
        self.Trias.ServiceRequest.RequestPayload.StopEventRequest.Params.IncludePreviousCalls = str(True).lower()
        self.Trias.ServiceRequest.RequestPayload.StopEventRequest.Params.IncludeOnwardCalls = str(True).lower()

def _timestamp(additional_seconds=0) -> str:
    ts = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
    ts = ts + datetime.timedelta(seconds=additional_seconds)

    return ts.isoformat()

def xml2trias_request(xml: str) -> TriasRequest:
    request = TriasRequest()
    request.Trias = fromstring(xml)

    return request