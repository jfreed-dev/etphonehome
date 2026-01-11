<script lang="ts">
	import { onMount } from 'svelte';
	import {
		commandHistoryState,
		loadHistory,
		searchHistory,
		filterByStatus,
		runCommand,
		rerunCommand,
		formatDuration,
		formatTimestamp,
		getStatusClass,
		type StatusFilter
	} from '$stores/commandHistory';
	import type { CommandRecord } from '$types';

	interface Props {
		clientUuid: string;
	}

	let { clientUuid }: Props = $props();

	let searchQuery = $state('');
	let statusFilter = $state<StatusFilter>('all');
	let commandInput = $state('');
	let cwdInput = $state('');
	let expandedId = $state<string | null>(null);

	onMount(() => {
		loadHistory(clientUuid);
	});

	async function handleSearch() {
		await searchHistory(searchQuery);
	}

	async function handleStatusFilter(event: Event) {
		const select = event.target as HTMLSelectElement;
		statusFilter = select.value as StatusFilter;
		await filterByStatus(statusFilter);
	}

	async function handleRunCommand(event: Event) {
		event.preventDefault();
		if (!commandInput.trim()) return;

		await runCommand(clientUuid, commandInput.trim(), cwdInput.trim() || undefined);
		commandInput = '';
	}

	async function handleRerun(record: CommandRecord) {
		await rerunCommand(record);
	}

	function toggleExpand(id: string) {
		expandedId = expandedId === id ? null : id;
	}

	function copyToClipboard(text: string) {
		navigator.clipboard.writeText(text);
	}
</script>

