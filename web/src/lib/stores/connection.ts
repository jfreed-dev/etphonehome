// =============================================================================
// ET Phone Home - Connection Store (WebSocket management)
// =============================================================================

import { writable, get } from 'svelte/store';
import type { ConnectionStatus, Client } from '$types';
import { createWebSocketClient, type WebSocketClient, hasApiToken } from '$api/client';
import { setClients, setClientOnline, addClient } from './clients';
import { addEvent } from './events';

// -----------------------------------------------------------------------------
// State
// -----------------------------------------------------------------------------

export const connectionStatus = writable<ConnectionStatus>('disconnected');
export const lastConnected = writable<Date | null>(null);

// -----------------------------------------------------------------------------
// WebSocket Client Instance
// -----------------------------------------------------------------------------

let wsClient: WebSocketClient | null = null;

// -----------------------------------------------------------------------------
// Actions
// -----------------------------------------------------------------------------

export function connect(): void {
	if (!hasApiToken()) {
		connectionStatus.set('disconnected');
		return;
	}

	if (wsClient) {
		wsClient.disconnect();
	}

	connectionStatus.set('connecting');

	wsClient = createWebSocketClient({
		onOpen: () => {
			connectionStatus.set('connected');
			lastConnected.set(new Date());
		},

		onClose: () => {
			connectionStatus.set('disconnected');
		},

		onError: () => {
			connectionStatus.set('error');
		},

		onInitialState: (clients: Client[], _online: number, _total: number) => {
			setClients(clients);
		},

		onClientConnected: (uuid: string, displayName: string) => {
			setClientOnline(uuid, true);
			addEvent({
				timestamp: new Date().toISOString(),
				type: 'client.connected',
				client_uuid: uuid,
				client_name: displayName,
				summary: 'Connected'
			});
		},

		onClientDisconnected: (uuid: string, displayName: string) => {
			setClientOnline(uuid, false);
			addEvent({
				timestamp: new Date().toISOString(),
				type: 'client.disconnected',
				client_uuid: uuid,
				client_name: displayName,
				summary: 'Disconnected'
			});
		}
	});

	wsClient.connect();
}

export function disconnect(): void {
	if (wsClient) {
		wsClient.disconnect();
		wsClient = null;
	}
	connectionStatus.set('disconnected');
}

export function reconnect(): void {
	disconnect();
	setTimeout(() => connect(), 100);
}

export function isConnected(): boolean {
	return get(connectionStatus) === 'connected';
}

// -----------------------------------------------------------------------------
// Auto-connect on token change
// -----------------------------------------------------------------------------

export function initConnection(): void {
	if (hasApiToken()) {
		connect();
	}
}
