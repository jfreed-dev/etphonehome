// =============================================================================
// Reach - Auth Store
// =============================================================================

import { writable, derived, get } from 'svelte/store';
import { getApiToken, setApiToken, clearApiToken, api } from '$api/client';
import { connect, disconnect } from './connection';

// -----------------------------------------------------------------------------
// State
// -----------------------------------------------------------------------------

export const isAuthenticated = writable<boolean>(false);
export const authError = writable<string | null>(null);
export const authLoading = writable<boolean>(false);

// -----------------------------------------------------------------------------
// Actions
// -----------------------------------------------------------------------------

export async function login(apiKey: string): Promise<boolean> {
	authLoading.set(true);
	authError.set(null);

	// Store the token
	setApiToken(apiKey);

	// Test the token by making an API call
	const response = await api.getDashboard();

	if (response.error) {
		clearApiToken();
		authError.set(response.error);
		authLoading.set(false);
		return false;
	}

	isAuthenticated.set(true);
	authLoading.set(false);

	// Connect WebSocket after successful auth
	connect();

	return true;
}

export function logout(): void {
	clearApiToken();
	disconnect();
	isAuthenticated.set(false);
	authError.set(null);
}

export function checkAuth(): boolean {
	const hasToken = getApiToken() !== null;
	isAuthenticated.set(hasToken);
	return hasToken;
}

// -----------------------------------------------------------------------------
// Initialize auth state on page load
// -----------------------------------------------------------------------------

export function initAuth(): void {
	checkAuth();
}
