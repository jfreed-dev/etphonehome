<script lang="ts">
	import { login, authError, authLoading } from '$stores/auth';

	let apiKey = $state('');

	async function handleSubmit(event: Event) {
		event.preventDefault();
		if (!apiKey.trim()) return;

		const success = await login(apiKey.trim());
		if (success) {
			// The parent component will handle the redirect/state change
		}
	}
</script>

<div class="login-form">
	<div class="login-form__header">
		<img src="/logos/logo-stacked.svg" alt="Reach" class="login-form__logo" />
		<h1 class="login-form__title">Welcome Back</h1>
		<p class="login-form__subtitle">Enter your API key to access the dashboard</p>
	</div>

	<form class="login-form__form" onsubmit={handleSubmit}>
		{#if $authError}
			<div class="login-form__error">
				{$authError}
			</div>
		{/if}

		<div class="login-form__field">
			<label for="api-key" class="login-form__label">API Key</label>
			<input
				type="password"
				id="api-key"
				class="login-form__input"
				placeholder="Enter your API key"
				bind:value={apiKey}
				disabled={$authLoading}
				autocomplete="off"
			/>
		</div>

		<button type="submit" class="login-form__submit" disabled={$authLoading || !apiKey.trim()}>
			{#if $authLoading}
				Authenticating...
			{:else}
				Sign In
			{/if}
		</button>
	</form>

	<div class="login-form__footer">
		<p>API key is configured in the server environment</p>
	</div>
</div>

<style lang="scss">
	// Variables and mixins are auto-injected via vite.config.ts

	.login-form {
		@include panel;
		max-width: 400px;
		margin: 0 auto;
		padding: $spacing-xl;

		&__header {
			text-align: center;
			margin-bottom: $spacing-xl;
		}

		&__logo {
			height: 80px;
			margin-bottom: $spacing-lg;
		}

		&__title {
			font-size: $font-size-2xl;
			font-weight: $font-weight-bold;
			color: $text-100;
			margin: 0 0 $spacing-sm;
		}

		&__subtitle {
			font-size: $font-size-sm;
			color: $text-300;
			margin: 0;
		}

		&__form {
			display: flex;
			flex-direction: column;
			gap: $spacing-md;
		}

		&__error {
			padding: $spacing-sm $spacing-md;
			background: rgba($accent-red, 0.1);
			border: 1px solid rgba($accent-red, 0.3);
			border-radius: $radius-md;
			color: $accent-red;
			font-size: $font-size-sm;
		}

		&__field {
			display: flex;
			flex-direction: column;
			gap: $spacing-xs;
		}

		&__label {
			font-size: $font-size-sm;
			font-weight: $font-weight-medium;
			color: $text-300;
		}

		&__input {
			@include input-base;
		}

		&__submit {
			@include button-primary;
			width: 100%;
			padding: $spacing-md;
			margin-top: $spacing-sm;
		}

		&__footer {
			margin-top: $spacing-lg;
			padding-top: $spacing-lg;
			border-top: 1px solid $border-color;
			text-align: center;

			p {
				font-size: $font-size-xs;
				color: $text-400;
				margin: 0;
			}
		}
	}
</style>
