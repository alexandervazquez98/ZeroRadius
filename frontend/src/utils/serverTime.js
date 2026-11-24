import dayjs from 'dayjs';
import utc from 'dayjs/plugin/utc';

dayjs.extend(utc);

/**
 * Parse a timestamp coming from the API and return it in the browser's local time.
 *
 * The backend stores timestamps in UTC and serializes them without an offset
 * (e.g. "2026-11-24T17:01:15"). Plain dayjs(value) would treat that as local
 * time and show UTC digits, so parse it as UTC first. Strings that already
 * carry an offset ("Z", "+00:00") keep it.
 */
export function parseServerTime(value) {
    return dayjs.utc(value).local();
}

/**
 * Convert a local date/time picked in the UI (e.g. a datetime-local value)
 * into the UTC, offset-less format the backend compares against.
 */
export function toServerTime(localValue) {
    return dayjs(localValue).utc().format('YYYY-MM-DDTHH:mm:ss');
}
