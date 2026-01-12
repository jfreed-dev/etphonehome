// =============================================================================
// ET Phone Home - TypeScript API Client
// =============================================================================

import type {
	ApiResponse,
	Client,
	ClientDetail,
	ClientsResponse,
	DashboardData,
	EventsResponse,
	ActivityEvent,
	CommandRecord,
	CommandHistoryResponse,
	FileListResponse,
	FilePreview,
	UploadResponse
} from '$types';

// -----------------------------------------------------------------------------
// Configuration
// -----------------------------------------------------------------------------

const API_BASE = '/api/v1';

// Storage key for API token
const TOKEN_KEY = 'etphonehome_api_key';

// -----------------------------------------------------------------------------
// Token Management
// -----------------------------------------------------------------------------

export function getApiToken(): string | null {
	if (typeof localStorage === 'undefined') return null;
	return localStorage.getItem(TOKEN_KEY);
}

export function setApiToken(token: string): void {
	if (typeof localStorage === 'undefined') return;
	localStorage.setItem(TOKEN_KEY, token);
}

export function clearApiToken(): void {
	if (typeof localStorage === 'undefined') return;
	localStorage.removeItem(TOKEN_KEY);
}

export function hasApiToken(): boolean {
	return getApiToken() !== null;
}

// -----------------------------------------------------------------------------
// HTTP Client
// -----------------------------------------------------------------------------

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<ApiResponse<T>> {
	const token = getApiToken();

	const headers: HeadersInit = {
		'Content-Type': 'application/json',
		...(options.headers || {})
	};

	if (token) {
		(headers as Record<string, string>)['Authorization'] = `Bearer ${token}`;
	}

	try {
		const response = await fetch(`${API_BASE}${endpoint}`, {
			...options,
			headers
		});

		if (response.status === 401) {
			clearApiToken();
			return { data: null, error: 'Unauthorized - please enter your API key' };
		}

		if (!response.ok) {
			const errorData = await response.json().catch(() => ({}));
			return {
				data: null,
				error: errorData.error || `Request failed: ${response.status}`
			};
		}

		const data = await response.json();
		return { data, error: null };
	} catch (err) {
		const message = err instanceof Error ? err.message : 'Network error';
		return { data: null, error: message };
	}
}

// -----------------------------------------------------------------------------
// API Methods
// -----------------------------------------------------------------------------

export const api = {
	/**
	 * Get dashboard summary data
	 */
	async getDashboard(): Promise<ApiResponse<DashboardData>> {
		return request<DashboardData>('/dashboard');
	},

	/**
	 * Get all clients
	 */
	async getClients(): Promise<ApiResponse<ClientsResponse>> {
		return request<ClientsResponse>('/clients');
	},

	/**
	 * Get detailed info about a specific client
	 */
	async getClient(uuid: string): Promise<ApiResponse<ClientDetail>> {
		return request<ClientDetail>(`/clients/${uuid}`);
	},

	/**
	 * Get recent activity events
	 */
	async getEvents(limit: number = 20): Promise<ApiResponse<EventsResponse>> {
		return request<EventsResponse>(`/events?limit=${limit}`);
	},

	/**
	 * Update client metadata
	 */
	async updateClient(
		uuid: string,
		data: Partial<{
			display_name: string;
			purpose: string;
			tags: string[];
			allowed_paths: string[] | null;
		}>
	): Promise<ApiResponse<ClientDetail>> {
		return request<ClientDetail>(`/clients/${uuid}`, {
			method: 'PATCH',
			body: JSON.stringify(data)
		});
	},

	/**
	 * Check server health (no auth required)
	 */
	async checkHealth(): Promise<boolean> {
		try {
			const response = await fetch('/health');
			return response.ok;
		} catch {
			return false;
		}
	},

	// -------------------------------------------------------------------------
	// Command History API
	// -------------------------------------------------------------------------

	/**
	 * Get command history for a client
	 */
	async getCommandHistory(
		clientUuid: string,
		options?: {
			limit?: number;
			offset?: number;
			search?: string;
			status?: 'all' | 'success' | 'failed';
		}
	): Promise<ApiResponse<CommandHistoryResponse>> {
		const params = new URLSearchParams();
		if (options?.limit) params.set('limit', String(options.limit));
		if (options?.offset) params.set('offset', String(options.offset));
		if (options?.search) params.set('search', options.search);
		if (options?.status && options.status !== 'all') {
			params.set('status', options.status);
		}
		const query = params.toString();
		return request<CommandHistoryResponse>(
			`/clients/${clientUuid}/history${query ? `?${query}` : ''}`
		);
	},

	/**
	 * Get a single command record
	 */
	async getCommandDetail(
		clientUuid: string,
		commandId: string
	): Promise<ApiResponse<CommandRecord>> {
		return request<CommandRecord>(`/clients/${clientUuid}/history/${commandId}`);
	},

	/**
	 * Run a command on a client and save to history
	 */
	async runCommand(
		clientUuid: string,
		command: string,
		options?: {
			cwd?: string;
			timeout?: number;
		}
	): Promise<ApiResponse<CommandRecord>> {
		return request<CommandRecord>(`/clients/${clientUuid}/history`, {
			method: 'POST',
			body: JSON.stringify({
				command,
				cwd: options?.cwd,
				timeout: options?.timeout
			})
		});
	},

	// -------------------------------------------------------------------------
	// File Browser API
	// -------------------------------------------------------------------------

	/**
	 * List files in a directory
	 */
	async listFiles(clientUuid: string, path: string = '/'): Promise<ApiResponse<FileListResponse>> {
		return request<FileListResponse>(
			`/clients/${clientUuid}/files?path=${encodeURIComponent(path)}`
		);
	},

	/**
	 * Preview file content
	 */
	async previewFile(clientUuid: string, path: string): Promise<ApiResponse<FilePreview>> {
		return request<FilePreview>(
			`/clients/${clientUuid}/files/preview?path=${encodeURIComponent(path)}`
		);
	},

	/**
	 * Download a file (triggers browser download)
	 */
	downloadFile(clientUuid: string, path: string): void {
		const token = getApiToken();
		const url = `${API_BASE}/clients/${clientUuid}/files/download?path=${encodeURIComponent(path)}&token=${encodeURIComponent(token || '')}`;
		window.location.href = url;
	},

	/**
	 * Upload a file to a client
	 */
	async uploadFile(
		clientUuid: string,
		file: File,
		destPath: string,
		onProgress?: (percent: number) => void
	): Promise<ApiResponse<UploadResponse>> {
		const token = getApiToken();

		return new Promise((resolve) => {
			const xhr = new XMLHttpRequest();
			const formData = new FormData();
			formData.append('file', file);
			formData.append('path', destPath);

			xhr.upload.onprogress = (event) => {
				if (event.lengthComputable && onProgress) {
					const percent = Math.round((event.loaded / event.total) * 100);
					onProgress(percent);
				}
			};

			xhr.onload = () => {
				try {
					const data = JSON.parse(xhr.responseText);
					if (xhr.status >= 200 && xhr.status < 300) {
						resolve({ data, error: null });
					} else {
						resolve({ data: null, error: data.error || `Upload failed: ${xhr.status}` });
					}
				} catch {
					resolve({ data: null, error: 'Failed to parse response' });
				}
			};

			xhr.onerror = () => {
				resolve({ data: null, error: 'Network error during upload' });
			};

			xhr.open('POST', `${API_BASE}/clients/${clientUuid}/files/upload`);
			if (token) {
				xhr.setRequestHeader('Authorization', `Bearer ${token}`);
			}
			xhr.send(formData);
		});
	}
};

