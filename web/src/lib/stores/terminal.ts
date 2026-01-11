// =============================================================================
// ET Phone Home - Terminal Store
// =============================================================================

import { writable, derived } from 'svelte/store';
import { api } from '$api/client';
import type { CommandRecord } from '$types';

// -----------------------------------------------------------------------------
// Types
// -----------------------------------------------------------------------------

export interface TerminalSession {
	id: string;
	clientUuid: string;
	index: number;
	createdAt: Date;
	cwd: string;
	history: TerminalHistoryEntry[];
	historyIndex: number;
}

export interface TerminalHistoryEntry {
	command: string;
	output: string;
	returncode: number;
	timestamp: Date;
}

export interface TerminalState {
	sessions: TerminalSession[];
	activeSessionId: string | null;
	executing: boolean;
	error: string | null;
}

// -----------------------------------------------------------------------------
// Store
// -----------------------------------------------------------------------------

const initialState: TerminalState = {
	sessions: [],
	activeSessionId: null,
	executing: false,
	error: null
};

export const terminalState = writable<TerminalState>(initialState);

let sessionCounter = 0;

// -----------------------------------------------------------------------------
// Derived Stores
// -----------------------------------------------------------------------------

export const sessions = derived(terminalState, ($state) => $state.sessions);

export const activeSession = derived(terminalState, ($state) =>
	$state.sessions.find((s) => s.id === $state.activeSessionId)
);

export const isExecuting = derived(terminalState, ($state) => $state.executing);

export const terminalError = derived(terminalState, ($state) => $state.error);

export const sessionCount = derived(terminalState, ($state) => $state.sessions.length);

// -----------------------------------------------------------------------------
// Actions
// -----------------------------------------------------------------------------

/**
 * Generate a UUID (fallback for non-secure contexts)
 */
function generateUUID(): string {
	// Use crypto.randomUUID if available (secure contexts only)
	if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
		return crypto.randomUUID();
	}
	// Fallback for non-secure contexts (HTTP)
	return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
		const r = (Math.random() * 16) | 0;
		const v = c === 'x' ? r : (r & 0x3) | 0x8;
		return v.toString(16);
	});
}

/**
 * Create a new terminal session
 */
export function createSession(clientUuid: string): string {
	const sessionId = generateUUID();
	sessionCounter++;

	const session: TerminalSession = {
		id: sessionId,
		clientUuid,
		index: sessionCounter,
		createdAt: new Date(),
		cwd: '~',
		history: [],
		historyIndex: -1
	};

	terminalState.update((s) => ({
		...s,
		sessions: [...s.sessions, session],
		activeSessionId: sessionId
	}));

	return sessionId;
}

/**
 * Close a terminal session
 */
export function closeSession(sessionId: string): void {
	terminalState.update((s) => {
		const sessions = s.sessions.filter((sess) => sess.id !== sessionId);
		let activeSessionId = s.activeSessionId;

		// If closing the active session, switch to another
		if (activeSessionId === sessionId) {
			activeSessionId = sessions.length > 0 ? sessions[sessions.length - 1].id : null;
		}

		return { ...s, sessions, activeSessionId };
	});
}

/**
 * Set active session
 */
export function setActiveSession(sessionId: string): void {
	terminalState.update((s) => ({
		...s,
		activeSessionId: sessionId
	}));
}

/**
 * Execute a command in a session
 */
export async function executeCommand(sessionId: string, command: string): Promise<CommandRecord | null> {
	let session: TerminalSession | undefined;
	terminalState.subscribe((s) => {
		session = s.sessions.find((sess) => sess.id === sessionId);
	})();

	if (!session) return null;

	terminalState.update((s) => ({
		...s,
		executing: true,
		error: null
	}));

	// Handle special commands
	if (command.trim() === 'clear') {
		terminalState.update((s) => ({
			...s,
			executing: false,
			sessions: s.sessions.map((sess) =>
				sess.id === sessionId ? { ...sess, history: [] } : sess
			)
		}));
		return null;
	}

	// Handle cd command to track working directory
	const cdMatch = command.trim().match(/^cd\s+(.+)$/);
	if (cdMatch) {
		const newDir = cdMatch[1].trim();
		terminalState.update((s) => ({
			...s,
			sessions: s.sessions.map((sess) =>
				sess.id === sessionId ? { ...sess, cwd: newDir } : sess
			)
		}));
	}

	const response = await api.runCommand(session.clientUuid, command, {
		cwd: session.cwd !== '~' ? session.cwd : undefined
	});

	if (response.error) {
		terminalState.update((s) => ({
			...s,
			executing: false,
			error: response.error
		}));

		// Still add to history as failed command
		const entry: TerminalHistoryEntry = {
			command,
			output: response.error || 'Command failed',
			returncode: -1,
			timestamp: new Date()
		};

		terminalState.update((s) => ({
			...s,
			sessions: s.sessions.map((sess) =>
				sess.id === sessionId
					? { ...sess, history: [...sess.history, entry], historyIndex: sess.history.length }
					: sess
			)
		}));

		return null;
	}

	const record = response.data;
	if (record) {
		const entry: TerminalHistoryEntry = {
			command: record.command,
			output: record.stdout + (record.stderr ? `\n${record.stderr}` : ''),
			returncode: record.returncode,
			timestamp: new Date(record.completed_at)
		};

		terminalState.update((s) => ({
			...s,
			executing: false,
			sessions: s.sessions.map((sess) =>
				sess.id === sessionId
					? { ...sess, history: [...sess.history, entry], historyIndex: sess.history.length }
					: sess
			)
		}));
	} else {
		terminalState.update((s) => ({ ...s, executing: false }));
	}

	return record;
}

/**
 * Get previous command from history
 */
export function getPreviousCommand(sessionId: string): string | null {
	let result: string | null = null;

	terminalState.update((s) => {
		const session = s.sessions.find((sess) => sess.id === sessionId);
		if (!session || session.history.length === 0) return s;

		const newIndex = Math.max(0, session.historyIndex - 1);
		result = session.history[newIndex]?.command || null;

		return {
			...s,
			sessions: s.sessions.map((sess) =>
				sess.id === sessionId ? { ...sess, historyIndex: newIndex } : sess
			)
		};
	});

	return result;
}

/**
 * Get next command from history
 */
export function getNextCommand(sessionId: string): string | null {
	let result: string | null = null;

	terminalState.update((s) => {
		const session = s.sessions.find((sess) => sess.id === sessionId);
		if (!session) return s;

		const newIndex = Math.min(session.history.length, session.historyIndex + 1);
		result = newIndex < session.history.length ? session.history[newIndex]?.command : '';

		return {
			...s,
			sessions: s.sessions.map((sess) =>
				sess.id === sessionId ? { ...sess, historyIndex: newIndex } : sess
			)
		};
	});

	return result;
}

/**
 * Reset history index to end
 */
export function resetHistoryIndex(sessionId: string): void {
	terminalState.update((s) => ({
		...s,
		sessions: s.sessions.map((sess) =>
			sess.id === sessionId ? { ...sess, historyIndex: sess.history.length } : sess
		)
	}));
}

/**
 * Clear all sessions
 */
export function clearTerminal(): void {
	terminalState.set(initialState);
	sessionCounter = 0;
}

/**
 * Get sessions for a specific client
 */
export function getSessionsForClient(clientUuid: string): TerminalSession[] {
	let result: TerminalSession[] = [];
	terminalState.subscribe((s) => {
		result = s.sessions.filter((sess) => sess.clientUuid === clientUuid);
	})();
	return result;
}
