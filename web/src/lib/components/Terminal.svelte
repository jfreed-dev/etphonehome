<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { browser } from '$app/environment';
	import {
		terminalState,
		executeCommand,
		getPreviousCommand,
		getNextCommand,
		resetHistoryIndex,
		type TerminalSession
	} from '$stores/terminal';

	// Dynamic imports for xterm (browser-only)
	type TerminalType = import('@xterm/xterm').Terminal;
	type FitAddonType = import('@xterm/addon-fit').FitAddon;

	interface Props {
		session: TerminalSession;
	}

	let { session }: Props = $props();

	let terminalElement: HTMLDivElement;
	let terminal: TerminalType;
	let fitAddon: FitAddonType;
	let currentLine = '';
	let cursorPosition = 0;

	const PROMPT = '\x1b[36m➜\x1b[0m ';

	onMount(async () => {
		if (!browser) return;

		// Dynamic imports for browser-only xterm
		const [xtermModule, fitModule, webLinksModule] = await Promise.all([
			import('@xterm/xterm'),
			import('@xterm/addon-fit'),
			import('@xterm/addon-web-links')
		]);
		await import('@xterm/xterm/css/xterm.css');

		const { Terminal } = xtermModule;
		const { FitAddon } = fitModule;
		const { WebLinksAddon } = webLinksModule;
		// Initialize xterm.js
		terminal = new Terminal({
			cursorBlink: true,
			cursorStyle: 'bar',
			fontSize: 13,
			fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
			lineHeight: 1.2,
			theme: {
				background: '#0B1020',
				foreground: '#E6F7FF',
				cursor: '#2DE2E6',
				cursorAccent: '#0B1020',
				selectionBackground: 'rgba(45, 226, 230, 0.3)',
				black: '#0B1020',
				red: '#FF6B6B',
				green: '#7CFF6B',
				yellow: '#FFB454',
				blue: '#2DE2E6',
				magenta: '#BD93F9',
				cyan: '#2DE2E6',
				white: '#E6F7FF',
				brightBlack: '#4A5568',
				brightRed: '#FF8585',
				brightGreen: '#98FF85',
				brightYellow: '#FFCC85',
				brightBlue: '#5EEAEA',
				brightMagenta: '#D4AFFF',
				brightCyan: '#5EEAEA',
				brightWhite: '#FFFFFF'
			}
		});

		fitAddon = new FitAddon();
		terminal.loadAddon(fitAddon);
		terminal.loadAddon(new WebLinksAddon());

		terminal.open(terminalElement);
		fitAddon.fit();

		// Write welcome message
		terminal.writeln('\x1b[1;36m╭─────────────────────────────────────╮\x1b[0m');
		terminal.writeln('\x1b[1;36m│\x1b[0m   ET Phone Home Terminal Session   \x1b[1;36m│\x1b[0m');
		terminal.writeln('\x1b[1;36m╰─────────────────────────────────────╯\x1b[0m');
		terminal.writeln('');
		terminal.writeln('\x1b[90mType commands and press Enter to execute.\x1b[0m');
		terminal.writeln('\x1b[90mUse ↑/↓ for history, Tab for completion.\x1b[0m');
		terminal.writeln('');

		// Restore history
		for (const entry of session.history) {
			writeHistoryEntry(entry);
		}

		writePrompt();

		// Handle input
		terminal.onData(handleInput);

		// Handle resize
		const resizeObserver = new ResizeObserver(() => {
			fitAddon.fit();
		});
		resizeObserver.observe(terminalElement);

		return () => {
			resizeObserver.disconnect();
			terminal.dispose();
		};
	});

	onDestroy(() => {
		terminal?.dispose();
	});

	function writePrompt() {
		terminal.write(PROMPT);
	}

	function writeHistoryEntry(entry: { command: string; output: string; returncode: number }) {
		terminal.write(PROMPT);
		terminal.writeln(entry.command);
		if (entry.output) {
			// Color output based on success/failure
			const color = entry.returncode === 0 ? '' : '\x1b[31m';
			const reset = entry.returncode === 0 ? '' : '\x1b[0m';
			terminal.writeln(color + entry.output + reset);
		}
	}

	async function handleInput(data: string) {
		// Handle special keys
		for (const char of data) {
			const code = char.charCodeAt(0);

			// Enter
			if (code === 13) {
				terminal.writeln('');
				if (currentLine.trim()) {
					await runCommand(currentLine);
				} else {
					writePrompt();
				}
				currentLine = '';
				cursorPosition = 0;
				resetHistoryIndex(session.id);
				continue;
			}

			// Backspace
			if (code === 127) {
				if (cursorPosition > 0) {
					currentLine = currentLine.slice(0, cursorPosition - 1) + currentLine.slice(cursorPosition);
					cursorPosition--;
					// Rewrite the line
					terminal.write('\x1b[2K\r'); // Clear line
					terminal.write(PROMPT + currentLine);
					// Move cursor back if needed
					if (cursorPosition < currentLine.length) {
						terminal.write(`\x1b[${currentLine.length - cursorPosition}D`);
					}
				}
				continue;
			}

			// Escape sequences
			if (code === 27) {
				continue;
			}

			// Arrow keys come as escape sequences
			if (data === '\x1b[A') {
				// Up arrow - previous command
				const prev = getPreviousCommand(session.id);
				if (prev !== null) {
					terminal.write('\x1b[2K\r'); // Clear line
					terminal.write(PROMPT + prev);
					currentLine = prev;
					cursorPosition = prev.length;
				}
				return;
			}

			if (data === '\x1b[B') {
				// Down arrow - next command
				const next = getNextCommand(session.id);
				if (next !== null) {
					terminal.write('\x1b[2K\r'); // Clear line
					terminal.write(PROMPT + next);
					currentLine = next;
					cursorPosition = next.length;
				}
				return;
			}

			if (data === '\x1b[C') {
				// Right arrow
				if (cursorPosition < currentLine.length) {
					cursorPosition++;
					terminal.write('\x1b[C');
				}
				return;
			}

			if (data === '\x1b[D') {
				// Left arrow
				if (cursorPosition > 0) {
					cursorPosition--;
					terminal.write('\x1b[D');
				}
				return;
			}

			// Ctrl+C
			if (code === 3) {
				terminal.writeln('^C');
				currentLine = '';
				cursorPosition = 0;
				writePrompt();
				continue;
			}

			// Ctrl+L (clear)
			if (code === 12) {
				terminal.clear();
				writePrompt();
				terminal.write(currentLine);
				continue;
			}

			// Ctrl+U (clear line)
			if (code === 21) {
				terminal.write('\x1b[2K\r');
				writePrompt();
				currentLine = '';
				cursorPosition = 0;
				continue;
			}

			// Regular character
			if (code >= 32) {
				currentLine = currentLine.slice(0, cursorPosition) + char + currentLine.slice(cursorPosition);
				cursorPosition++;
				// Rewrite from cursor position
				terminal.write(char + currentLine.slice(cursorPosition));
				// Move cursor back if we inserted in the middle
				if (cursorPosition < currentLine.length) {
					terminal.write(`\x1b[${currentLine.length - cursorPosition}D`);
				}
			}
		}
	}

	async function runCommand(command: string) {
		terminal.writeln(`\x1b[90mExecuting...\x1b[0m`);

		const result = await executeCommand(session.id, command);

		if (command.trim() === 'clear') {
			terminal.clear();
		} else if (result) {
			// Write output
			if (result.stdout) {
				terminal.writeln(result.stdout);
			}
			if (result.stderr) {
				terminal.writeln(`\x1b[31m${result.stderr}\x1b[0m`);
			}

			// Show exit code if non-zero
			if (result.returncode !== 0) {
				terminal.writeln(`\x1b[31m[Exit code: ${result.returncode}]\x1b[0m`);
			}
		} else if ($terminalState.error) {
			terminal.writeln(`\x1b[31mError: ${$terminalState.error}\x1b[0m`);
		}

		writePrompt();
	}
</script>

<div class="terminal-wrapper">
	<div class="terminal-container" bind:this={terminalElement}></div>
</div>

<style lang="scss">
	.terminal-wrapper {
		@include panel;
		height: 100%;
		min-height: 400px;
		overflow: hidden;
		background: $bg-900;
	}

	.terminal-container {
		height: 100%;
		padding: $spacing-sm;

		:global(.xterm) {
			height: 100%;
		}

		:global(.xterm-viewport) {
			@include custom-scrollbar;
		}
	}
</style>
