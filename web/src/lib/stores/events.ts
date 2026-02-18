// =============================================================================
// Reach - Events Store
// =============================================================================

import { writable, derived } from 'svelte/store';
import type { ActivityEvent, EventType } from '$types';
import { api } from '$api/client';

// -----------------------------------------------------------------------------
// State
// -----------------------------------------------------------------------------

const MAX_EVENTS = 100;

export const events = writable<ActivityEvent[]>([]);
export const eventsLoading = writable<boolean>(false);
export const eventsError = writable<string | null>(null);

// -----------------------------------------------------------------------------
// Derived Stores
// -----------------------------------------------------------------------------

export const recentEvents = derived(events, ($events) => $events.slice(0, 20));

export const connectionEvents = derived(events, ($events) =>
	$events.filter((e) => e.type === 'client.connected' || e.type === 'client.disconnected')
);

export const commandEvents = derived(events, ($events) =>
	$events.filter((e) => e.type === 'command_executed')
);

// -----------------------------------------------------------------------------
// Actions
// -----------------------------------------------------------------------------

export async function fetchEvents(limit: number = 20): Promise<void> {
	eventsLoading.set(true);
	eventsError.set(null);

	const response = await api.getEvents(limit);

	if (response.error) {
		eventsError.set(response.error);
	} else if (response.data) {
		events.set(response.data.events);
	}

	eventsLoading.set(false);
}

export function addEvent(event: ActivityEvent): void {
	events.update(($events) => {
		const newEvents = [event, ...$events];
		// Trim to max events
		if (newEvents.length > MAX_EVENTS) {
			return newEvents.slice(0, MAX_EVENTS);
		}
		return newEvents;
	});
}

export function clearEvents(): void {
	events.set([]);
}

// -----------------------------------------------------------------------------
// Event Helpers
// -----------------------------------------------------------------------------

export function getEventIcon(type: EventType): string {
	switch (type) {
		case 'client.connected':
			return 'link';
		case 'client.disconnected':
			return 'link-off';
		case 'client.key_mismatch':
			return 'key';
		case 'client.unhealthy':
			return 'alert';
		case 'command_executed':
			return 'terminal';
		case 'file_accessed':
			return 'file';
		default:
			return 'info';
	}
}

export function getEventColor(type: EventType): string {
	switch (type) {
		case 'client.connected':
			return 'green';
		case 'client.disconnected':
			return 'red';
		case 'client.key_mismatch':
			return 'amber';
		case 'client.unhealthy':
			return 'amber';
		case 'command_executed':
			return 'cyan';
		case 'file_accessed':
			return 'cyan';
		default:
			return 'cyan';
	}
}

export function formatEventTime(timestamp: string): string {
	const date = new Date(timestamp);
	const now = new Date();
	const diffMs = now.getTime() - date.getTime();
	const diffMins = Math.floor(diffMs / 60000);
	const diffHours = Math.floor(diffMs / 3600000);
	const diffDays = Math.floor(diffMs / 86400000);

	if (diffMins < 1) return 'just now';
	if (diffMins < 60) return `${diffMins}m ago`;
	if (diffHours < 24) return `${diffHours}h ago`;
	if (diffDays < 7) return `${diffDays}d ago`;

	return date.toLocaleDateString();
}
