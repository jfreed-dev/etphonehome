// =============================================================================
// Reach - File Browser Store
// =============================================================================

import { writable, derived, get } from 'svelte/store';
import { api } from '$api/client';
import type { FileEntry, FilePreview, UploadProgress } from '$types';

// -----------------------------------------------------------------------------
// Types
// -----------------------------------------------------------------------------

export type SortField = 'name' | 'size' | 'modified' | 'type';
export type SortDirection = 'asc' | 'desc';

export interface FileBrowserState {
	currentPath: string;
	entries: FileEntry[];
	loading: boolean;
	error: string | null;
	selectedFile: FileEntry | null;
	sortBy: SortField;
	sortDir: SortDirection;
	history: string[];
	historyIndex: number;
	clientUuid: string | null;
	preview: FilePreview | null;
	previewLoading: boolean;
	previewError: string | null;
	uploading: boolean;
	uploadProgress: UploadProgress | null;
}

// -----------------------------------------------------------------------------
// Store
// -----------------------------------------------------------------------------

const initialState: FileBrowserState = {
	currentPath: '/',
	entries: [],
	loading: false,
	error: null,
	selectedFile: null,
	sortBy: 'name',
	sortDir: 'asc',
	history: ['/'],
	historyIndex: 0,
	clientUuid: null,
	preview: null,
	previewLoading: false,
	previewError: null,
	uploading: false,
	uploadProgress: null
};

export const fileBrowserState = writable<FileBrowserState>(initialState);

// -----------------------------------------------------------------------------
// Derived Stores
// -----------------------------------------------------------------------------

export const currentPath = derived(fileBrowserState, ($state) => $state.currentPath);
export const entries = derived(fileBrowserState, ($state) => $state.entries);
export const isLoading = derived(fileBrowserState, ($state) => $state.loading);
export const browserError = derived(fileBrowserState, ($state) => $state.error);
export const selectedFile = derived(fileBrowserState, ($state) => $state.selectedFile);
export const preview = derived(fileBrowserState, ($state) => $state.preview);
export const isPreviewLoading = derived(fileBrowserState, ($state) => $state.previewLoading);
export const isUploading = derived(fileBrowserState, ($state) => $state.uploading);
export const uploadProgress = derived(fileBrowserState, ($state) => $state.uploadProgress);

/**
 * Parse modified time to milliseconds (handles Unix timestamps and ISO strings)
 */
function parseModifiedTime(modified: string | number): number {
	if (typeof modified === 'number') {
		return modified * 1000;
	} else if (typeof modified === 'string' && !isNaN(Number(modified))) {
		return Number(modified) * 1000;
	} else {
		return new Date(modified).getTime();
	}
}

// Sorted entries with directories first
export const sortedEntries = derived(fileBrowserState, ($state) => {
	const sorted = [...$state.entries].sort((a, b) => {
		// Directories always first
		if (a.type === 'dir' && b.type !== 'dir') return -1;
		if (a.type !== 'dir' && b.type === 'dir') return 1;

		// Then sort by selected field
		let comparison = 0;
		switch ($state.sortBy) {
			case 'name':
				comparison = a.name.localeCompare(b.name);
				break;
			case 'size':
				comparison = a.size - b.size;
				break;
			case 'modified':
				comparison = parseModifiedTime(a.modified) - parseModifiedTime(b.modified);
				break;
			case 'type':
				comparison = a.type.localeCompare(b.type);
				break;
		}

		return $state.sortDir === 'asc' ? comparison : -comparison;
	});

	return sorted;
});

// Breadcrumb path segments
export const pathSegments = derived(fileBrowserState, ($state) => {
	const parts = $state.currentPath.split('/').filter(Boolean);
	const segments: { name: string; path: string }[] = [{ name: '/', path: '/' }];

	let currentPath = '';
	for (const part of parts) {
		currentPath += `/${part}`;
		segments.push({ name: part, path: currentPath });
	}

	return segments;
});

// Can go back in history
export const canGoBack = derived(fileBrowserState, ($state) => $state.historyIndex > 0);

