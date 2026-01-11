// =============================================================================
// ET Phone Home - TypeScript Type Definitions
// =============================================================================

// -----------------------------------------------------------------------------
// Client Types
// -----------------------------------------------------------------------------

export interface Client {
	uuid: string;
	display_name: string;
	hostname: string;
	platform: string;
	purpose: string;
	tags: string[];
	online: boolean;
	last_seen: string;
	is_selected: boolean;
	key_mismatch?: boolean;
}

export interface ClientDetail extends Client {
	client_version: string;
	tunnel_port: number;
	ssh_key_fingerprint: string;
	first_seen: string;
	allowed_paths: string[] | null;
	webhook_url: string | null;
	rate_limit_rpm: number | null;
	rate_limit_concurrent: number | null;
	capabilities: string[];
	metadata: Record<string, unknown>;
}

// -----------------------------------------------------------------------------
// Dashboard Types
// -----------------------------------------------------------------------------

export interface DashboardData {
	server: {
		uptime_seconds: number;
		version: string;
	};
	clients: {
		online: number;
		total: number;
	};
	tunnels: {
		active: number;
	};
}

// -----------------------------------------------------------------------------
// Event Types
// -----------------------------------------------------------------------------

export type EventType =
	| 'client.connected'
	| 'client.disconnected'
	| 'client.key_mismatch'
	| 'client.unhealthy'
	| 'command_executed'
	| 'file_accessed';

export interface ActivityEvent {
	timestamp: string;
	type: EventType;
	client_uuid: string;
	client_name: string;
	summary: string;
}

// -----------------------------------------------------------------------------
// WebSocket Message Types
// -----------------------------------------------------------------------------

export interface WSMessage {
	type: string;
	timestamp?: string;
	data?: Record<string, unknown>;
}

export interface WSInitialState extends WSMessage {
	type: 'initial_state';
	data: {
		clients: Client[];
		online_count: number;
		total_count: number;
	};
}

export interface WSClientConnected extends WSMessage {
	type: 'client.connected';
	data: {
		uuid: string;
		display_name: string;
	};
}

export interface WSClientDisconnected extends WSMessage {
	type: 'client.disconnected';
	data: {
		uuid: string;
		display_name: string;
	};
}

// -----------------------------------------------------------------------------
// API Response Types
// -----------------------------------------------------------------------------

export interface ApiResponse<T> {
	data: T | null;
	error: string | null;
}

export interface ClientsResponse {
	clients: Client[];
}

export interface ClientDetailResponse extends ClientDetail {}

export interface EventsResponse {
	events: ActivityEvent[];
}

// -----------------------------------------------------------------------------
// Metrics Types
// -----------------------------------------------------------------------------

export interface ClientMetrics {
	cpu_percent: number;
	memory_percent: number;
	memory_used_mb: number;
	memory_total_mb: number;
	disk_percent: number;
	disk_used_gb: number;
	disk_total_gb: number;
	uptime_seconds: number;
	load_avg: [number, number, number];
}

// -----------------------------------------------------------------------------
// Command/File Types
// -----------------------------------------------------------------------------

export interface CommandResult {
	stdout: string;
	stderr: string;
	returncode: number;
	duration_ms: number;
}

export interface CommandRecord {
	id: string;
	client_uuid: string;
	command: string;
	cwd: string | null;
	stdout: string;
	stderr: string;
	returncode: number;
	started_at: string;
	completed_at: string;
	duration_ms: number;
	user: string;
}

export interface CommandHistoryResponse {
	commands: CommandRecord[];
	total: number;
	limit: number;
	offset: number;
}

export interface FileEntry {
	name: string;
	type: 'file' | 'dir' | 'symlink';
	size: number;
	permissions: string;
	modified: string | number; // Unix timestamp (seconds) or ISO string
	owner?: string;
	group?: string;
	target?: string; // For symlinks
}

export interface FileListResponse {
	path: string;
	entries: FileEntry[];
}

export interface FilePreview {
	path: string;
	content: string | null;
	binary: boolean;
	size: number;
	mimeType: string;
}

export interface UploadProgress {
	filename: string;
	loaded: number;
	total: number;
	percent: number;
}

export interface UploadResponse {
	path: string;
	size: number;
	binary: boolean;
}

// -----------------------------------------------------------------------------
// Terminal Types
// -----------------------------------------------------------------------------

// Note: TerminalSession is defined in stores/terminal.ts as TerminalSessionState

export type TerminalMessageType =
	| 'terminal.open'
	| 'terminal.input'
	| 'terminal.output'
	| 'terminal.resize'
	| 'terminal.close'
	| 'terminal.error';

export interface TerminalMessage {
	type: TerminalMessageType;
	data: {
		session_id?: string;
		client_uuid?: string;
		data?: string;
		rows?: number;
		cols?: number;
		error?: string;
	};
}

// -----------------------------------------------------------------------------
// Rate Limit Types
// -----------------------------------------------------------------------------

export interface RateLimitStats {
	uuid: string;
	requests_per_minute: number;
	concurrent_requests: number;
	limit_rpm: number;
	limit_concurrent: number;
}

// -----------------------------------------------------------------------------
// Utility Types
// -----------------------------------------------------------------------------

export type ConnectionStatus = 'connected' | 'connecting' | 'disconnected' | 'error';

export interface Toast {
	id: string;
	type: 'success' | 'error' | 'warning' | 'info';
	message: string;
	duration?: number;
}
