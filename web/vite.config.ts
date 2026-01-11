import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';
import path from 'path';

export default defineConfig({
	plugins: [sveltekit()],
	css: {
		preprocessorOptions: {
			scss: {
				// Use loadPaths to make SCSS files findable
				loadPaths: [path.resolve('./src/styles')],
				// Make SCSS variables/mixins available globally in component styles
				additionalData: `
					@use 'variables' as *;
					@use 'mixins' as *;
				`
			}
		}
	},
	server: {
		// Proxy API requests to Python server during development
		proxy: {
			'/api': {
				target: 'http://127.0.0.1:8765',
				changeOrigin: true,
				// Enable WebSocket proxying for /api/v1/ws
				ws: true
			},
			'/health': {
				target: 'http://127.0.0.1:8765',
				changeOrigin: true
			}
		}
	},
	build: {
		// Generate sourcemaps for debugging
		sourcemap: true
	}
});