// -----------------------------------------------------------------------------
// WebSocket Connection
// -----------------------------------------------------------------------------

export interface WebSocketCallbacks {
	onOpen?: () => void;
	onClose?: () => void;
	onError?: (error: Event) => void;
	onMessage?: (message: unknown) => void;
	onInitialState?: (clients: Client[], online: number, total: number) => void;
	onClientConnected?: (uuid: string, displayName: string) => void;
	onClientDisconnected?: (uuid: string, displayName: string) => void;
}

export class WebSocketClient {
	private ws: WebSocket | null = null;
	private callbacks: WebSocketCallbacks = {};
	private reconnectAttempts = 0;
	private maxReconnectAttempts = 5;
	private reconnectDelay = 1000;
	private pingInterval: ReturnType<typeof setInterval> | null = null;

	constructor(callbacks: WebSocketCallbacks = {}) {
		this.callbacks = callbacks;
	}

	connect(): void {
		const token = getApiToken();
		if (!token) {
			console.warn('No API token available for WebSocket connection');
			return;
		}

		const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
		const wsUrl = `${protocol}//${window.location.host}/api/v1/ws?token=${encodeURIComponent(token)}`;

		this.ws = new WebSocket(wsUrl);

		this.ws.onopen = () => {
			console.log('WebSocket connected');
			this.reconnectAttempts = 0;
			this.startPing();
			this.callbacks.onOpen?.();
		};

		this.ws.onclose = () => {
			console.log('WebSocket disconnected');
			this.stopPing();
			this.callbacks.onClose?.();
			this.attemptReconnect();
		};

		this.ws.onerror = (error) => {
			console.error('WebSocket error:', error);
			this.callbacks.onError?.(error);
		};

		this.ws.onmessage = (event) => {
			// Skip ping/pong keepalive messages
			if (event.data === 'pong' || event.data === 'ping') {
				return;
			}
			try {
				const message = JSON.parse(event.data);
				this.handleMessage(message);
			} catch (err) {
				console.error('Failed to parse WebSocket message:', err);
			}
		};
	}

	private handleMessage(message: Record<string, unknown>): void {
		this.callbacks.onMessage?.(message);

		switch (message.type) {
			case 'initial_state': {
				const data = message.data as {
					clients: Client[];
					online_count: number;
					total_count: number;
				};
				this.callbacks.onInitialState?.(data.clients, data.online_count, data.total_count);
				break;
			}

			case 'client.connected': {
				const data = message.data as { uuid: string; display_name: string };
				this.callbacks.onClientConnected?.(data.uuid, data.display_name);
				break;
			}

			case 'client.disconnected': {
				const data = message.data as { uuid: string; display_name: string };
				this.callbacks.onClientDisconnected?.(data.uuid, data.display_name);
				break;
			}
		}
	}

	private startPing(): void {
		this.pingInterval = setInterval(() => {
			if (this.ws?.readyState === WebSocket.OPEN) {
				this.ws.send('ping');
			}
		}, 30000);
	}

	private stopPing(): void {
		if (this.pingInterval) {
			clearInterval(this.pingInterval);
			this.pingInterval = null;
		}
	}

	private attemptReconnect(): void {
		if (this.reconnectAttempts >= this.maxReconnectAttempts) {
			console.log('Max reconnection attempts reached');
			return;
		}

		this.reconnectAttempts++;
		const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);

		console.log(`Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`);

		setTimeout(() => {
			this.connect();
		}, delay);
	}

	disconnect(): void {
		this.stopPing();
		if (this.ws) {
			this.ws.close();
			this.ws = null;
		}
	}

	isConnected(): boolean {
		return this.ws?.readyState === WebSocket.OPEN;
	}
}

// Export singleton instance factory
export function createWebSocketClient(callbacks: WebSocketCallbacks): WebSocketClient {
	return new WebSocketClient(callbacks);
}
