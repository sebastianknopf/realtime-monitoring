import click
import logging
import os
import time

from datetime import datetime, timedelta, timezone
from sqlobject import connectionForURI, sqlhub

from realtimeobserver.config import Configuration
from realtimeobserver.setcover import SetCoverCalculator
from realtimeobserver.model import MonitoredTrip
from realtimeobserver.worker import MonitorWorker
from realtimeobserver.version import __version__


logging.basicConfig(
    level=logging.INFO, 
    format= '[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%H:%M:%S'
)

@click.group()
def cli():
    pass

@cli.command()
def version():
    print(__version__)

@cli.command()
@click.argument('database')
@click.argument('config')
def observe(database, config):

    # load config and set default values
    Configuration.apply_config(config)

    # init database tables
    database = os.path.join(os.getcwd(), database)
    sqlhub.processConnection = connectionForURI(f"sqlite:///{database}")

    MonitoredTrip.createTable(ifNotExists=True)

    # create station ID index and next departure index
    station_ids: list[str] = list()
    station_dep_index = dict()

    while True:
        
        # check if station_ids should be updated
        if len(station_ids) == 0:
            logging.info('Updating relevant station IDs ...')
            set_cover_calculator = SetCoverCalculator()
            station_ids = set_cover_calculator.calculate(Configuration.app.gtfs)

            logging.info(f"Found {len(station_ids)} relevant station IDs: {', '.join(station_ids)}")

        # perform observer requests
        logging.info('Performing observer requests ...')
        for station_id in station_ids:

            # check if station preview time is reached
            next_departure_time = station_dep_index.get(station_id, None)
            if next_departure_time is not None and next_departure_time >= datetime.now(timezone.utc) + timedelta(minutes=5):
                logging.info(f"Skipping station {station_id}, preview time window not reached")
                continue
            
            # run worker for this station
            logging.info(f"Running request for station {station_id} ...")
            worker: MonitorWorker = MonitorWorker(
                database,
                Configuration.app.adapter
            )

            if not len(Configuration.app.lines) == 0:
                worker.start(station_id, [str(l).strip() for l in Configuration.app.lines])
            else:
                worker.start(station_id, None)

            # store next departure index
            station_dep_index[station_id] = worker.next_departure_timestamp

        logging.info('All requests done, sleeping for 60 seconds ...')
        time.sleep(60)
    

if __name__ == '__main__':
    cli()