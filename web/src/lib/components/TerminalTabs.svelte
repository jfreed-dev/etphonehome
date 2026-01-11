<script lang="ts">
	import { onMount } from 'svelte';
	import Terminal from './Terminal.svelte';
	import {
		terminalState,
		createSession,
		closeSession,
		setActiveSession,
		getSessionsForClient
	} from '$stores/terminal';

	interface Props {
		clientUuid: string;
	}

	let { clientUuid }: Props = $props();

	// Filter sessions for this client
	let clientSessions = $derived($terminalState.sessions.filter((s) => s.clientUuid === clientUuid));
	let activeSession = $derived(clientSessions.find((s) => s.id === $terminalState.activeSessionId));

	onMount(() => {
		// Create initial session if none exist for this client
		if (getSessionsForClient(clientUuid).length === 0) {
			createSession(clientUuid);
		} else {
			// Set active to first session for this client if current active is different client
			const sessions = getSessionsForClient(clientUuid);
			if (sessions.length > 0 && !activeSession) {
				setActiveSession(sessions[0].id);
			}
		}
	});

	function handleNewSession() {
		createSession(clientUuid);
	}

	function handleCloseSession(sessionId: string, event: Event) {
		event.stopPropagation();
		closeSession(sessionId);
	}

	function handleSelectSession(sessionId: string) {
		setActiveSession(sessionId);
	}
</script>

<div class="terminal-tabs">
	<div class="terminal-tabs__header">
		<div class="terminal-tabs__list">
			{#each clientSessions as session (session.id)}
				<div
					class="terminal-tabs__tab"
					class:terminal-tabs__tab--active={$terminalState.activeSessionId === session.id}
					onclick={() => handleSelectSession(session.id)}
					onkeydown={(e) => e.key === 'Enter' && handleSelectSession(session.id)}
					role="tab"
					tabindex="0"
					aria-selected={$terminalState.activeSessionId === session.id}
				>
					<span class="terminal-tabs__tab-icon">⬢</span>
					<span class="terminal-tabs__tab-name">Terminal {session.index}</span>
					<button
						class="terminal-tabs__tab-close"
						onclick={(e) => handleCloseSession(session.id, e)}
						title="Close terminal"
					>
						×
					</button>
				</div>
			{/each}
		</div>
		<button class="terminal-tabs__new" onclick={handleNewSession} title="New terminal">
			<span>+</span>
		</button>
	</div>

	<div class="terminal-tabs__content">
		{#if activeSession}
			{#key activeSession.id}
				<Terminal session={activeSession} />
			{/key}
		{:else}
			<div class="terminal-tabs__empty">
				<p>No terminal session</p>
				<button class="terminal-tabs__empty-btn" onclick={handleNewSession}>Create Terminal</button>
			</div>
		{/if}
	</div>
</div>

<style lang="scss">
	.terminal-tabs {
		display: flex;
		flex-direction: column;
		height: 100%;
		min-height: 450px;

		&__header {
			@include flex-between;
			background: $bg-800;
			border-bottom: 1px solid $border-color;
			padding: 0 $spacing-xs;
		}

		&__list {
			display: flex;
			overflow-x: auto;
			@include custom-scrollbar;
		}

		&__tab {
			display: flex;
			align-items: center;
			gap: $spacing-xs;
			padding: $spacing-sm $spacing-md;
			background: transparent;
			border: none;
			border-bottom: 2px solid transparent;
			color: $text-400;
			font-size: $font-size-sm;
			cursor: pointer;
			white-space: nowrap;
			transition: all 0.15s ease;

			&:hover {
				background: rgba($text-100, 0.02);
				color: $text-200;
			}

			&--active {
				color: $accent-cyan;
				border-bottom-color: $accent-cyan;
				background: rgba($accent-cyan, 0.05);
			}
		}

		&__tab-icon {
			font-size: 10px;
		}

		&__tab-name {
			font-weight: $font-weight-medium;
		}

		&__tab-close {
			display: flex;
			align-items: center;
			justify-content: center;
			width: 16px;
			height: 16px;
			margin-left: $spacing-xs;
			padding: 0;
			background: transparent;
			border: none;
			border-radius: 50%;
			color: inherit;
			font-size: 14px;
			line-height: 1;
			cursor: pointer;
			opacity: 0.5;
			transition: all 0.15s ease;

			&:hover {
				opacity: 1;
				background: rgba($accent-red, 0.2);
				color: $accent-red;
			}
		}

		&__new {
			display: flex;
			align-items: center;
			justify-content: center;
			width: 32px;
			height: 32px;
			margin: $spacing-xs;
			padding: 0;
			background: $bg-700;
			border: 1px solid $border-color;
			border-radius: $radius-sm;
			color: $text-300;
			font-size: 18px;
			cursor: pointer;
			transition: all 0.15s ease;

			&:hover {
				background: $bg-600;
				border-color: $accent-cyan;
				color: $accent-cyan;
			}
		}

		&__content {
			flex: 1;
			min-height: 0;
		}

		&__empty {
			@include flex-center;
			flex-direction: column;
			gap: $spacing-md;
			height: 100%;
			min-height: 300px;
			color: $text-400;
		}

		&__empty-btn {
			@include button-primary;
		}
	}
</style>
