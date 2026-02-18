<script lang="ts">
	import { onMount } from 'svelte';
	import { ClientCard, ActivityStream, StatsCard } from '$components';
	import { clients, onlineCount, totalCount, fetchClients, clientsLoading } from '$stores/clients';
	import { fetchEvents } from '$stores/events';
	import { fetchDashboard, serverUptime, serverVersion } from '$stores/dashboard';

	onMount(() => {
		// Fetch initial data
		fetchDashboard();
		fetchClients();
		fetchEvents();
	});
</script>

<div class="dashboard reach-container">
	<!-- Stats Row -->
	<section class="dashboard__stats">
		<StatsCard label="Online Clients" value={$onlineCount} variant="green" icon="🟢" />
		<StatsCard label="Total Clients" value={$totalCount} variant="cyan" icon="📡" />
		<StatsCard label="Server Uptime" value={$serverUptime ?? '—'} variant="default" icon="⏱️" />
		<StatsCard label="Version" value={$serverVersion ?? '—'} variant="default" icon="🏷️" />
	</section>

	<!-- Main Content -->
	<div class="dashboard__content">
		<!-- Clients Section -->
		<section class="dashboard__clients">
			<div class="dashboard__section-header">
				<h2 class="dashboard__section-title">Clients</h2>
				<span class="dashboard__section-count">{$totalCount} total</span>
			</div>

			{#if $clientsLoading}
				<div class="dashboard__loading">Loading clients...</div>
			{:else if $clients.length === 0}
				<div class="dashboard__empty">
					<p>No clients registered yet.</p>
					<p>Run the Reach client to connect.</p>
				</div>
			{:else}
				<div class="dashboard__client-grid">
					{#each $clients as client (client.uuid)}
						<ClientCard {client} />
					{/each}
				</div>
			{/if}
		</section>

		<!-- Activity Section -->
		<aside class="dashboard__activity">
			<ActivityStream />
		</aside>
	</div>
</div>

<style lang="scss">
	// Variables and mixins are auto-injected via vite.config.ts

	.dashboard {
		padding-top: $spacing-lg;
		padding-bottom: $spacing-lg;

		&__stats {
			display: grid;
			grid-template-columns: repeat(2, 1fr);
			gap: $spacing-md;
			margin-bottom: $spacing-xl;

			@include md {
				grid-template-columns: repeat(4, 1fr);
			}
		}

		&__content {
			display: grid;
			gap: $spacing-xl;

			@include lg {
				grid-template-columns: 1fr 350px;
			}
		}

		&__section-header {
			@include flex-between;
			margin-bottom: $spacing-md;
		}

		&__section-title {
			font-size: $font-size-xl;
			font-weight: $font-weight-semibold;
			color: $text-100;
			margin: 0;
		}

		&__section-count {
			font-size: $font-size-sm;
			color: $text-400;
		}

		&__client-grid {
			display: grid;
			gap: $spacing-md;

			@include md {
				grid-template-columns: repeat(2, 1fr);
			}

			@include xl {
				grid-template-columns: repeat(2, 1fr);
			}
		}

		&__loading {
			@include panel;
			@include flex-center;
			padding: $spacing-2xl;
			text-align: center;
			color: $text-400;
		}

		&__empty {
			@include panel;
			@include flex-center;
			flex-direction: column;
			padding: $spacing-2xl;
			text-align: center;
			color: $text-400;

			p {
				margin: $spacing-xs 0;

				&:first-child {
					color: $text-300;
				}
			}
		}

		&__activity {
			@include lg {
				position: sticky;
				top: calc($header-height + $spacing-lg);
				height: fit-content;
			}
		}
	}
</style>
