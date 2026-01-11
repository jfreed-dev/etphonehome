<script lang="ts">
	import { onMount } from 'svelte';
	import {
		fileBrowserState,
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
		isPreviewable,
		type SortField
	} from '$stores/fileBrowser';
	import type { FileEntry } from '$types';
	import Breadcrumb from './Breadcrumb.svelte';
	import FileList from './FileList.svelte';
	import FilePreview from './FilePreview.svelte';

	interface Props {
		clientUuid: string;
		initialPath?: string;
	}

	let { clientUuid, initialPath = '/' }: Props = $props();

	let isDragging = $state(false);
	let dropZoneRef: HTMLDivElement;

	onMount(() => {
		navigateTo(clientUuid, initialPath);
	});

	function handleNavigate(path: string) {
		navigateTo(clientUuid, path);
	}

	function handleSelect(entry: FileEntry) {
		selectFile(entry);
		if (entry.type === 'file' && isPreviewable(entry)) {
			const filePath =
				$fileBrowserState.currentPath === '/'
					? `/${entry.name}`
					: `${$fileBrowserState.currentPath}/${entry.name}`;
			loadPreview(clientUuid, filePath);
		}
	}

	function handleOpen(entry: FileEntry) {
		if (entry.type === 'dir') {
			const newPath =
				$fileBrowserState.currentPath === '/'
					? `/${entry.name}`
					: `${$fileBrowserState.currentPath}/${entry.name}`;
			navigateTo(clientUuid, newPath);
		} else {
			handleSelect(entry);
		}
	}

	function handleSort(field: SortField) {
		setSort(field);
	}

	function handleClosePreview() {
		selectFile(null);
	}

	// Drag and drop handlers
	function handleDragEnter(event: DragEvent) {
		event.preventDefault();
		isDragging = true;
	}

	function handleDragOver(event: DragEvent) {
		event.preventDefault();
		isDragging = true;
	}

	function handleDragLeave(event: DragEvent) {
		event.preventDefault();
		// Only set isDragging to false if leaving the drop zone entirely
		if (event.relatedTarget && !dropZoneRef.contains(event.relatedTarget as Node)) {
			isDragging = false;
		}
	}

	async function handleDrop(event: DragEvent) {
		event.preventDefault();
		isDragging = false;

		const files = event.dataTransfer?.files;
		if (!files || files.length === 0) return;

		// Upload each file
		for (const file of Array.from(files)) {
			await uploadFile(file);
		}
	}

	async function handleFileInput(event: Event) {
		const input = event.target as HTMLInputElement;
		const files = input.files;
		if (!files || files.length === 0) return;

		for (const file of Array.from(files)) {
			await uploadFile(file);
		}

		// Reset input
		input.value = '';
	}
</script>

<div
	class="file-browser"
	class:file-browser--dragging={isDragging}
	bind:this={dropZoneRef}
	ondragenter={handleDragEnter}
	ondragover={handleDragOver}
	ondragleave={handleDragLeave}
	ondrop={handleDrop}
	role="region"
	aria-label="File browser"