// Can go forward in history
export const canGoForward = derived(
	fileBrowserState,
	($state) => $state.historyIndex < $state.history.length - 1
);

// -----------------------------------------------------------------------------
// Actions
// -----------------------------------------------------------------------------

/**
 * Navigate to a path
 */
export async function navigateTo(clientUuid: string, path: string): Promise<void> {
	fileBrowserState.update((s) => ({
		...s,
		loading: true,
		error: null,
		clientUuid,
		selectedFile: null,
		preview: null
	}));

	const response = await api.listFiles(clientUuid, path);

	if (response.error) {
		fileBrowserState.update((s) => ({
			...s,
			loading: false,
			error: response.error
		}));
		return;
	}

	if (response.data) {
		fileBrowserState.update((s) => {
			// Add to history only if navigating forward
			const newHistory = [...s.history.slice(0, s.historyIndex + 1), path];
			return {
				...s,
				loading: false,
				currentPath: path,
				entries: response.data!.entries,
				history: newHistory,
				historyIndex: newHistory.length - 1
			};
		});
	}
}

/**
 * Refresh current directory
 */
export async function refresh(): Promise<void> {
	const state = get(fileBrowserState);

	if (!state.clientUuid) return;

	fileBrowserState.update((s) => ({ ...s, loading: true, error: null }));

	const response = await api.listFiles(state.clientUuid, state.currentPath);

	if (response.error) {
		fileBrowserState.update((s) => ({
			...s,
			loading: false,
			error: response.error
		}));
		return;
	}

	if (response.data) {
		fileBrowserState.update((s) => ({
			...s,
			loading: false,
			entries: response.data!.entries
		}));
	}
}

/**
 * Go up one directory
 */
export async function goUp(): Promise<void> {
	const state = get(fileBrowserState);

	if (!state.clientUuid || state.currentPath === '/') return;

	const parentPath = state.currentPath.split('/').slice(0, -1).join('/') || '/';
	await navigateTo(state.clientUuid, parentPath);
}

/**
 * Go back in history
 */
export async function goBack(): Promise<void> {
	const state = get(fileBrowserState);

	if (!state.clientUuid || state.historyIndex <= 0) return;

	const newIndex = state.historyIndex - 1;
	const path = state.history[newIndex];

	fileBrowserState.update((s) => ({
		...s,
		loading: true,
		error: null,
		selectedFile: null,
		preview: null
	}));

	const response = await api.listFiles(state.clientUuid, path);

	if (response.error) {
		fileBrowserState.update((s) => ({
			...s,
			loading: false,
			error: response.error
		}));
		return;
	}

	if (response.data) {
		fileBrowserState.update((s) => ({
			...s,
			loading: false,
			currentPath: path,
			entries: response.data!.entries,
			historyIndex: newIndex
		}));
	}
}

/**
 * Go forward in history
 */
export async function goForward(): Promise<void> {
	const state = get(fileBrowserState);

	if (!state.clientUuid || state.historyIndex >= state.history.length - 1) return;

	const newIndex = state.historyIndex + 1;
	const path = state.history[newIndex];

	fileBrowserState.update((s) => ({
		...s,
		loading: true,
		error: null,
		selectedFile: null,
		preview: null
	}));

	const response = await api.listFiles(state.clientUuid, path);

	if (response.error) {
		fileBrowserState.update((s) => ({
			...s,
			loading: false,
			error: response.error
		}));
		return;
	}

	if (response.data) {
		fileBrowserState.update((s) => ({
			...s,
			loading: false,
			currentPath: path,
			entries: response.data!.entries,
			historyIndex: newIndex
		}));
	}
}

/**
 * Select a file
 */
export function selectFile(file: FileEntry | null): void {
	fileBrowserState.update((s) => ({
		...s,
		selectedFile: file,
		preview: null,
		previewError: null
	}));
}

/**
 * Load file preview
 */
