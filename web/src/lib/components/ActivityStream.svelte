<script lang="ts">
	import { recentEvents } from '$stores/events';
	import { formatEventTime, getEventColor } from '$stores/events';

	function getEventIcon(type: string): string {
		switch (type) {
			case 'client.connected':
				return '🔗';
			case 'client.disconnected':
				return '🔌';
			case 'client.key_mismatch':
				return '🔑';
			case 'client.unhealthy':
				return '⚠️';
			case 'command_executed':
				return '💻';
			case 'file_accessed':
				return '📁';
			default:
				return 'ℹ️';
		}
	}

	function getTypeLabel(type: string): string {
		switch (type) {
			case 'client.connected':
				return 'Connected';
			case 'client.disconnected':
				return 'Disconnected';
			case 'client.key_mismatch':
				return 'Key Mismatch';
			case 'client.unhealthy':
				return 'Unhealthy';
			case 'command_executed':
				return 'Command';
			case 'file_accessed':
				return 'File Access';
			default:
				return type;
		}
	}
</script>

<div class="activity-stream">
	<div class="activity-stream__header">
		<h3 class="activity-stream__title">Recent Activity</h3>
	</div>

	{#if $recentEvents.length === 0}
		<div class="activity-stream__empty">
			<p>No recent activity</p>
		</div>
	{:else}
		<ul class="activity-stream__list">
			{#each $recentEvents as event (event.timestamp + event.client_uuid)}
				<li class="activity-stream__item" data-type={event.type}>
					<span class="activity-stream__icon">{getEventIcon(event.type)}</span>
					<div class="activity-stream__content">
						<div class="activity-stream__row">
							<span class="activity-stream__client">{event.client_name}</span>
							<span class="activity-stream__time">{formatEventTime(event.timestamp)}</span>
						</div>
						<div class="activity-stream__row">
							<span class="activity-stream__type" data-color={getEventColor(event.type as any)}>
								{getTypeLabel(event.type)}
							</span>
							{#if event.summary}
								<span class="activity-stream__summary">{event.summary}</span>
							{/if}
						</div>
					</div>
				</li>
			{/each}
		</ul>
	{/if}
</div>

<style lang="scss">
	// Variables and mixins are auto-injected via vite.config.ts

	.activity-stream {
		@include panel;
		padding: 0;
		max-height: 400px;
		overflow: hidden;
		display: flex;
		flex-direction: column;

		&__header {
			@include flex-between;
			padding: $spacing-md $spacing-lg;
			border-bottom: 1px solid $border-color;
		}

		&__title {
			font-size: $font-size-base;
			font-weight: $font-weight-semibold;
			color: $text-100;
			margin: 0;
		}

		&__empty {
			@include flex-center;
			padding: $spacing-xl;
			color: $text-400;
			font-size: $font-size-sm;
		}

		&__list {
			list-style: none;
			margin: 0;
			padding: 0;
			overflow-y: auto;
			@include custom-scrollbar;
		}

		&__item {
			display: flex;
			gap: $spacing-sm;
			padding: $spacing-sm $spacing-lg;
			border-bottom: 1px solid rgba($border-color, 0.5);
			transition: background $transition-fast;

			&:last-child {
				border-bottom: none;
			}

			&:hover {
				background: rgba($accent-cyan, 0.05);
			}
		}

		&__icon {
			flex-shrink: 0;
			width: 24px;
			text-align: center;
			font-size: $font-size-sm;
		}

		&__content {
			flex: 1;
			min-width: 0;
		}

		&__row {
			@include flex-between;
			gap: $spacing-sm;

			&:first-child {
				margin-bottom: 2px;
			}
		}

		&__client {
			font-size: $font-size-sm;
			font-weight: $font-weight-medium;
			color: $text-100;
			@include text-truncate;
		}

		&__time {
			font-size: $font-size-xs;
			color: $text-400;
			flex-shrink: 0;
		}

		&__type {
			font-size: $font-size-xs;
			font-weight: $font-weight-medium;

			&[data-color='green'] {
				color: $accent-green;
			}
			&[data-color='red'] {
				color: $accent-red;
			}
			&[data-color='amber'] {
				color: $accent-amber;
			}
			&[data-color='cyan'] {
				color: $accent-cyan;
			}
		}

		&__summary {
			font-size: $font-size-xs;
			color: $text-300;
			@include text-truncate;
		}
	}
</style>
