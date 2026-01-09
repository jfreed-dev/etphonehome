<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { page } from '$app/stores';
	import {
		clientDetail,
		clientDetailLoading,
		clientDetailError,
		fetchClientDetail,
		clearClientDetail
	} from '$stores/clients';

	let uuid = $derived($page.url.searchParams.get('uuid'));

	onMount(() => {
		if (uuid) {
			fetchClientDetail(uuid);
		}
	});

	onDestroy(() => {
		clearClientDetail();
	});

	$effect(() => {
		if (uuid) {
			fetchClientDetail(uuid);
		}
	});

	function formatDate(dateStr: string): string {
		return new Date(dateStr).toLocaleString();
	}

	function formatUptime(seconds: number): string {
		const days = Math.floor(seconds / 86400);
		const hours = Math.floor((seconds % 86400) / 3600);
		const mins = Math.floor((seconds % 3600) / 60);

		if (days > 0) return `${days}d ${hours}h`;
		if (hours > 0) return `${hours}h ${mins}m`;
		return `${mins}m`;
	}
</script>

<div class="client-detail et-container">
	<div class="client-detail__back">
		<a href="/" class="client-detail__back-link">← Back to Dashboard</a>
	</div>

	{#if $clientDetailLoading}
		<div class="client-detail__loading">
			<div class="et-skeleton et-skeleton--title"></div>
			<div class="et-skeleton et-skeleton--text"></div>
			<div class="et-skeleton et-skeleton--text"></div>
		</div>
	{:else if $clientDetailError}
		<div class="client-detail__error">
			<h2>Error Loading Client</h2>
			<p>{$clientDetailError}</p>
			<a href="/" class="et-btn et-btn--primary">Back to Dashboard</a>
		</div>
	{:else if $clientDetail}
		<div class="client-detail__header">
			<div class="client-detail__header-main">
				<div
					class="client-detail__status"
					class:client-detail__status--online={$clientDetail.online}
				>
					<span class="client-detail__status-dot"></span>
					<span>{$clientDetail.online ? 'Online' : 'Offline'}</span>
				</div>
				<h1 class="client-detail__name">{$clientDetail.display_name}</h1>
				<p class="client-detail__hostname">{$clientDetail.hostname}</p>
			</div>

			{#if $clientDetail.tags.length > 0}
				<div class="client-detail__tags">
					{#each $clientDetail.tags as tag}
						<span class="et-chip">{tag}</span>
					{/each}
				</div>
			{/if}
		</div>

		<div class="client-detail__content">
			<!-- Info Panel -->
			<section class="client-detail__panel">
				<h3 class="client-detail__panel-title">Client Information</h3>
				<dl class="client-detail__info-list">
					<div class="client-detail__info-item">
						<dt>UUID</dt>
						<dd><code>{$clientDetail.uuid}</code></dd>
					</div>
					<div class="client-detail__info-item">
						<dt>Platform</dt>
						<dd>{$clientDetail.platform}</dd>
					</div>
					<div class="client-detail__info-item">
						<dt>Purpose</dt>
						<dd>{$clientDetail.purpose || '—'}</dd>
					</div>
					<div class="client-detail__info-item">
						<dt>Client Version</dt>
						<dd>{$clientDetail.client_version}</dd>
					</div>
					<div class="client-detail__info-item">
						<dt>First Seen</dt>
						<dd>{formatDate($clientDetail.first_seen)}</dd>
					</div>
					<div class="client-detail__info-item">
						<dt>Last Seen</dt>
						<dd>{formatDate($clientDetail.last_seen)}</dd>
					</div>
				</dl>
			</section>

			<!-- Connection Panel -->
			<section class="client-detail__panel">
				<h3 class="client-detail__panel-title">Connection Details</h3>
				<dl class="client-detail__info-list">
					<div class="client-detail__info-item">
						<dt>Tunnel Port</dt>
						<dd>{$clientDetail.tunnel_port}</dd>
					</div>
					<div class="client-detail__info-item">
						<dt>SSH Key Fingerprint</dt>
						<dd><code>{$clientDetail.ssh_key_fingerprint}</code></dd>
					</div>
					{#if $clientDetail.key_mismatch}
						<div class="client-detail__info-item client-detail__info-item--warning">
							<dt>Status</dt>
							<dd>⚠️ Key Mismatch - verification required</dd>
						</div>
					{/if}
				</dl>
			</section>

			<!-- Capabilities Panel -->
			{#if $clientDetail.capabilities.length > 0}
				<section class="client-detail__panel">
					<h3 class="client-detail__panel-title">Capabilities</h3>
					<div class="client-detail__capabilities">
						{#each $clientDetail.capabilities as cap}
							<span class="et-chip et-chip--green">{cap}</span>
						{/each}
					</div>
				</section>
			{/if}

			<!-- Rate Limits Panel -->
			<section class="client-detail__panel">
				<h3 class="client-detail__panel-title">Rate Limits</h3>
				<dl class="client-detail__info-list">
					<div class="client-detail__info-item">
						<dt>Requests/Minute</dt>
						<dd>{$clientDetail.rate_limit_rpm ?? 'Default'}</dd>
					</div>
					<div class="client-detail__info-item">
						<dt>Concurrent Requests</dt>
						<dd>{$clientDetail.rate_limit_concurrent ?? 'Default'}</dd>
					</div>
				</dl>
			</section>

			<!-- Allowed Paths Panel -->
			{#if $clientDetail.allowed_paths}
				<section class="client-detail__panel">
					<h3 class="client-detail__panel-title">Allowed Paths</h3>
					<ul class="client-detail__paths">
						{#each $clientDetail.allowed_paths as path}
							<li><code>{path}</code></li>
						{/each}
					</ul>
				</section>
			{/if}
		</div>
	{:else}
		<div class="client-detail__error">
			<h2>Client Not Found</h2>
			<p>No client UUID provided or client does not exist.</p>
			<a href="/" class="et-btn et-btn--primary">Back to Dashboard</a>
		</div>
	{/if}
</div>

<style lang="scss">
	// Variables and mixins are auto-injected via vite.config.ts

	.client-detail {
		padding-top: $spacing-lg;
		padding-bottom: $spacing-lg;

		&__back {
			margin-bottom: $spacing-lg;
		}

		&__back-link {
			font-size: $font-size-sm;
			color: $text-300;
			text-decoration: none;

			&:hover {
				color: $accent-cyan;
			}
		}

		&__loading {
			@include panel;
			padding: $spacing-xl;
		}

		&__error {
			@include panel;
			@include flex-column;
			align-items: center;
			padding: $spacing-2xl;
			text-align: center;

			h2 {
				margin-bottom: $spacing-sm;
			}

			p {
				color: $text-300;
				margin-bottom: $spacing-lg;
			}
		}

		&__header {
			@include panel;
			margin-bottom: $spacing-lg;
		}

		&__header-main {
			margin-bottom: $spacing-md;
		}

		&__status {
			@include chip;
			background: rgba($accent-red, 0.12);
			color: $accent-red;
			margin-bottom: $spacing-sm;

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

		&__name {
			font-size: $font-size-2xl;
			font-weight: $font-weight-bold;
			color: $text-100;
			margin: 0 0 $spacing-xs;
		}

		&__hostname {
			font-family: $font-family-mono;
			font-size: $font-size-sm;
			color: $text-300;
			margin: 0;
		}

		&__tags {
			@include flex-start;
			flex-wrap: wrap;
			gap: $spacing-xs;
		}

		&__content {
			display: grid;
			gap: $spacing-lg;

			@include md {
				grid-template-columns: repeat(2, 1fr);
			}
		}

		&__panel {
			@include panel;
		}

		&__panel-title {
			font-size: $font-size-base;
			font-weight: $font-weight-semibold;
			color: $text-100;
			margin: 0 0 $spacing-md;
			padding-bottom: $spacing-sm;
			border-bottom: 1px solid $border-color;
		}

		&__info-list {
			margin: 0;
		}

		&__info-item {
			display: flex;
			justify-content: space-between;
			align-items: flex-start;
			padding: $spacing-sm 0;
			border-bottom: 1px solid rgba($border-color, 0.5);

			&:last-child {
				border-bottom: none;
			}

			dt {
				font-size: $font-size-sm;
				color: $text-400;
			}

			dd {
				font-size: $font-size-sm;
				color: $text-200;
				margin: 0;
				text-align: right;

				code {
					font-size: $font-size-xs;
				}
			}

			&--warning dd {
				color: $accent-amber;
			}
		}

		&__capabilities {
			@include flex-start;
			flex-wrap: wrap;
			gap: $spacing-xs;
		}

		&__paths {
			list-style: none;
			padding: 0;
			margin: 0;

			li {
				padding: $spacing-xs 0;
				border-bottom: 1px solid rgba($border-color, 0.5);

				&:last-child {
					border-bottom: none;
				}
			}
		}
	}
</style>
