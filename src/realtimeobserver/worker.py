import datetime

from datetime import datetime

from realtimeobserver.adapter.base import BaseAdapter
from realtimeobserver.model import MonitoredTrip

class MonitorWorker:

    def __init__(self, database: str, adapter_config: any) -> None:
        self._database: str = database
        self._adapter_config: any = adapter_config

        self.next_departure_timestamp = None

    def start(self, station_id: str, line_ids: list[str]|None = None) -> None:
        self.next_departure_timestamp = self._run(station_id, line_ids)

    def _run(self, station_id: str, line_ids: list[str]|None = None) -> datetime|None:
        adapter: BaseAdapter = None
        if self._adapter_config.type == 'vdv431':
            #from realtimeobserver.adapter.vdv431.adapter import VDV431Adapter
            #adapter = VDV431Adapter(self._adapter_config['key'], self._adapter_config['endpoint'])
            # VDV431 adapter needs a complete refactoring and must not be used
            # throw an exception for noew
            raise NotImplementedError("VDV431 adapter is not implemented yet")
        elif self._adapter_config.type == 'efajson':
            from realtimeobserver.adapter.efajson.adapter import EfaJsonAdapter
            adapter = EfaJsonAdapter(self._adapter_config.token, self._adapter_config.endpoint)
        else:
            raise ValueError(f"Unsupported adapter type: {self._adapter_config.type}")
        
        stop_events, next_departure_timestamp = adapter.process(station_id, line_ids)

        for stop_event in stop_events:
            operation_day = stop_event['operation_day']
            trip_id = stop_event['trip_id']

            monitored_trip = MonitoredTrip.select((MonitoredTrip.q.operation_day == operation_day) & (MonitoredTrip.q.trip_id == trip_id)).getOne(default=None)
            if monitored_trip is None:
                # create monitored trip object
                MonitoredTrip(
                    operation_day=operation_day,
                    trip_id=trip_id,
                    line_id=stop_event['line_id'],
                    line_name=stop_event['line_name'],
                    origin_stop_id=stop_event['origin_stop_id'],
                    origin_name=stop_event['origin_name'],
                    destination_stop_id=stop_event['destination_stop_id'],
                    destination_name=stop_event['destination_name'],
                    start_time=stop_event['start_time'],
                    end_time=stop_event['end_time'],
                    ref_stop_id=stop_event['ref_stop_id'],
                    ref_stop_name=stop_event['ref_stop_name'],
                    ref_stop_departure_time=stop_event['ref_stop_departure_time'],
                    realtime_first_appeared=stop_event['realtime_first_appeared'],
                    realtime_cancelled=stop_event['realtime_cancelled'],
                    realtime_num_cancelled_stops=stop_event['realtime_num_cancelled_stops'],
                    realtime_num_added_stops=stop_event['realtime_num_added_stops']
                )

            else:
                # only update the trip if there's no realtime available yet
                if monitored_trip.realtime_first_appeared == None:
                    # check realtime existence
                    if stop_event['realtime_monitored']:
                        realtime_first_appeared = datetime.now().isoformat()
                        monitored_trip.realtime_first_appeared = realtime_first_appeared

                # update realtime metrics if there's something special
                realtime_cancelled, realtime_num_cancelled_stops, realtime_num_added_stops = stop_event['realtime_cancelled'], stop_event['realtime_num_cancelled_stops'], stop_event['realtime_num_added_stops']
                
                if realtime_cancelled > monitored_trip.realtime_cancelled \
                    or realtime_num_cancelled_stops > monitored_trip.realtime_num_cancelled_stops \
                    or realtime_num_added_stops > monitored_trip.realtime_num_added_stops:

                    monitored_trip.realtime_cancelled = realtime_cancelled
                    monitored_trip.realtime_num_cancelled_stops = realtime_num_cancelled_stops
                    monitored_trip.realtime_num_added_stops = realtime_num_added_stops
        
        return datetime.fromisoformat(next_departure_timestamp) if next_departure_timestamp is not None else None    
    