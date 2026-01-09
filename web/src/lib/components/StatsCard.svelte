<script lang="ts">
	interface Props {
		label: string;
		value: string | number;
		variant?: 'default' | 'green' | 'amber' | 'cyan';
		icon?: string;
	}

	let { label, value, variant = 'default', icon }: Props = $props();
</script>

<div class="stats-card" data-variant={variant}>
	{#if icon}
		<span class="stats-card__icon">{icon}</span>
	{/if}
	<div class="stats-card__value">{value}</div>
	<div class="stats-card__label">{label}</div>
</div>

<style lang="scss">
	// Variables and mixins are auto-injected via vite.config.ts

	.stats-card {
		@include panel;
		text-align: center;
		padding: $spacing-lg;

		&__icon {
			display: block;
			font-size: 24px;
			margin-bottom: $spacing-sm;
		}

		&__value {
			font-size: $font-size-3xl;
			font-weight: $font-weight-bold;
			color: $accent-cyan;
			line-height: $line-height-tight;
		}

		&__label {
			font-size: $font-size-sm;
			color: $text-300;
			margin-top: $spacing-xs;
		}

		&[data-variant='green'] &__value {
			color: $accent-green;
		}

		&[data-variant='amber'] &__value {
			color: $accent-amber;
		}

		&[data-variant='cyan'] &__value {
			color: $accent-cyan;
		}
	}
</style>
