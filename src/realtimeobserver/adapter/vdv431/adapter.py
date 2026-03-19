import logging
import requests

from datetime import datetime

from realtimeobserver.adapter.base import BaseAdapter
from realtimeobserver.model import MonitoredTrip
from realtimeobserver.adapter.vdv431.request import TriasRequest
from realtimeobserver.adapter.vdv431.request import StopEventRequest
from realtimeobserver.adapter.vdv431.response import TriasResponse
from realtimeobserver.adapter.vdv431.response import xml2trias_response
from realtimeobserver.adapter.vdv431.triasxml import exists as triasxml_exists
from realtimeobserver.adapter.vdv431.triasxml import get_value as triasxml_get_value


class VDV431Adapter(BaseAdapter):
    def process(self, stop_id: str, line_ids: list[str]|None) -> tuple[list[dict], str]:
        # send request
        request = StopEventRequest(self._token, stop_id, self._current_iso_timestamp())
        response = self._request(request)

        # process results
        if triasxml_exists(response, 'Trias.ServiceDelivery.DeliveryPayload.StopEventResponse.StopEventResult'):
            for stop_event_result in response.Trias.ServiceDelivery.DeliveryPayload.StopEventResponse.StopEventResult:
                
                # obtain variables for identification of monitored trip
                operation_day = triasxml_get_value(stop_event_result, 'StopEvent.Service.OperatingDayRef')
                trip_id = triasxml_get_value(stop_event_result, 'StopEvent.Service.JourneyRef')
                line_id = triasxml_get_value(stop_event_result, 'StopEvent.Service.LineRef')

                # apply line name filter if available
                if line_ids is not None and len(line_ids) > 0:
                    if not any([line_id.startswith(id) for id in line_ids]):
                        continue

                # identify monitored trip instance
                monitored_trip = MonitoredTrip.select((MonitoredTrip.q.operation_day == operation_day) & (MonitoredTrip.q.trip_id == trip_id)).getOne(default=None)
                if monitored_trip is None:
                    
                    # gather all data to generate a new monitored trip instance for this operation day
                    line_name = triasxml_get_value(stop_event_result, 'StopEvent.Service.PublishedLineName.Text')
                    origin_stop_id = triasxml_get_value(stop_event_result, 'StopEvent.Service.OriginStopPointRef')
                    origin_stop_name = triasxml_get_value(stop_event_result, 'StopEvent.Service.OriginText.Text')
                    destination_stop_id = triasxml_get_value(stop_event_result, 'StopEvent.Service.DestinationStopPointRef')
                    destination_stop_name = triasxml_get_value(stop_event_result, 'StopEvent.Service.DestinationText.Text')

                    if triasxml_exists(stop_event_result, 'StopEvent.PreviousCall'):
                        first_call = stop_event_result.StopEvent.PreviousCall[0]

                        start_time = triasxml_get_value(first_call, 'CallAtStop.ServiceDeparture.TimetabledTime')
                        start_time = start_time.replace('Z', '+00:00')
                    elif triasxml_exists(stop_event_result, 'StopEvent.ThisCall'):
                        this_call = stop_event_result.StopEvent.ThisCall

                        start_time = triasxml_get_value(this_call, 'CallAtStop.ServiceDeparture.TimetabledTime')
                        start_time = start_time.replace('Z', '+00:00')
                    else:
                        start_time = ""

                    if triasxml_exists(stop_event_result, 'StopEvent.OnwardCall'):
                        last_call = stop_event_result.StopEvent.OnwardCall[-1]

                        end_time = triasxml_get_value(last_call, 'CallAtStop.ServiceArrival.TimetabledTime')
                        end_time = end_time.replace('Z', '+00:00')
                    elif triasxml_exists(stop_event_result, 'StopEvent.ThisCall'):
                        this_call = stop_event_result.StopEvent.ThisCall

                        end_time = triasxml_get_value(this_call, 'CallAtStop.ServiceArrival.TimetabledTime')
                        end_time = end_time.replace('Z', '+00:00')
                    else:
                        end_time = ""

                    # check realtime existence
                    realtime_ref_station = stop_id

                    if triasxml_exists(stop_event_result, 'StopEvent.ThisCall.CallAtStop.ServiceDeparture.EstimatedTime'):
                        realtime_first_appeared = self._current_iso_timestamp()
                    else:
                        realtime_first_appeared = None

                    realtime_cancelled, realtime_num_cancelled_stops, realtime_num_added_stops = self._get_realtime_metrics(stop_event_result)
                    
                    # create monitored trip object
                    MonitoredTrip(
                        operation_day=operation_day,
                        trip_id=trip_id,
                        line_id=line_id,
                        line_name=line_name,
                        origin_stop_id=origin_stop_id,
                        origin_name=origin_stop_name,
                        destination_stop_id=destination_stop_id,
                        destination_name=destination_stop_name,
                        start_time=start_time,
                        end_time=end_time,
                        realtime_ref_station=realtime_ref_station,
                        realtime_first_appeared=realtime_first_appeared,
                        realtime_cancelled=realtime_cancelled,
                        realtime_num_cancelled_stops=realtime_num_cancelled_stops,
                        realtime_num_added_stops=realtime_num_added_stops
                    )
                    
                else:

                    # only update the trip if there's no realtime available yet
                    if monitored_trip.realtime_first_appeared == None:
                        # check realtime existence
                        if triasxml_exists(stop_event_result, 'StopEvent.ThisCall.CallAtStop.ServiceDeparture.EstimatedTime'):
                            realtime_first_appeared = self._current_iso_timestamp()
                            monitored_trip.realtime_first_appeared = realtime_first_appeared

                    # update realtime metrics if there's something special
                    realtime_cancelled, realtime_num_cancelled_stops, realtime_num_added_stops = self._get_realtime_metrics(stop_event_result)
                    if realtime_cancelled > monitored_trip.realtime_cancelled \
                        or realtime_num_cancelled_stops > monitored_trip.realtime_num_cancelled_stops \
                        or realtime_num_added_stops > monitored_trip.realtime_num_added_stops:

                        monitored_trip.realtime_cancelled = realtime_cancelled
                        monitored_trip.realtime_num_cancelled_stops = realtime_num_cancelled_stops
                        monitored_trip.realtime_num_added_stops = realtime_num_added_stops           

            # return first departure time found
            first_stop_event_result = response.Trias.ServiceDelivery.DeliveryPayload.StopEventResponse.StopEventResult[0]
            if triasxml_exists(first_stop_event_result, 'StopEvent.ThisCall'):
                this_call = first_stop_event_result.StopEvent.ThisCall

                if triasxml_exists(this_call, 'CallAtStop.ServiceDeparture'):
                    next_departure_timestamp = triasxml_get_value(this_call, 'CallAtStop.ServiceDeparture.TimetabledTime')
                    next_departure_timestamp = next_departure_timestamp.replace('Z', '+00:00')

                    return datetime.fromisoformat(next_departure_timestamp)
                elif triasxml_exists(this_call, 'CallAtStop.ServiceArrival'):
                    next_departure_timestamp = triasxml_get_value(this_call, 'CallAtStop.ServiceArrival.TimetabledTime')
                    next_departure_timestamp = next_departure_timestamp.replace('Z', '+00:00')

                    return datetime.fromisoformat(next_departure_timestamp)
                else:
                    return None
            else:
                return None
        else:
            return None

    def _get_realtime_metrics(self, stop_event_result: object) -> str:
        realtime_cancelled = 0
        realtime_num_cancelled_stops = 0
        realtime_num_added_stops = 0
        
        if triasxml_exists(stop_event_result, 'StopEvent.Service.Cancelled') and stop_event_result.StopEvent.Service.Cancelled:
            realtime_cancelled = 1
        
        if triasxml_exists(stop_event_result, 'StopEvent.PreviousCall'):
            for call in stop_event_result.StopEvent.PreviousCall:
                if triasxml_exists(call, 'CallAtStop.NotServicedStop') and call.CallAtStop.NotServicedStop:
                    realtime_num_cancelled_stops = realtime_num_cancelled_stops + 1

                if triasxml_exists(call, 'CallAtStop.UnplannedStop') and call.CallAtStop.UnplannedStop:
                    realtime_num_added_stops = realtime_num_added_stops + 1

        if triasxml_exists(stop_event_result, 'StopEvent.ThisCall'):
            if triasxml_exists(stop_event_result.StopEvent.ThisCall, 'CallAtStop.NotServicedStop') and stop_event_result.StopEvent.ThisCall.CallAtStop.NotServicedStop:
                realtime_num_cancelled_stops = realtime_num_cancelled_stops + 1

            if triasxml_exists(stop_event_result.StopEvent.ThisCall, 'CallAtStop.UnplannedStop') and stop_event_result.StopEvent.ThisCall.CallAtStop.UnplannedStop:
                realtime_num_added_stops = realtime_num_added_stops + 1

        if triasxml_exists(stop_event_result, 'StopEvent.OnwardCall'):
            for call in stop_event_result.StopEvent.OnwardCall:
                if triasxml_exists(call, 'CallAtStop.NotServicedStop') and call.CallAtStop.NotServicedStop:
                    realtime_num_cancelled_stops = realtime_num_cancelled_stops + 1

                if triasxml_exists(call, 'CallAtStop.UnplannedStop') and call.CallAtStop.UnplannedStop:
                    realtime_num_added_stops = realtime_num_added_stops + 1

        return (realtime_cancelled, realtime_num_cancelled_stops, realtime_num_added_stops)
    
    def _request(self, request: TriasRequest) -> TriasResponse:
        headers = {
            'Content-Type': 'application/xml',
            'User-Agent': 'ticktrack-worker'
        }
        
        try:            
            response_xml = requests.post(self._endpoint, headers=headers, data=request.xml())
            response = xml2trias_response(response_xml.content)

            return response
        except Exception as ex:
            logging.error(ex)
            return None