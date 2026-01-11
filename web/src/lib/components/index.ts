// =============================================================================
// ET Phone Home - Component Exports
// =============================================================================

export { default as Header } from './Header.svelte';
export { default as ClientCard } from './ClientCard.svelte';
export { default as ActivityStream } from './ActivityStream.svelte';
export { default as StatsCard } from './StatsCard.svelte';
export { default as LoginForm } from './LoginForm.svelte';

// Phase 3 Components
export { default as CommandHistory } from './CommandHistory.svelte';
export { default as FileBrowser } from './FileBrowser.svelte';
export { default as FileList } from './FileList.svelte';
export { default as FilePreview } from './FilePreview.svelte';
export { default as Breadcrumb } from './Breadcrumb.svelte';

// Terminal components use browser-only xterm.js - import directly where needed
// import Terminal from '$lib/components/Terminal.svelte';
// import TerminalTabs from '$lib/components/TerminalTabs.svelte';
