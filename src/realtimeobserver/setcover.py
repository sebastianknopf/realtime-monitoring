import csv
import os
import re
import shutil
import tempfile
import zipfile

from collections import defaultdict
from datetime import datetime

import requests

from realtimeobserver.config import Configuration


class SetCoverCalculator:
    
    def calculate(self, gtfs_feed_url: str) -> list[str]:
        with tempfile.TemporaryDirectory() as temp_dir:
            archive_path = self._download_feed(gtfs_feed_url, temp_dir)
            extract_dir = self._extract_feed(archive_path, temp_dir)

            valid_service_ids = self._load_valid_service_ids(extract_dir)
            route_ids = self._load_route_ids(extract_dir, self._get_configured_lines())
            valid_trip_ids = self._load_trip_ids_for_service_ids(extract_dir, valid_service_ids, route_ids)
            trips_per_stop = self._load_trips_per_stop(extract_dir, valid_trip_ids)

            minimal_stop_set = self._find_minimal_stop_set(trips_per_stop)
            return sorted(minimal_stop_set)

    def _get_configured_lines(self) -> list[str]:
        app_config = getattr(Configuration, 'app', None)
        if app_config is None:
            return []

        lines = getattr(app_config, 'lines', None)
        if lines is None:
            return []

        return list(lines)

    def _download_feed(self, gtfs_feed_url: str, temp_dir: str) -> str:
        archive_path = os.path.join(temp_dir, 'gtfs-feed.zip')

        response = requests.get(gtfs_feed_url, timeout=120)
        response.raise_for_status()

        with open(archive_path, 'wb') as file_handle:
            file_handle.write(response.content)

        return archive_path

    def _extract_feed(self, archive_path: str, temp_dir: str) -> str:
        extract_dir = os.path.join(temp_dir, 'gtfs')
        os.makedirs(extract_dir, exist_ok=True)

        with zipfile.ZipFile(archive_path) as archive:
            archive.extractall(extract_dir)

        nested_dir = self._find_nested_feed_dir(extract_dir)
        if nested_dir is not None:
            normalized_dir = os.path.join(temp_dir, 'gtfs-normalized')
            shutil.copytree(nested_dir, normalized_dir)
            return normalized_dir

        return extract_dir

    def _find_nested_feed_dir(self, extract_dir: str) -> str | None:
        if self._is_gtfs_directory(extract_dir):
            return None

        for current_root, _, _ in os.walk(extract_dir):
            if current_root == extract_dir:
                continue

            if self._is_gtfs_directory(current_root):
                return current_root

        return None

    def _is_gtfs_directory(self, directory: str) -> bool:
        required_files = {
            'routes.txt',
            'trips.txt',
            'stop_times.txt',
        }
        available_files = set(os.listdir(directory))
        return required_files.issubset(available_files)

    def _reduce_ifopt(self, ifopt_id: str) -> str:
        pattern = r'^[a-z]{2}:\d{5}:[\w\d]+(:[\w\d]+){0,2}$'
        if re.fullmatch(pattern, ifopt_id) is not None:
            return ':'.join(ifopt_id.split(':')[:3])

        return ifopt_id

    def _read_csv_rows(self, gtfs_path: str, filename: str) -> list[dict[str, str]]:
        file_path = os.path.join(gtfs_path, filename)
        with open(file_path, encoding='utf-8-sig') as file_handle:
            return list(csv.DictReader(file_handle, delimiter=','))

    def _load_valid_service_ids(self, gtfs_path: str) -> set[str]:
        current_date = int(datetime.today().strftime('%Y%m%d'))
        current_weekday = datetime.today().strftime('%A').lower()

        valid_service_ids: set[str] = set()

        calendar_path = os.path.join(gtfs_path, 'calendar.txt')
        if os.path.exists(calendar_path):
            for row in self._read_csv_rows(gtfs_path, 'calendar.txt'):
                if row[current_weekday] == '1' and int(row['start_date']) <= current_date and int(row['end_date']) >= current_date:
                    valid_service_ids.add(row['service_id'])

        calendar_dates_path = os.path.join(gtfs_path, 'calendar_dates.txt')
        if os.path.exists(calendar_dates_path):
            for row in self._read_csv_rows(gtfs_path, 'calendar_dates.txt'):
                if int(row['date']) != current_date:
                    continue

                service_id = row['service_id']
                exception_type = row['exception_type']

                if exception_type == '1':
                    valid_service_ids.add(service_id)
                elif exception_type == '2':
                    valid_service_ids.discard(service_id)

        return valid_service_ids

    def _load_route_ids(self, gtfs_path: str, configured_lines: list[str]) -> set[str] | None:
        normalized_lines = {str(line).strip() for line in configured_lines if str(line).strip()}
        if len(normalized_lines) == 0:
            return None

        route_ids: set[str] = set()
        for row in self._read_csv_rows(gtfs_path, 'routes.txt'):
            route_short_name = (row.get('route_short_name') or '').strip()
            if route_short_name in normalized_lines:
                route_ids.add(row['route_id'])

        return route_ids

    def _load_trip_ids_for_service_ids(
        self,
        gtfs_path: str,
        valid_service_ids: set[str],
        filter_route_ids: set[str] | None,
    ) -> set[str]:
        valid_trips: set[str] = set()

        for row in self._read_csv_rows(gtfs_path, 'trips.txt'):
            if row['service_id'] not in valid_service_ids:
                continue

            if filter_route_ids is not None and row['route_id'] not in filter_route_ids:
                continue

            valid_trips.add(row['trip_id'])

        return valid_trips

    def _load_trips_per_stop(self, gtfs_path: str, valid_trip_ids: set[str]) -> dict[str, set[str]]:
        trips_per_stop: dict[str, set[str]] = defaultdict(set)
        rows = self._read_csv_rows(gtfs_path, 'stop_times.txt')

        for index in range(len(rows) - 1):
            row = rows[index]
            next_row = rows[index + 1]

            if row['trip_id'] not in valid_trip_ids:
                continue

            if row.get('pickup_type') == '1':
                continue

            if row['trip_id'] != next_row['trip_id']:
                continue

            stop_id = self._reduce_ifopt(row['stop_id'])
            trips_per_stop[stop_id].add(row['trip_id'])

        return trips_per_stop

    def _find_minimal_stop_set(self, trips_per_stop: dict[str, set[str]]) -> set[str]:
        if len(trips_per_stop) == 0:
            return set()

        all_trips = set().union(*trips_per_stop.values())
        covered_trips: set[str] = set()
        selected_stops: set[str] = set()

        while covered_trips != all_trips:
            best_stop, best_trips = max(
                trips_per_stop.items(),
                key=lambda item: len(item[1] - covered_trips),
            )

            if len(best_trips - covered_trips) == 0:
                break

            selected_stops.add(best_stop)
            covered_trips.update(best_trips)

        return selected_stops