export async function loadPreview(clientUuid: string, path: string): Promise<void> {
	fileBrowserState.update((s) => ({
		...s,
		previewLoading: true,
		previewError: null,
		preview: null
	}));

	const response = await api.previewFile(clientUuid, path);

	if (response.error) {
		fileBrowserState.update((s) => ({
			...s,
			previewLoading: false,
			previewError: response.error
		}));
		return;
	}

	if (response.data) {
		fileBrowserState.update((s) => ({
			...s,
			previewLoading: false,
			preview: response.data
		}));
	}
}

/**
 * Download selected file
 */
export function downloadSelected(): void {
	const state = get(fileBrowserState);

	if (!state.clientUuid || !state.selectedFile) return;
	if (state.selectedFile.type === 'dir') return;

	const filePath =
		state.currentPath === '/'
			? `/${state.selectedFile.name}`
			: `${state.currentPath}/${state.selectedFile.name}`;

	api.downloadFile(state.clientUuid, filePath);
}

/**
 * Upload a file
 */
export async function uploadFile(file: File, destPath?: string): Promise<boolean> {
	const state = get(fileBrowserState);

	if (!state.clientUuid) return false;

	const targetPath = destPath ?? `${state.currentPath}/${file.name}`.replace(/\/+/g, '/');

	fileBrowserState.update((s) => ({
		...s,
		uploading: true,
		uploadProgress: {
			filename: file.name,
			loaded: 0,
			total: file.size,
			percent: 0
		}
	}));

	const response = await api.uploadFile(state.clientUuid, file, targetPath, (percent) => {
		fileBrowserState.update((s) => ({
			...s,
			uploadProgress: s.uploadProgress
				? {
						...s.uploadProgress,
						percent
					}
				: null
		}));
	});

	fileBrowserState.update((s) => ({
		...s,
		uploading: false,
		uploadProgress: null
	}));

	if (response.error) {
		fileBrowserState.update((s) => ({
			...s,
			error: response.error
		}));
		return false;
	}

	// Refresh to show new file
	await refresh();
	return true;
}

/**
 * Set sort options
 */
export function setSort(field: SortField, dir?: SortDirection): void {
	fileBrowserState.update((s) => ({
		...s,
		sortBy: field,
		sortDir: dir ?? (s.sortBy === field && s.sortDir === 'asc' ? 'desc' : 'asc')
	}));
}

/**
 * Clear browser state
 */
export function clearBrowser(): void {
	fileBrowserState.set(initialState);
}

// -----------------------------------------------------------------------------
// Utility Functions
// -----------------------------------------------------------------------------

/**
 * Format file size in human-readable format
 */
export function formatSize(bytes: number): string {
	if (bytes === 0) return '0 B';
	const k = 1024;
	const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
	const i = Math.floor(Math.log(bytes) / Math.log(k));
	return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}

/**
 * Format modified date
 * Handles both Unix timestamps (seconds since epoch) and ISO strings
 */
export function formatModified(modified: string | number): string {
	let date: Date;

	if (typeof modified === 'number') {
		// Unix timestamp (seconds) - convert to milliseconds
		date = new Date(modified * 1000);
	} else if (typeof modified === 'string' && !isNaN(Number(modified))) {
		// String that looks like a Unix timestamp
		date = new Date(Number(modified) * 1000);
	} else {
		// ISO string or other date format
		date = new Date(modified);
	}

	// Check for invalid date
	if (isNaN(date.getTime())) {
		return 'Unknown';
	}

	const now = new Date();
	const diff = now.getTime() - date.getTime();

	// Less than a day
	if (diff < 86400000) {
		return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
	}

	// Less than a week
	if (diff < 604800000) {
		return date.toLocaleDateString([], { weekday: 'short', hour: '2-digit', minute: '2-digit' });
	}

	// Older
	return date.toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' });
}

/**
 * Get file icon based on type/extension
 */