>
	<!-- Toolbar -->
	<div class="file-browser__toolbar">
		<div class="file-browser__nav">
			<button
				class="file-browser__nav-btn"
				onclick={() => goBack()}
				disabled={!$canGoBack}
				title="Back"
			>
				←
			</button>
			<button
				class="file-browser__nav-btn"
				onclick={() => goForward()}
				disabled={!$canGoForward}
				title="Forward"
			>
				→
			</button>
			<button
				class="file-browser__nav-btn"
				onclick={() => goUp()}
				disabled={$fileBrowserState.currentPath === '/'}
				title="Up"
			>
				↑
			</button>
			<button class="file-browser__nav-btn" onclick={() => refresh()} title="Refresh">⟳</button>
		</div>

		<div class="file-browser__breadcrumb">
			<Breadcrumb segments={$pathSegments} onNavigate={handleNavigate} />
		</div>

		<div class="file-browser__actions">
			<label class="file-browser__upload-btn">
				<input type="file" multiple onchange={handleFileInput} />
				Upload
			</label>
			{#if $fileBrowserState.selectedFile && $fileBrowserState.selectedFile.type === 'file'}
				<button class="file-browser__action-btn" onclick={downloadSelected}>Download</button>
			{/if}
		</div>
	</div>

	<!-- Error -->
	{#if $fileBrowserState.error}
		<div class="file-browser__error">
			{$fileBrowserState.error}
		</div>
	{/if}

	<!-- Upload Progress -->
	{#if $fileBrowserState.uploading && $fileBrowserState.uploadProgress}
		<div class="file-browser__upload-progress">
			<span>Uploading {$fileBrowserState.uploadProgress.filename}...</span>
			<div class="file-browser__progress-bar">
				<div
					class="file-browser__progress-fill"
					style="width: {$fileBrowserState.uploadProgress.percent}%"
				></div>
			</div>
			<span>{$fileBrowserState.uploadProgress.percent}%</span>
		</div>
	{/if}

	<!-- Main Content -->
	<div class="file-browser__content">
		<div class="file-browser__list-container">
			<FileList
				entries={$sortedEntries}
				loading={$fileBrowserState.loading}
				selectedFile={$fileBrowserState.selectedFile}
				sortBy={$fileBrowserState.sortBy}
				sortDir={$fileBrowserState.sortDir}
				onSelect={handleSelect}
				onOpen={handleOpen}
				onSort={handleSort}
			/>
		</div>

		{#if $fileBrowserState.selectedFile && $fileBrowserState.selectedFile.type === 'file'}
			<div class="file-browser__preview-container">
				<FilePreview
					file={$fileBrowserState.selectedFile}
					preview={$fileBrowserState.preview}
					loading={$fileBrowserState.previewLoading}
					error={$fileBrowserState.previewError}
					onDownload={downloadSelected}
					onClose={handleClosePreview}
				/>
			</div>
		{/if}
	</div>

	<!-- Drag overlay -->
	{#if isDragging}
		<div class="file-browser__drop-overlay">
			<div class="file-browser__drop-message">
				<span class="file-browser__drop-icon">📁</span>
				<span>Drop files to upload</span>
			</div>
		</div>
	{/if}
</div>

<style lang="scss">
	.file-browser {
		display: flex;
		flex-direction: column;
		gap: $spacing-md;
		position: relative;

		&--dragging {
			.file-browser__content {
				opacity: 0.5;
			}
		}

		&__toolbar {
			@include flex-between;
			gap: $spacing-md;
			flex-wrap: wrap;
		}

		&__nav {
			@include flex-start;
			gap: $spacing-xs;
		}

		&__nav-btn {
			width: 32px;
			height: 32px;
			display: flex;
			align-items: center;
			justify-content: center;
			background: $bg-700;
			border: 1px solid $border-color;
			border-radius: $radius-sm;
			color: $text-200;
			cursor: pointer;
			transition: all 0.15s ease;

			&:hover:not(:disabled) {
				background: $bg-600;
				border-color: $text-400;
				color: $text-100;
			}

			&:disabled {
				opacity: 0.4;
				cursor: not-allowed;
			}
		}

		&__breadcrumb {
			flex: 1;
			min-width: 0;
		}

		&__actions {
			@include flex-start;
			gap: $spacing-sm;
		}

		&__upload-btn {
			@include button-primary;
			padding: $spacing-xs $spacing-md;
			cursor: pointer;

			input {
				display: none;
			}
		}

		&__action-btn {
			padding: $spacing-xs $spacing-md;
			background: $bg-600;
			border: 1px solid $border-color;
			border-radius: $radius-md;
			color: $text-200;
			font-size: $font-size-sm;
			cursor: pointer;
			transition: all 0.15s ease;

			&:hover {
				background: $bg-500;
				border-color: $text-400;
				color: $text-100;
			}
		}

		&__error {
			padding: $spacing-md;
			background: rgba($accent-red, 0.1);
			border: 1px solid rgba($accent-red, 0.3);
			border-radius: $radius-md;
			color: $accent-red;
			font-size: $font-size-sm;
		}

		&__upload-progress {
			@include flex-start;
			gap: $spacing-md;
			padding: $spacing-sm $spacing-md;
			background: rgba($accent-cyan, 0.1);
			border: 1px solid rgba($accent-cyan, 0.3);
			border-radius: $radius-md;
			font-size: $font-size-sm;
			color: $text-200;
		}

		&__progress-bar {
			flex: 1;
			height: 4px;
			background: $bg-700;
			border-radius: 2px;
			overflow: hidden;
		}

		&__progress-fill {
			height: 100%;
			background: $accent-cyan;
			transition: width 0.2s ease;
		}

		&__content {
			display: grid;
			grid-template-columns: 1fr;
			gap: $spacing-md;

			@include lg {
				grid-template-columns: 1fr 1fr;
			}
		}

		&__list-container {
			min-width: 0;
		}

		&__preview-container {
			min-width: 0;
		}

		&__drop-overlay {
			position: absolute;
			inset: 0;
			display: flex;
			align-items: center;
			justify-content: center;
			background: rgba($bg-900, 0.9);
			border: 2px dashed $accent-cyan;
			border-radius: $radius-lg;
			z-index: 10;
		}

		&__drop-message {
			display: flex;
			flex-direction: column;
			align-items: center;
			gap: $spacing-md;
			color: $accent-cyan;
			font-size: $font-size-lg;
		}

		&__drop-icon {
			font-size: 48px;
		}
	}
</style>
