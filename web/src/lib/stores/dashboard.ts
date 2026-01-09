// =============================================================================
// ET Phone Home - Dashboard Store
// =============================================================================

import { writable, derived } from 'svelte/store';
import type { DashboardData } from '$types';
import { api } from '$api/client';

// -----------------------------------------------------------------------------
// State
// -----------------------------------------------------------------------------

export const dashboardData = writable<DashboardData | null>(null);
export const dashboardLoading = writable<boolean>(false);
export const dashboardError = writable<string | null>(null);

// -----------------------------------------------------------------------------
// Derived Stores
// -----------------------------------------------------------------------------

export const serverUptime = derived(dashboardData, ($data) => {
	if (!$data) return null;
	return formatUptime($data.server.uptime_seconds);
});

export const serverVersion = derived(dashboardData, ($data) =>
	$data?.server.version ?? null
);

// -----------------------------------------------------------------------------
// Actions
// -----------------------------------------------------------------------------

export async function fetchDashboard(): Promise<void> {
	dashboardLoading.set(true);
	dashboardError.set(null);

	const response = await api.getDashboard();

	if (response.error) {
		dashboardError.set(response.error);
	} else if (response.data) {
		dashboardData.set(response.data);
	}

	dashboardLoading.set(false);
}

// -----------------------------------------------------------------------------
// Helpers
// -----------------------------------------------------------------------------

function formatUptime(seconds: number): string {
	const days = Math.floor(seconds / 86400);
	const hours = Math.floor((seconds % 86400) / 3600);
	const minutes = Math.floor((seconds % 3600) / 60);

	const parts: string[] = [];
	if (days > 0) parts.push(`${days}d`);
	if (hours > 0) parts.push(`${hours}h`);
	if (minutes > 0 || parts.length === 0) parts.push(`${minutes}m`);

	return parts.join(' ');
}