export function getFileIcon(entry: FileEntry): string {
	if (entry.type === 'dir') return 'folder';
	if (entry.type === 'symlink') return 'link';

	const name = entry.name.toLowerCase();

	// Handle dotfiles - they're usually config files
	if (name.startsWith('.')) {
		// Check for shell config files
		if (
			name.includes('rc') ||
			name.includes('profile') ||
			name.includes('aliases') ||
			name.includes('logout')
		) {
			return 'file-code';
		}
		// Check for git-related files
		if (name.startsWith('.git')) {
			return 'file-config';
		}
		// Check for environment files
		if (name.startsWith('.env')) {
			return 'file-config';
		}
		// Default dotfiles to config icon
		return 'file-config';
	}

	const ext = name.split('.').pop()?.toLowerCase();
	switch (ext) {
		case 'txt':
		case 'md':
		case 'log':
			return 'file-text';
		case 'js':
		case 'ts':
		case 'py':
		case 'sh':
		case 'rs':
		case 'go':
			return 'file-code';
		case 'json':
		case 'yaml':
		case 'yml':
		case 'xml':
		case 'toml':
			return 'file-config';
		case 'jpg':
		case 'jpeg':
		case 'png':
		case 'gif':
		case 'svg':
		case 'webp':
			return 'file-image';
		case 'mp3':
		case 'wav':
		case 'ogg':
		case 'flac':
			return 'file-audio';
		case 'mp4':
		case 'webm':
		case 'mkv':
		case 'avi':
			return 'file-video';
		case 'zip':
		case 'tar':
		case 'gz':
		case 'xz':
		case '7z':
		case 'rar':
			return 'file-archive';
		case 'pdf':
			return 'file-pdf';
		default:
			return 'file';
	}
}

/**
 * Common dotfiles that are previewable text/config files
 */
const PREVIEWABLE_DOTFILES = [
	'.bashrc',
	'.bash_profile',
	'.bash_aliases',
	'.bash_logout',
	'.profile',
	'.zshrc',
	'.zprofile',
	'.zshenv',
	'.zlogout',
	'.vimrc',
	'.gvimrc',
	'.exrc',
	'.inputrc',
	'.screenrc',
	'.tmux.conf',
	'.gitconfig',
	'.gitignore',
	'.gitattributes',
	'.gitmodules',
	'.hgrc',
	'.hgignore',
	'.npmrc',
	'.yarnrc',
	'.nvmrc',
	'.prettierrc',
	'.eslintrc',
	'.editorconfig',
	'.dockerignore',
	'.env',
	'.env.local',
	'.env.example',
	'.htaccess',
	'.htpasswd',
	'.curlrc',
	'.wgetrc',
	'.netrc',
	'.ssh/config',
	'.gnupg/gpg.conf',
	'.config',
	'.xinitrc',
	'.Xresources',
	'.xsession',
	'.pam_environment',
	'.mailrc',
	'.muttrc',
	'.crontab',
	'.selected_editor'
];

/**
 * Check if file is previewable
 */
export function isPreviewable(entry: FileEntry): boolean {
	if (entry.type !== 'file') return false;
	if (entry.size > 1024 * 1024) return false; // 1MB limit

	const name = entry.name.toLowerCase();

	// Check if it's a known dotfile
	if (name.startsWith('.')) {
		// Check exact match first
		if (PREVIEWABLE_DOTFILES.includes(name)) {
			return true;
		}
		// Check if it's a dotfile with a previewable extension (e.g., .env.local)
		const parts = name.split('.');
		if (parts.length > 2) {
			const ext = parts.pop();
			if (ext && previewableExts.includes(ext)) {
				return true;
			}
		}
		// Generic dotfiles without extension are usually config files
		if (parts.length === 2 && parts[0] === '') {
			return true; // .bashrc, .vimrc, etc.
		}
	}

	const ext = name.split('.').pop()?.toLowerCase();
	return previewableExts.includes(ext ?? '');
}

const previewableExts = [
	'txt',
	'md',
	'log',
	'js',
	'ts',
	'py',
	'sh',
	'rs',
	'go',
	'json',
	'yaml',
	'yml',
	'xml',
	'toml',
	'html',
	'css',
	'scss',
	'svelte',
	'vue',
	'jsx',
	'tsx',
	'c',
	'cpp',
	'h',
	'java',
	'rb',
	'php',
	'sql',
	'env',
	'gitignore',
	'dockerfile',
	'makefile',
	'ini',
	'conf',
	'cfg'
];
