import logging

from datetime import datetime
from datetime import timezone
from typing import Any

import requests

from realtimeobserver.adapter.base import BaseAdapter
from realtimeobserver.version import version


class EfaJsonAdapter(BaseAdapter):
    def process(self, stop_id: str, line_ids: list[str]|None) -> tuple[list[dict], str|None]:
        stop_events = self._request_stop_events(stop_id)

        transformed_events: list[dict] = []

        now = datetime.now(timezone.utc)
        next_departure_at: datetime|None = None

        for stop_event in stop_events:
            transformed_event = self._transform_stop_event(stop_event, stop_id)

            line_name = transformed_event['line_name']
            if line_ids is not None and line_name not in line_ids:
                continue

            transformed_events.append(transformed_event)

            departure_at = self._extract_departure_datetime(stop_event)
            if departure_at is None or departure_at < now:
                continue

            if next_departure_at is None or departure_at < next_departure_at:
                next_departure_at = departure_at

        next_departure_timestamp = next_departure_at.isoformat() if next_departure_at is not None else None

        return (transformed_events, next_departure_timestamp)

    def _request_stop_events(self, stop_id: str) -> list[dict]:
        params = self._build_params(stop_id)
        headers = self._build_headers()

        try:
            response = requests.get(self._endpoint, params=params, headers=headers, timeout=30)
            response.raise_for_status()
            payload = response.json()
            return payload.get('stopEvents', []) or []
        except Exception as ex:
            logging.error('EFA-JSON request failed for stop %s: %s', stop_id, ex)
            return []

    def _build_params(self, stop_id: str) -> dict[str, str]:
        return {
            'action': 'XML_DM_REQUEST',
            'outputFormat': 'rapidJSON',
            'type_dm': 'all',
            'name_dm': stop_id,
            'mode': 'direct',
            'useRealtime': '1',
        }

    def _build_headers(self) -> dict[str, str]:
        headers = {
            'User-Agent': f"realtime-observer/{version}",
        }

        if self._token:
            headers['Authorization'] = f"Bearer {self._token}"

        return headers

    def _extract_departure_datetime(self, stop_event: dict[str, Any]) -> datetime|None:
        departure_timestamp = self._extract_departure_timestamp(stop_event)
        if not departure_timestamp:
            return None

        try:
            return datetime.fromisoformat(departure_timestamp)
        except ValueError:
            return None

    def _extract_departure_timestamp(self, stop_event: dict[str, Any]) -> str:
        departure_planned = stop_event.get('departureTimePlanned') or ''
        departure_estimated = stop_event.get('departureTimeEstimated') or ''
        departure_base = stop_event.get('departureTimeBaseTimetable') or ''

        raw_departure = departure_estimated or departure_planned or departure_base

        return self._normalize_timestamp(raw_departure)

    def _build_trip_id(self, transportation: dict[str, Any], transportation_properties: dict[str, Any]) -> str:
        transportation_id = transportation.get('id') or ''
        trip_code = transportation_properties.get('tripCode')
        if trip_code is not None and transportation_id:
            return f"{transportation_id}:{trip_code}"

        return transportation_id

    def _normalize_timestamp(self, value: str|None) -> str:
        if not value:
            return ''

        return value.replace('Z', '+00:00')

    def _transform_stop_event(self, stop_event: dict[str, Any], stop_id: str) -> dict:
        transportation = stop_event.get('transportation', {}) or {}
        transportation_properties = transportation.get('properties', {}) or {}

        origin = transportation.get('origin', {}) or {}
        destination = transportation.get('destination', {}) or {}

        line_id = transportation_properties.get('globalId') or ''
        line_name = transportation.get('number') or transportation.get('name') or line_id

        departure_planned = stop_event.get('departureTimePlanned') or ''
        departure_base = stop_event.get('departureTimeBaseTimetable') or departure_planned

        departure_estimated = stop_event.get('departureTimeEstimated')

        operation_day = departure_base[:10] if departure_base else ''
        trip_id = self._build_trip_id(transportation, transportation_properties)

        realtime_status = stop_event.get('realtimeStatus', []) or []
        realtime_monitored = bool(stop_event.get('isRealtimeControlled')) or ('MONITORED' in realtime_status)

        realtime_cancelled = 1 if 'CANCELLED' in realtime_status else 0

        return {
            'operation_day': operation_day,
            'trip_id': trip_id,
            'line_id': line_id,
            'line_name': line_name,
            'origin_stop_id': origin.get('id') or '',
            'origin_name': origin.get('name') or '',
            'destination_stop_id': destination.get('id') or '',
            'destination_name': destination.get('name') or '',
            'start_time': self._normalize_timestamp(departure_base),
            'end_time': None,
            'realtime_ref_station': stop_id,
            'realtime_first_appeared': datetime.now().isoformat() if realtime_monitored or departure_estimated else None,
            'realtime_cancelled': realtime_cancelled,
            'realtime_num_cancelled_stops': 0,
            'realtime_num_added_stops': 0,
            'realtime_monitored': realtime_monitored,
        }