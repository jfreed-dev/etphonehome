<script lang="ts">
	import type { FileEntry } from '$types';
	import { formatSize, formatModified, getFileIcon, type SortField } from '$stores/fileBrowser';

	interface Props {
		entries: FileEntry[];
		loading: boolean;
		selectedFile: FileEntry | null;
		sortBy: SortField;
		sortDir: 'asc' | 'desc';
		onSelect: (entry: FileEntry) => void;
		onOpen: (entry: FileEntry) => void;
		onSort: (field: SortField) => void;
	}

	let { entries, loading, selectedFile, sortBy, sortDir, onSelect, onOpen, onSort }: Props =
		$props();

	function getSortIndicator(field: SortField): string {
		if (sortBy !== field) return '';
		return sortDir === 'asc' ? ' ↑' : ' ↓';
	}

	function handleKeyDown(event: KeyboardEvent, entry: FileEntry) {
		if (event.key === 'Enter') {
			onOpen(entry);
		}
	}
</script>

<div class="file-list">
	<div class="file-list__header">
		<button class="file-list__col file-list__col--name" onclick={() => onSort('name')}>
			Name{getSortIndicator('name')}
		</button>
		<button class="file-list__col file-list__col--size" onclick={() => onSort('size')}>
			Size{getSortIndicator('size')}
		</button>
		<button class="file-list__col file-list__col--modified" onclick={() => onSort('modified')}>
			Modified{getSortIndicator('modified')}
		</button>
		<span class="file-list__col file-list__col--perms">Permissions</span>
	</div>

	{#if loading}
		<div class="file-list__loading">Loading...</div>
	{:else if entries.length === 0}
		<div class="file-list__empty">Directory is empty</div>
	{:else}
		<div class="file-list__body">
			{#each entries as entry (entry.name)}
				<div
					class="file-list__row"
					class:file-list__row--selected={selectedFile?.name === entry.name}
					class:file-list__row--dir={entry.type === 'dir'}
					role="button"
					tabindex="0"
					onclick={() => onSelect(entry)}
					ondblclick={() => onOpen(entry)}
					onkeydown={(e) => handleKeyDown(e, entry)}
				>
					<span class="file-list__col file-list__col--name">
						<span class="file-list__icon file-list__icon--{getFileIcon(entry)}"></span>
						<span class="file-list__name">{entry.name}</span>
						{#if entry.type === 'symlink' && entry.target}
							<span class="file-list__target">→ {entry.target}</span>
						{/if}
					</span>
					<span class="file-list__col file-list__col--size">
						{entry.type === 'dir' ? '—' : formatSize(entry.size)}
					</span>
					<span class="file-list__col file-list__col--modified">
						{formatModified(entry.modified)}
					</span>
					<span class="file-list__col file-list__col--perms">
						{entry.permissions}
					</span>
				</div>
			{/each}
		</div>
	{/if}
</div>

<style lang="scss">
	.file-list {
		@include panel;
		overflow: hidden;

		&__header {
			display: flex;
			padding: $spacing-sm $spacing-md;
			background: $bg-700;
			border-bottom: 1px solid $border-color;
			font-size: $font-size-xs;
			font-weight: $font-weight-medium;
			color: $text-300;
			text-transform: uppercase;
			letter-spacing: 0.5px;

			button {
				background: none;
				border: none;
				color: inherit;
				cursor: pointer;
				text-align: left;
				padding: 0;

				&:hover {
					color: $text-100;
				}
			}
		}

		&__body {
			max-height: 400px;
			overflow-y: auto;
			@include custom-scrollbar;
		}

		&__row {
			display: flex;
			padding: $spacing-sm $spacing-md;
			border-bottom: 1px solid rgba($border-color, 0.5);
			cursor: pointer;
			transition: background 0.1s ease;

			&:hover {
				background: rgba($text-100, 0.02);
			}

			&--selected {
				background: rgba($accent-cyan, 0.08);

				&:hover {
					background: rgba($accent-cyan, 0.12);
				}
			}

			&--dir {
				.file-list__name {
					color: $accent-cyan;
				}
			}

			&:last-child {
				border-bottom: none;
			}
		}

		&__col {
			font-size: $font-size-sm;

			&--name {
				flex: 1;
				display: flex;
				align-items: center;
				gap: $spacing-sm;
				min-width: 0;
			}

			&--size {
				width: 80px;
				text-align: right;
				color: $text-400;
			}

			&--modified {
				width: 140px;
				color: $text-400;
			}

			&--perms {
				width: 100px;
				font-family: $font-family-mono;
				font-size: $font-size-xs;
				color: $text-400;
			}
		}

		&__icon {
			flex-shrink: 0;
			width: 16px;
			height: 16px;
			display: flex;
			align-items: center;
			justify-content: center;
			font-size: 12px;

			&::before {
				content: '📄';
			}

			&--folder::before {
				content: '📁';
			}
			&--link::before {
				content: '🔗';
			}
			&--file-text::before {
				content: '📄';
			}
			&--file-code::before {
				content: '📝';
			}
			&--file-config::before {
				content: '⚙️';
			}
			&--file-image::before {
				content: '🖼️';
			}
			&--file-audio::before {
				content: '🎵';
			}
			&--file-video::before {
				content: '🎬';
			}
			&--file-archive::before {
				content: '📦';
			}
			&--file-pdf::before {
				content: '📕';
			}
		}

		&__name {
			@include text-truncate;
			color: $text-100;
		}

		&__target {
			font-size: $font-size-xs;
			color: $text-400;
			margin-left: $spacing-xs;
		}

		&__loading,
		&__empty {
			padding: $spacing-xl;
			text-align: center;
			color: $text-400;
		}
	}
</style>
