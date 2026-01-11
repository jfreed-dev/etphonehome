<script lang="ts">
	interface PathSegment {
		name: string;
		path: string;
	}

	interface Props {
		segments: PathSegment[];
		onNavigate: (path: string) => void;
	}

	let { segments, onNavigate }: Props = $props();
</script>

<nav class="breadcrumb">
	{#each segments as segment, i}
		{#if i > 0}
			<span class="breadcrumb__separator">/</span>
		{/if}
		{#if i === segments.length - 1}
			<span class="breadcrumb__current">{segment.name}</span>
		{:else}
			<button class="breadcrumb__link" onclick={() => onNavigate(segment.path)}>
				{segment.name}
			</button>
		{/if}
	{/each}
</nav>

<style lang="scss">
	.breadcrumb {
		display: flex;
		align-items: center;
		gap: $spacing-xs;
		font-size: $font-size-sm;
		font-family: $font-family-mono;
		overflow-x: auto;
		@include custom-scrollbar;

		&__separator {
			color: $text-400;
		}

		&__link {
			background: none;
			border: none;
			padding: $spacing-xs $spacing-sm;
			color: $accent-cyan;
			cursor: pointer;
			border-radius: $radius-sm;
			transition: all 0.15s ease;

			&:hover {
				background: rgba($accent-cyan, 0.1);
			}
		}

		&__current {
			padding: $spacing-xs $spacing-sm;
			color: $text-100;
			font-weight: $font-weight-medium;
		}
	}
</style>
