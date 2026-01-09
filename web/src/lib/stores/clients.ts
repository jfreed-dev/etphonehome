// =============================================================================
// ET Phone Home - Clients Store
// =============================================================================

import { writable, derived, get } from 'svelte/store';
import type { Client, ClientDetail } from '$types';
import { api } from '$api/client';

// -----------------------------------------------------------------------------
// State
// -----------------------------------------------------------------------------

export const clients = writable<Client[]>([]);
export const selectedClientUuid = writable<string | null>(null);
export const clientsLoading = writable<boolean>(false);
export const clientsError = writable<string | null>(null);

// -----------------------------------------------------------------------------
// Derived Stores
// -----------------------------------------------------------------------------

export const onlineClients = derived(clients, ($clients) =>
	$clients.filter((c) => c.online)
);

export const offlineClients = derived(clients, ($clients) =>
	$clients.filter((c) => !c.online)
);

export const onlineCount = derived(clients, ($clients) =>
	$clients.filter((c) => c.online).length
);

export const totalCount = derived(clients, ($clients) => $clients.length);

export const selectedClient = derived(
	[clients, selectedClientUuid],
	([$clients, $selectedUuid]) => {
		if (!$selectedUuid) return null;
		return $clients.find((c) => c.uuid === $selectedUuid) || null;
	}
);

// -----------------------------------------------------------------------------
// Actions
// -----------------------------------------------------------------------------

export async function fetchClients(): Promise<void> {
	clientsLoading.set(true);
	clientsError.set(null);

	const response = await api.getClients();

	if (response.error) {
		clientsError.set(response.error);
	} else if (response.data) {
		clients.set(response.data.clients);
	}

	clientsLoading.set(false);
}

export function setClients(newClients: Client[]): void {
	clients.set(newClients);
}

export function updateClient(uuid: string, updates: Partial<Client>): void {
	clients.update(($clients) =>
		$clients.map((c) => (c.uuid === uuid ? { ...c, ...updates } : c))
	);
}

export function addClient(client: Client): void {
	clients.update(($clients) => {
		// Check if client already exists
		const exists = $clients.some((c) => c.uuid === client.uuid);
		if (exists) {
			// Update existing client
			return $clients.map((c) =>
				c.uuid === client.uuid ? { ...c, ...client } : c
			);
		}
		// Add new client
		return [...$clients, client];
	});
}

export function setClientOnline(uuid: string, online: boolean): void {
	clients.update(($clients) =>
		$clients.map((c) =>
			c.uuid === uuid
				? { ...c, online, last_seen: new Date().toISOString() }
				: c
		)
	);
}

export function selectClient(uuid: string | null): void {
	selectedClientUuid.set(uuid);
}

// -----------------------------------------------------------------------------
// Client Detail Store (for individual client page)
// -----------------------------------------------------------------------------

export const clientDetail = writable<ClientDetail | null>(null);
export const clientDetailLoading = writable<boolean>(false);
export const clientDetailError = writable<string | null>(null);

export async function fetchClientDetail(uuid: string): Promise<void> {
	clientDetailLoading.set(true);
	clientDetailError.set(null);
	clientDetail.set(null);

	const response = await api.getClient(uuid);

	if (response.error) {
		clientDetailError.set(response.error);
	} else if (response.data) {
		clientDetail.set(response.data);
	}

	clientDetailLoading.set(false);
}

export function clearClientDetail(): void {
	clientDetail.set(null);
	clientDetailError.set(null);
}
