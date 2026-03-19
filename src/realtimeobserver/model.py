from sqlobject import *

class MonitoredTrip(SQLObject):
    operation_day = StringCol()
    trip_id = StringCol()
    line_id = StringCol()
    line_name = StringCol()
    origin_stop_id = StringCol()
    origin_name = StringCol()
    destination_stop_id = StringCol()
    destination_name = StringCol()
    start_time = StringCol()
    end_time = StringCol()
    realtime_ref_station = StringCol()
    realtime_first_appeared = StringCol(default=None)
    realtime_cancelled = IntCol(default=0)
    realtime_num_cancelled_stops = IntCol(default=0)
    realtime_num_added_stops = IntCol(default=0)