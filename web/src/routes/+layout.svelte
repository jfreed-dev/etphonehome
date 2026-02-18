<script lang="ts">
	import '$styles/global.scss';
	import { onMount } from 'svelte';
	import { initAuth, isAuthenticated } from '$stores/auth';
	import { initConnection } from '$stores/connection';
	import { Header, LoginForm } from '$components';

	let { children } = $props();

	onMount(() => {
		initAuth();
		if ($isAuthenticated) {
			initConnection();
		}
	});
</script>

<svelte:head>
	<title>Reach</title>
	<meta name="description" content="Remote access management dashboard" />
	<link rel="preconnect" href="https://fonts.googleapis.com" />
	<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin="anonymous" />
	<link
		href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap"
		rel="stylesheet"
	/>
</svelte:head>

{#if $isAuthenticated}
	<div class="page">
		<div class="page__header">
			<Header />
		</div>
		<main class="page__main">
			{@render children()}
		</main>
		<footer class="page__footer">
			<div class="reach-container">Reach &bull; Remote Access Management</div>
		</footer>
	</div>
{:else}
	<div class="login-page">
		<LoginForm />
	</div>
{/if}

<style lang="scss">
	// Variables and mixins are auto-injected via vite.config.ts

	.login-page {
		min-height: 100vh;
		display: flex;
		align-items: center;
		justify-content: center;
		padding: $spacing-lg;
		background: linear-gradient(135deg, $bg-900 0%, $bg-800 100%);
	}
</style>
