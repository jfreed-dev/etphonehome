<script lang="ts">
	import type { Client } from '$types';

	interface Props {
		client: Client;
	}

	let { client }: Props = $props();

	function formatLastSeen(timestamp: string): string {
		const date = new Date(timestamp);
		const now = new Date();
		const diffMs = now.getTime() - date.getTime();
		const diffMins = Math.floor(diffMs / 60000);
		const diffHours = Math.floor(diffMs / 3600000);

		if (diffMins < 1) return 'just now';
		if (diffMins < 60) return `${diffMins}m ago`;
		if (diffHours < 24) return `${diffHours}h ago`;
		return date.toLocaleDateString();
	}
</script>

<a
	href="/client?uuid={client.uuid}"
	class="client-card"
	class:client-card--offline={!client.online}
>
	<div class="client-card__header">
		<div class="client-card__status" class:client-card__status--online={client.online}>
			<span class="client-card__status-dot"></span>
			<span>{client.online ? 'Online' : 'Offline'}</span>
		</div>
		{#if client.is_selected}
			<span class="client-card__selected">Selected</span>
		{/if}
	</div>

	<h3 class="client-card__name">{client.display_name}</h3>
	<p class="client-card__hostname">{client.hostname}</p>

	<div class="client-card__meta">
		<span class="client-card__platform">{client.platform}</span>
		{#if client.purpose}
			<span class="client-card__purpose">{client.purpose}</span>
		{/if}
	</div>

	{#if client.tags.length > 0}
		<div class="client-card__tags">
			{#each client.tags.slice(0, 3) as tag}
				<span class="client-card__tag">{tag}</span>
			{/each}
			{#if client.tags.length > 3}
				<span class="client-card__tag">+{client.tags.length - 3}</span>
			{/if}
		</div>
	{/if}

	<div class="client-card__footer">
		<span class="client-card__last-seen">
			{client.online ? 'Active now' : `Last seen ${formatLastSeen(client.last_seen)}`}
		</span>
	</div>
</a>

<style lang="scss">
	// Variables and mixins are auto-injected via vite.config.ts

	.client-card {
		@include panel;
		@include panel-hover;
		display: block;
		text-decoration: none;
		color: inherit;

		&--offline {
			opacity: 0.7;
		}

		&__header {
			@include flex-between;
			margin-bottom: $spacing-sm;
		}

		&__status {
			@include chip;
			background: rgba($accent-red, 0.12);
			color: $accent-red;

			&--online {
				background: rgba($accent-green, 0.12);
				color: $accent-green;
			}
		}

		&__status-dot {
			width: 6px;
			height: 6px;
			border-radius: 50%;
			background: currentColor;
		}

		&__selected {
			@include chip;
			background: rgba($accent-cyan, 0.12);
			color: $accent-cyan;
		}

		&__name {
			font-size: $font-size-lg;
			font-weight: $font-weight-semibold;
			color: $text-100;
			margin: 0 0 $spacing-xs;
			@include text-truncate;
		}

		&__hostname {
			font-size: $font-size-sm;
			color: $text-300;
			margin: 0 0 $spacing-md;
			font-family: $font-family-mono;
		}

		&__meta {
			@include flex-start;
			gap: $spacing-sm;
			margin-bottom: $spacing-sm;
		}

		&__platform,
		&__purpose {
			font-size: $font-size-xs;
			color: $text-400;
		}

		&__platform {
			&::after {
				content: '•';
				margin-left: $spacing-sm;
			}
		}

		&__tags {
			@include flex-start;
			flex-wrap: wrap;
			gap: $spacing-xs;
			margin-bottom: $spacing-md;
		}

		&__tag {
			@include chip-cyan;
			font-size: 10px;
			padding: 2px 6px;
		}

		&__footer {
			padding-top: $spacing-sm;
			border-top: 1px solid $border-color;
		}

		&__last-seen {
			font-size: $font-size-xs;
			color: $text-400;
		}
	}
</style>
