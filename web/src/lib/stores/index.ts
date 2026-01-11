// =============================================================================
// ET Phone Home - Store Exports
// =============================================================================

// Auth store
export * from './auth';

// Clients store
export * from './clients';

// Connection store
export * from './connection';

// Dashboard store
export * from './dashboard';

// Events store
export * from './events';

// Command history store - rename isLoading to avoid conflict
export {
	commandHistoryState,
	commands,
	isLoading as isHistoryLoading,
	historyError,
	totalCommands,
	isRunningCommand,
	hasMore,
	successCount,
	failedCount,
	loadHistory,
	loadMore,
	searchHistory,
	filterByStatus,
	runCommand,
	rerunCommand,
	clearHistory,
	formatDuration,
	formatTimestamp,
	getStatusClass,
	type StatusFilter,
	type CommandHistoryState
} from './commandHistory';

// File browser store - rename isLoading to avoid conflict
export {
	fileBrowserState,
	currentPath,
	entries,
	isLoading as isBrowserLoading,
	browserError,
	selectedFile,
	preview,
	isPreviewLoading,
	isUploading,
	uploadProgress,
	sortedEntries,
	pathSegments,
	canGoBack,
	canGoForward,
	navigateTo,
	refresh,
	goUp,
	goBack,
	goForward,
	selectFile,
	loadPreview,
	downloadSelected,
	uploadFile,
	setSort,
	clearBrowser,
	formatSize,
	formatModified,
	getFileIcon,
	isPreviewable,
	type SortField,
	type SortDirection,
	type FileBrowserState
} from './fileBrowser';

// Terminal store - rename TerminalSession to avoid conflict with types
export {
	terminalState,
	sessions,
	activeSession,
	isExecuting,
	terminalError,
	sessionCount,
	createSession,
	closeSession,
	setActiveSession,
	executeCommand,
	getPreviousCommand,
	getNextCommand,
	resetHistoryIndex,
	clearTerminal,
	getSessionsForClient,
	type TerminalSession as TerminalSessionState,
	type TerminalHistoryEntry,
	type TerminalState
} from './terminal';
