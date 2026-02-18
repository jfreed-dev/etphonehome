<script lang="ts">
	import { connectionStatus } from '$stores';
	import { logout } from '$stores/auth';

	function handleLogout() {
		logout();
		window.location.reload();
	}
</script>

<header class="header">
	<div class="header__left">
		<a href="/" class="header__logo">
			<img src="/logos/logo-horizontal.svg" alt="Reach" class="header__logo-img" />
		</a>
	</div>

	<div class="header__right">
		<div class="header__status" class:header__status--connected={$connectionStatus === 'connected'}>
			<span class="header__status-dot"></span>
			<span class="header__status-text">
				{#if $connectionStatus === 'connected'}
					Connected
				{:else if $connectionStatus === 'connecting'}
					Connecting...
				{:else}
					Disconnected
				{/if}
			</span>
		</div>

		<button class="header__logout" onclick={handleLogout} title="Logout">
			<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
				<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
				<polyline points="16 17 21 12 16 7" />
				<line x1="21" y1="12" x2="9" y2="12" />
			</svg>
		</button>
	</div>
</header>

<style lang="scss">
	// Variables and mixins are auto-injected via vite.config.ts

	.header {
		@include flex-between;
		height: $header-height;
		padding: 0 $spacing-lg;
		background: $bg-800;
		border-bottom: 1px solid $border-color;

		&__left {
			@include flex-start;
		}

		&__logo {
			display: block;
			text-decoration: none;
		}

		&__logo-img {
			height: 32px;
			width: auto;
		}

		&__right {
			@include flex-start;
			gap: $spacing-md;
		}

		&__status {
			@include flex-start;
			gap: $spacing-xs;
			padding: $spacing-xs $spacing-sm;
			border-radius: $radius-full;
			background: rgba($accent-red, 0.1);
			font-size: $font-size-sm;
			color: $accent-red;

			&--connected {
				background: rgba($accent-green, 0.1);
				color: $accent-green;
			}
		}

		&__status-dot {
			width: 8px;
			height: 8px;
			border-radius: 50%;
			background: currentColor;
		}

		&__logout {
			@include button-ghost;
			width: 36px;
			height: 36px;
			padding: 0;
			border-radius: $radius-md;

			svg {
				width: 20px;
				height: 20px;
			}
		}
	}
</style>
