// =============================================================================
// ET Phone Home - Command History Store
// =============================================================================

import { writable, derived, get } from 'svelte/store';
import { api } from '$api/client';
import type { CommandRecord } from '$types';

// -----------------------------------------------------------------------------
// Types
// -----------------------------------------------------------------------------

export type StatusFilter = 'all' | 'success' | 'failed';

export interface CommandHistoryState {
	commands: CommandRecord[];
	loading: boolean;
	error: string | null;
	total: number;
	limit: number;
	offset: number;
	searchQuery: string;
	statusFilter: StatusFilter;
	clientUuid: string | null;
	runningCommand: boolean;
}

// -----------------------------------------------------------------------------
// Store
// -----------------------------------------------------------------------------

const initialState: CommandHistoryState = {
	commands: [],
	loading: false,
	error: null,
	total: 0,
	limit: 50,
	offset: 0,
	searchQuery: '',
	statusFilter: 'all',
	clientUuid: null,
	runningCommand: false
};

export const commandHistoryState = writable<CommandHistoryState>(initialState);

// -----------------------------------------------------------------------------
// Derived Stores
// -----------------------------------------------------------------------------

export const commands = derived(commandHistoryState, ($state) => $state.commands);
export const isLoading = derived(commandHistoryState, ($state) => $state.loading);
export const historyError = derived(commandHistoryState, ($state) => $state.error);
export const totalCommands = derived(commandHistoryState, ($state) => $state.total);
export const isRunningCommand = derived(commandHistoryState, ($state) => $state.runningCommand);

export const hasMore = derived(commandHistoryState, ($state) => {
	return $state.offset + $state.commands.length < $state.total;
});

export const successCount = derived(commandHistoryState, ($state) => {
	return $state.commands.filter((c) => c.returncode === 0).length;
});

export const failedCount = derived(commandHistoryState, ($state) => {
	return $state.commands.filter((c) => c.returncode !== 0).length;
});

// -----------------------------------------------------------------------------
// Actions
// -----------------------------------------------------------------------------

/**
 * Load command history for a client
 */
export async function loadHistory(
	clientUuid: string,
	options?: {
		limit?: number;
		offset?: number;
		search?: string;
		status?: StatusFilter;
		append?: boolean;
	}
): Promise<void> {
	commandHistoryState.update((s) => ({
		...s,
		loading: true,
		error: null,
		clientUuid
	}));

	const response = await api.getCommandHistory(clientUuid, {
		limit: options?.limit ?? 50,
		offset: options?.offset ?? 0,
		search: options?.search,
		status: options?.status
	});

	if (response.error) {
		commandHistoryState.update((s) => ({
			...s,
			loading: false,
			error: response.error
		}));
		return;
	}

	if (response.data) {
		commandHistoryState.update((s) => ({
			...s,
			loading: false,
			commands: options?.append
				? [...s.commands, ...response.data!.commands]
				: response.data!.commands,
			total: response.data!.total,
			limit: response.data!.limit,
			offset: response.data!.offset,
			searchQuery: options?.search ?? s.searchQuery,
			statusFilter: options?.status ?? s.statusFilter
		}));
	}
}

/**
 * Load more commands (pagination)
 */
export async function loadMore(): Promise<void> {
	const state = get(commandHistoryState);

	if (!state.clientUuid || state.loading) return;

	await loadHistory(state.clientUuid, {
		limit: state.limit,
		offset: state.offset + state.limit,
		search: state.searchQuery,
		status: state.statusFilter,
		append: true
	});
}

/**
 * Search command history
 */
export async function searchHistory(query: string): Promise<void> {
	const state = get(commandHistoryState);

	if (!state.clientUuid) return;

	await loadHistory(state.clientUuid, {
		search: query,
		status: state.statusFilter,
		offset: 0
	});
}

/**
 * Filter by status
 */
export async function filterByStatus(status: StatusFilter): Promise<void> {
	const state = get(commandHistoryState);

	if (!state.clientUuid) return;

	await loadHistory(state.clientUuid, {
		search: state.searchQuery,
		status,
		offset: 0
	});
}

/**
 * Run a command and save to history
 */
export async function runCommand(
	clientUuid: string,
	command: string,
	cwd?: string
): Promise<CommandRecord | null> {
	commandHistoryState.update((s) => ({
		...s,
		runningCommand: true,
		error: null
	}));

	const response = await api.runCommand(clientUuid, command, { cwd });

	if (response.error) {
		commandHistoryState.update((s) => ({
			...s,
			runningCommand: false,
			error: response.error
		}));
		return null;
	}

	if (response.data) {
		// Add the new command to the front of the list
		commandHistoryState.update((s) => ({
			...s,
			runningCommand: false,
			commands: [response.data!, ...s.commands],
			total: s.total + 1
		}));
		return response.data;
	}

	commandHistoryState.update((s) => ({ ...s, runningCommand: false }));
	return null;
}

/**
 * Re-run a command from history
 */
export async function rerunCommand(record: CommandRecord): Promise<CommandRecord | null> {
	return runCommand(record.client_uuid, record.command, record.cwd ?? undefined);
}

/**
 * Clear history state
 */
export function clearHistory(): void {
	commandHistoryState.set(initialState);
}

// -----------------------------------------------------------------------------
// Utility Functions
// -----------------------------------------------------------------------------

/**
 * Format duration in human-readable format
 */
export function formatDuration(ms: number): string {
	if (ms < 1000) return `${ms}ms`;
	if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
	const minutes = Math.floor(ms / 60000);
	const seconds = Math.floor((ms % 60000) / 1000);
	return `${minutes}m ${seconds}s`;
}

/**
 * Format timestamp in local time
 */
export function formatTimestamp(iso: string): string {
	const date = new Date(iso);
	return date.toLocaleString();
}

/**
 * Get status color class
 */
export function getStatusClass(returncode: number): string {
	return returncode === 0 ? 'success' : 'failed';
}
