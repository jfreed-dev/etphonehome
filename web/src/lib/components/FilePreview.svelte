<script lang="ts">
	import type { FilePreview, FileEntry } from '$types';
	import { formatSize } from '$stores/fileBrowser';

	interface Props {
		file: FileEntry;
		preview: FilePreview | null;
		loading: boolean;
		error: string | null;
		onDownload: () => void;
		onClose: () => void;
	}

	let { file, preview, loading, error, onDownload, onClose }: Props = $props();

	function getLanguageClass(mimeType: string): string {
		const map: Record<string, string> = {
			'text/x-python': 'python',
			'text/javascript': 'javascript',
			'text/typescript': 'typescript',
			'application/json': 'json',
			'text/yaml': 'yaml',
			'text/xml': 'xml',
			'text/html': 'html',
			'text/css': 'css',
			'text/x-shellscript': 'bash',
			'text/markdown': 'markdown'
		};
		return map[mimeType] || 'plaintext';
	}
</script>

<div class="file-preview">
	<div class="file-preview__header">
		<div class="file-preview__info">
			<h3 class="file-preview__name">{file.name}</h3>
			<span class="file-preview__size">{formatSize(file.size)}</span>
		</div>
		<div class="file-preview__actions">
			<button class="file-preview__btn" onclick={onDownload}>Download</button>
			<button class="file-preview__btn file-preview__btn--close" onclick={onClose}>Close</button>
		</div>
	</div>

	<div class="file-preview__content">
		{#if loading}
			<div class="file-preview__loading">Loading preview...</div>
		{:else if error}
			<div class="file-preview__error">{error}</div>
		{:else if preview?.binary}
			<div class="file-preview__binary">
				<p>Binary file - cannot preview</p>
				<p class="file-preview__binary-size">{formatSize(preview.size)}</p>
				<button class="file-preview__download-btn" onclick={onDownload}>Download File</button>
			</div>
		{:else if preview?.content}
			<pre class="file-preview__code language-{getLanguageClass(preview.mimeType)}">{preview.content}</pre>
		{:else}
			<div class="file-preview__empty">No preview available</div>
		{/if}
	</div>
</div>

<style lang="scss">
	.file-preview {
		@include panel;
		display: flex;
		flex-direction: column;
		height: 100%;
		min-height: 300px;

		&__header {
			@include flex-between;
			padding: $spacing-md;
			border-bottom: 1px solid $border-color;
			flex-shrink: 0;
		}

		&__info {
			display: flex;
			align-items: baseline;
			gap: $spacing-md;
			min-width: 0;
		}

		&__name {
			font-size: $font-size-base;
			font-weight: $font-weight-semibold;
			color: $text-100;
			margin: 0;
			@include text-truncate;
		}

		&__size {
			font-size: $font-size-sm;
			color: $text-400;
			flex-shrink: 0;
		}

		&__actions {
			@include flex-start;
			gap: $spacing-sm;
			flex-shrink: 0;
		}

		&__btn {
			padding: $spacing-xs $spacing-md;
			background: $bg-600;
			border: 1px solid $border-color;
			border-radius: $radius-sm;
			color: $text-200;
			font-size: $font-size-sm;
			cursor: pointer;
			transition: all 0.15s ease;

			&:hover {
				background: $bg-500;
				border-color: $text-400;
				color: $text-100;
			}

			&--close {
				background: transparent;
			}
		}

		&__content {
			flex: 1;
			overflow: auto;
			@include custom-scrollbar;
		}

		&__loading,
		&__error,
		&__empty,
		&__binary {
			display: flex;
			flex-direction: column;
			align-items: center;
			justify-content: center;
			height: 100%;
			min-height: 200px;
			color: $text-400;
			text-align: center;
		}

		&__error {
			color: $accent-red;
		}

		&__binary-size {
			font-size: $font-size-sm;
			margin-top: $spacing-xs;
		}

		&__download-btn {
			@include button-primary;
			margin-top: $spacing-md;
		}

		&__code {
			margin: 0;
			padding: $spacing-md;
			font-family: $font-family-mono;
			font-size: $font-size-xs;
			line-height: 1.5;
			color: $text-200;
			white-space: pre-wrap;
			word-break: break-all;
			background: $bg-900;
		}
	}
</style>
