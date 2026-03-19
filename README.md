# realtimeobserver
Python client for monitoring and logging of realtime data in passenger information systems using public data interfaces. 

## Purpose & Usage
`realtimeobserver` is a simple tool to monitor departures and the availability of realtime data. Each trip detected is logged to a SQLite database which can be used for analyzing problems and behind the generation of realtime data. Following questions can be answered using those data:

- Which lines have a good or less realtime coverage?
- Are there some trips which have no realtime data available for several days?
- How is the realtime coverage over some lines in the past 5 days?
- Are there cancelled trips or single cancelled or added stops?

To collect the data, the `realtimeobserver` client performs StopEventRequests periodically for each configured station ID and adds an entry for each unique trip per operation day. 

Everythin results in a table with the following structure:

| Column                  | Type   | Description                | Comment
|-------------------------|------------|------------------------------|---|
| id                      | INTEGER    | Primary Key, AutoID     |    |
| operation_day           | TEXT       | Operation Day (YYYY-MM-DD)  ||
| trip_id                 | TEXT       | Trip-ID                     ||
| line_id                 | TEXT       | Line-ID                     ||
| line_name               | TEXT       | Line Name                   ||
| origin_stop_id          | TEXT       | Start Station ID            ||
| origin_name             | TEXT       | Start Station Name          ||
| destination_stop_id     | TEXT       | Destination Station ID      ||
| destination_name        | TEXT       | Destination Station Name    ||
| start_time              | TEXT       | Nominal Start Time (ISO8601) ||
| end_time                | TEXT       | Nominal End Timestamp (ISO8601) ||
| realtime_ref_station    | TEXT       | Reference Station ID | station ID where the trip has been seen the first time |
| realtime_first_appeared | TEXT       | First Realtime Timestamp (ISO8601) |timestamp when the trip had realtime information the first time | 
| realtime_cancelled | INTEGER | Realtime Cancellation Flag | indicates whether the complete trip was cancelled for at least one time |
| realtime_num_cancelled_stops | INTEGER | Realtime No. Cancelled Stops | number of stops in this trip which are cancelled |
| realtime_num_added_stops | INTEGER | Realtime No. Added Stops | number of stops in this trip which are added |

### Installation
There're different options to use realtimeobserver. You can use it by cloning this repository and install it into your virtual environment directly:
```
git clone https://github.com/sebastianknopf/realtimeobserver.git
cd realtimeobserver

pip install .
```
and run it by using
```
python -m realtimeobserver observe ./data/database.db3 ./config/your-config.yaml
```
This is especially good for development. 

If you simply want to run `realtimeobserver` on your server, you also can use docker:
```
docker run 
    --rm 
    -v ./host/config.yaml:/app/config/config.yaml 
    -v ./host/database.db3:/app/data/data.db3
    sebastianknopf/realtimeobserver:latest
```
Please note, that you're required to mount a configuration file with your specific configuration and a SQLite database file into the docker container to make the application running. 

## Configuration
There's a YAML file for configuring the requested interface endpoint, an optional access token and the URL to a static GTFS feed for obtaining the stations, which need to be queried. See [config/default.yaml](config/default.yaml) for reference.

As `realtimeobserver` performs periodic requests for departure tables to load realtime data of all available trips, the number of stations should be as small as possible to avoid unneccessary network traffic. To achieve this, `realtimeobserver` loads a GTFS static feed to obtain all planned trips and find a minimum set of required to stations to meet each planned trip at least one time.

## Available Interfaces
Currently, different interfaces are implemented to observe the realtime data presence. See following list:

- `efajson` (adapter name: `efajson`) Using the EFA JSON API provided by several passenger information platforms powered by EFA (Mentz)
- `vdv431` (adapter name: `vdv431`) Using the VDV431 interface for supplyer-independent data monitoring

## License
This project is licensed under the Apache License. See [LICENSE.md](LICENSE.md) for more information.