<div class="command-history">
	<!-- Command Input -->
	<form class="command-input" onsubmit={handleRunCommand}>
		<div class="command-input__row">
			<input
				type="text"
				class="command-input__field"
				placeholder="Enter command..."
				bind:value={commandInput}
				disabled={$commandHistoryState.runningCommand}
			/>
			<button
				type="submit"
				class="command-input__btn"
				disabled={$commandHistoryState.runningCommand || !commandInput.trim()}
			>
				{$commandHistoryState.runningCommand ? 'Running...' : 'Run'}
			</button>
		</div>
		<div class="command-input__cwd">
			<label>
				<span>Working Directory:</span>
				<input type="text" placeholder="/" bind:value={cwdInput} />
			</label>
		</div>
	</form>

	<!-- Toolbar -->
	<div class="command-history__toolbar">
		<div class="command-history__search">
			<input
				type="search"
				placeholder="Search commands..."
				bind:value={searchQuery}
				oninput={handleSearch}
			/>
		</div>
		<div class="command-history__filters">
			<select value={statusFilter} onchange={handleStatusFilter}>
				<option value="all">All</option>
				<option value="success">Success</option>
				<option value="failed">Failed</option>
			</select>
			<span class="command-history__count">
				{$commandHistoryState.total} command{$commandHistoryState.total !== 1 ? 's' : ''}
			</span>
		</div>
	</div>

	<!-- Error Message -->
	{#if $commandHistoryState.error}
		<div class="command-history__error">
			{$commandHistoryState.error}
		</div>
	{/if}

	<!-- Loading -->
	{#if $commandHistoryState.loading && $commandHistoryState.commands.length === 0}
		<div class="command-history__loading">Loading history...</div>
	{/if}

	<!-- Command List -->
	<div class="command-history__list">
		{#each $commandHistoryState.commands as record (record.id)}
			<div class="command-item" class:command-item--failed={record.returncode !== 0}>
				<button class="command-item__header" onclick={() => toggleExpand(record.id)}>
					<div class="command-item__status">
						<span
							class="command-item__status-dot"
							class:command-item__status-dot--success={record.returncode === 0}
							class:command-item__status-dot--failed={record.returncode !== 0}
						></span>
					</div>
					<code class="command-item__cmd">{record.command}</code>
					<div class="command-item__meta">
						<span class="command-item__duration">{formatDuration(record.duration_ms)}</span>
						<span class="command-item__time">{formatTimestamp(record.completed_at)}</span>
						<span class="command-item__expand">{expandedId === record.id ? '−' : '+'}</span>
					</div>
				</button>

				{#if expandedId === record.id}
					<div class="command-item__details">
						{#if record.cwd}
							<div class="command-item__cwd">
								<span class="label">CWD:</span>
								<code>{record.cwd}</code>
							</div>
						{/if}

						{#if record.stdout}
							<div class="command-item__output">
								<span class="label">stdout:</span>
								<pre>{record.stdout}</pre>
							</div>
						{/if}

						{#if record.stderr}
							<div class="command-item__output command-item__output--stderr">
								<span class="label">stderr:</span>
								<pre>{record.stderr}</pre>
							</div>
						{/if}

						<div class="command-item__info">
							<span>Exit code: {record.returncode}</span>
							<span>Duration: {formatDuration(record.duration_ms)}</span>
							<span>User: {record.user}</span>
						</div>

						<div class="command-item__actions">
							<button class="btn btn--ghost" onclick={() => handleRerun(record)}>Re-run</button>
							<button class="btn btn--ghost" onclick={() => copyToClipboard(record.command)}
								>Copy</button
							>
							{#if record.stdout}
								<button class="btn btn--ghost" onclick={() => copyToClipboard(record.stdout)}
									>Copy Output</button
								>
							{/if}
						</div>
					</div>
				{/if}
			</div>
		{/each}
	</div>

	<!-- Empty State -->
	{#if !$commandHistoryState.loading && $commandHistoryState.commands.length === 0}
		<div class="command-history__empty">
			<p>No commands in history</p>
			<p class="command-history__empty-hint">Run a command above to get started</p>
		</div>
	{/if}
</div>

<style lang="scss">
	.command-history {
		display: flex;
		flex-direction: column;
		gap: $spacing-md;

		&__toolbar {
			@include flex-between;
			gap: $spacing-md;
		}

		&__search {
			flex: 1;

			input {
				width: 100%;
				padding: $spacing-sm $spacing-md;
				background: $bg-700;
				border: 1px solid $border-color;
				border-radius: $radius-md;
				color: $text-100;
				font-size: $font-size-sm;

				&::placeholder {
					color: $text-400;
				}

				&:focus {
					outline: none;
					border-color: $accent-cyan;
				}
			}
		}

		&__filters {
			@include flex-start;
			gap: $spacing-md;

			select {
				padding: $spacing-sm $spacing-md;
				background: $bg-700;
				border: 1px solid $border-color;
				border-radius: $radius-md;
				color: $text-100;
				font-size: $font-size-sm;

				&:focus {
					outline: none;
					border-color: $accent-cyan;
				}
			}
		}

		&__count {
			font-size: $font-size-sm;
			color: $text-400;
		}

		&__error {
			padding: $spacing-md;
			background: rgba($accent-red, 0.1);
			border: 1px solid rgba($accent-red, 0.3);
			border-radius: $radius-md;
			color: $accent-red;
			font-size: $font-size-sm;
		}

		&__loading,
		&__empty {
			padding: $spacing-xl;
			text-align: center;
			color: $text-400;
		}

		&__empty-hint {
			font-size: $font-size-sm;
			margin-top: $spacing-xs;
		}

		&__list {
			display: flex;
			flex-direction: column;
			gap: $spacing-sm;
		}
	}

	.command-input {
		@include panel;
		display: flex;
		flex-direction: column;
		gap: $spacing-sm;

		&__row {
			display: flex;
			gap: $spacing-sm;
		}

		&__field {
			flex: 1;
			padding: $spacing-sm $spacing-md;
			background: $bg-900;
			border: 1px solid $border-color;
			border-radius: $radius-md;
			color: $text-100;
			font-family: $font-family-mono;
			font-size: $font-size-sm;

			&::placeholder {
				color: $text-400;
			}

			&:focus {
				outline: none;
				border-color: $accent-cyan;
			}

			&:disabled {
				opacity: 0.5;
			}
		}

		&__btn {
			@include button-primary;
			padding: $spacing-sm $spacing-lg;

			&:disabled {
				opacity: 0.5;
				cursor: not-allowed;
			}
		}

		&__cwd {
			label {
				display: flex;
				align-items: center;
				gap: $spacing-sm;
				font-size: $font-size-xs;
				color: $text-400;

				input {
					flex: 1;
					padding: $spacing-xs $spacing-sm;
					background: $bg-900;
					border: 1px solid $border-color;
					border-radius: $radius-sm;
					color: $text-200;
					font-family: $font-family-mono;
					font-size: $font-size-xs;

					&::placeholder {
						color: $text-400;
					}

					&:focus {
						outline: none;
						border-color: $accent-cyan;
					}
				}
			}
		}
	}

	.command-item {
		@include panel;
		overflow: hidden;

		&--failed {
			border-color: rgba($accent-red, 0.3);
		}

		&__header {
			width: 100%;
			display: flex;
			align-items: center;
			gap: $spacing-md;
			padding: $spacing-sm;
			background: none;
			border: none;
			color: inherit;
			cursor: pointer;
			text-align: left;

			&:hover {
				background: rgba($text-100, 0.02);
			}
		}

		&__status {
			flex-shrink: 0;
		}

		&__status-dot {
			display: block;
			width: 8px;
			height: 8px;
			border-radius: 50%;
			background: $text-400;

			&--success {
				background: $accent-green;
			}

			&--failed {
				background: $accent-red;
			}
		}

		&__cmd {
			flex: 1;
			font-family: $font-family-mono;
			font-size: $font-size-sm;
			color: $text-100;
			@include text-truncate;
		}

		&__meta {
			@include flex-start;
			gap: $spacing-md;
			flex-shrink: 0;
		}

		&__duration,
		&__time {
			font-size: $font-size-xs;
			color: $text-400;
		}

		&__expand {
			width: 20px;
			text-align: center;
			font-size: $font-size-lg;
			color: $text-400;
		}

		&__details {
			padding: $spacing-md;
			border-top: 1px solid $border-color;
			background: $bg-900;
		}

		&__cwd {
			margin-bottom: $spacing-sm;
			font-size: $font-size-xs;

			.label {
				color: $text-400;
				margin-right: $spacing-xs;
			}

			code {
				color: $text-200;
				font-family: $font-family-mono;
			}
		}

		&__output {
			margin-bottom: $spacing-md;

			.label {
				display: block;
				font-size: $font-size-xs;
				color: $text-400;
				margin-bottom: $spacing-xs;
			}

			pre {
				padding: $spacing-sm;
				background: $bg-800;
				border-radius: $radius-sm;
				font-family: $font-family-mono;
				font-size: $font-size-xs;
				color: $text-200;
				white-space: pre-wrap;
				word-break: break-all;
				max-height: 300px;
				overflow-y: auto;
				@include custom-scrollbar;
			}

			&--stderr pre {
				color: $accent-red;
			}
		}

		&__info {
			@include flex-start;
			gap: $spacing-md;
			margin-bottom: $spacing-md;
			font-size: $font-size-xs;
			color: $text-400;
		}

		&__actions {
			@include flex-start;
			gap: $spacing-sm;
		}
	}

	.btn {
		padding: $spacing-xs $spacing-sm;
		border-radius: $radius-sm;
		font-size: $font-size-xs;
		cursor: pointer;
		transition: all 0.15s ease;

		&--ghost {
			background: transparent;
			border: 1px solid $border-color;
			color: $text-300;

			&:hover {
				background: rgba($text-100, 0.05);
				border-color: $text-400;
				color: $text-100;
			}
		}
	}
</style>
