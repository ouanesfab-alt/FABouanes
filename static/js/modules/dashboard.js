// dashboard.js — KPI sheets, Chart.js graphs, date pickers
// Extracted from dashboard.html inline <script> block 1


	// ─── KPI SHEET ───
	let currentKpiKey = null;
	let currentKpiLabel = null;
	function openKpiSheet(key, label) {
		currentKpiKey = key;
		currentKpiLabel = label;
		document.getElementById('kpiSheetTitle').textContent = label + ' à une date';
		const overlay = document.getElementById('kpiSheetOverlay');
		if (overlay.parentElement !== document.body) {
			document.body.appendChild(overlay);
		}
		overlay.classList.add('open');
		document.body.classList.add('kpi-modal-open');
		const input = document.getElementById('kpiDateInput');
		if (!input.value) {
			const d = new Date();
			input.value = (new Date(d.getTime() - d.getTimezoneOffset() * 60000)).toISOString().slice(0, 10);
		}
		document.getElementById('kpiResult').classList.remove('show');
		document.querySelectorAll('.kpi-quick-btn').forEach(b => b.classList.remove('active'));
	}
	function closeKpiSheet() {
		document.getElementById('kpiSheetOverlay').classList.remove('open');
		document.body.classList.remove('kpi-modal-open');
	}
	function setKpiDateOffset(days, btn) {
		const d = new Date();
		d.setDate(d.getDate() - days);
		document.getElementById('kpiDateInput').value = (new Date(d.getTime() - d.getTimezoneOffset() * 60000)).toISOString().slice(0, 10);
		document.querySelectorAll('.kpi-quick-btn').forEach(b => b.classList.remove('active'));
		if (btn) btn.classList.add('active');
	}
	async function fetchKpiAtDate() {
		if (!currentKpiKey) return;
		const date = document.getElementById('kpiDateInput').value;
		if (!date) return;
		const res = await fetch(`/api/kpi-at-date?metric=${encodeURIComponent(currentKpiKey)}&date=${encodeURIComponent(date)}`);
		const data = await res.json();
		const result = document.getElementById('kpiResult');
		document.getElementById('kpiResultLabel').textContent = currentKpiLabel;
		document.getElementById('kpiResultValue').textContent = (data.display || '0').replace(' DA', '');
		document.getElementById('kpiResultDate').textContent = 'Date : ' + date;
		result.classList.add('show');
	}
	document.addEventListener('keydown', function (event) {
		if (event.key === 'Escape') {
			const overlay = document.getElementById('kpiSheetOverlay');
			if (overlay && overlay.classList.contains('open')) closeKpiSheet();
			// Also close settings
			document.getElementById('fabSettingsOverlay')?.classList.remove('show');
		}
	});

	// ─── SABRINA ASSISTANT WIDGET ───
	(function () {
		const hero = document.getElementById('fabHero');
		const chatArea = document.getElementById('fabChatArea');
		const input = document.getElementById('fabChatInput');
		const sendBtn = document.getElementById('fabSendBtn');
		const stopBtn = document.getElementById('fabStopBtn');
		const clearBtn = document.getElementById('fabClearChatBtn');
		const micBtn = document.getElementById('fabMicBtn');
		const soundwave = document.getElementById('fabSoundwave');
		const attachBtn = document.getElementById('fabAttachBtn');
		const fileInput = document.getElementById('fabFileInput');
		const fileChip = document.getElementById('fabFileChip');
		const fileName = document.getElementById('fabFileName');
		const fileIcon = document.getElementById('fabFileIcon');
		const removeFile = document.getElementById('fabRemoveFile');
		const settingsToggle = document.getElementById('fabSettingsToggle');

		let history = [];
		let threads = [];
		let activeThreadId = null;
		let abortController = null;
		let selectedFile = null;

		// ── Save Settings AJAX Helper ──
		async function saveSettingsAJAX(model, apiKey) {
			const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || "";
			const formData = new FormData();
			formData.append('csrf_token', csrfToken);
			if (model) formData.append('gemini_model', model);
			if (apiKey) formData.append('gemini_api_key', apiKey);
			try {
				const res = await fetch('/assistant/settings', {
					method: 'POST', body: formData,
					headers: { 'X-Requested-With': 'XMLHttpRequest' }
				});
				return res.ok;
			} catch { return false; }
		}

		// Force-clear local storage key to start fresh as requested by user
		localStorage.removeItem('fab_gemini_api_key');

		// ── Thread Management ──
		function loadActiveThread() {
			try {
				const saved = localStorage.getItem('fab_assistant_threads');
				const activeId = localStorage.getItem('fab_assistant_active_thread_id');
				if (saved) threads = JSON.parse(saved);
				if (activeId && threads.some(t => t.id === activeId)) {
					activeThreadId = activeId;
				} else if (threads.length > 0) {
					activeThreadId = threads[0].id;
				}
				const thread = threads.find(t => t.id === activeThreadId);
				history = thread ? (thread.history || []) : [];
			} catch (e) { }
		}

		function saveActiveThread() {
			try {
				let thread = threads.find(t => t.id === activeThreadId);
				if (!thread) {
					thread = { id: 'thread_' + Date.now(), title: 'Nouvelle discussion 💬', history: [] };
					threads.unshift(thread);
					activeThreadId = thread.id;
					localStorage.setItem('fab_assistant_active_thread_id', activeThreadId);
				}
				thread.history = history;
				if (thread.title === 'Nouvelle discussion 💬' && history.length > 0) {
					const first = history.find(m => m.role === 'user');
					if (first) {
						let t = "";
						if (first.content) {
							t = first.content;
						} else if (first.parts && first.parts.length > 0) {
							const textPart = first.parts.find(p => p.text);
							if (textPart) t = textPart.text;
						}
						if (t) {
							thread.title = t.substring(0, 24) + (t.length > 24 ? '...' : '');
						}
					}
				}
				localStorage.setItem('fab_assistant_threads', JSON.stringify(threads));
			} catch (e) { }
		}

		// ── Chat UI ──
		function showChatView() {
			hero.classList.add('chat-active');
			chatArea.classList.add('active');
			localStorage.setItem('fab_chat_expanded', 'true');
		}

		function scrollToBottom(smooth = true) {
			chatArea.scrollTo({ top: chatArea.scrollHeight, behavior: smooth ? 'smooth' : 'auto' });
		}

		function appendMessage(role, text, shouldScroll = true) {
			const bubble = document.createElement('div');
			bubble.className = `fab-chat-bubble ${role}`;
			bubble.setAttribute('data-raw-text', text);

			const content = document.createElement('div');
			content.className = 'bubble-content';

			// Check if message is a voice note
			const audioMatch = text.match(/^\[AUDIO:([^|]+)\|(.*)]\s*$/s) ||
				text.match(/^\[AUDIO:([^|]+)\|(.*)\]$/);
			if (audioMatch) {
				const dataUrl = audioMatch[1];
				const transcript = (audioMatch[2] || '').trim();

				// Build the voice-note bubble using DOM APIs (NOT innerHTML) so the
				// base64 data URL isn't corrupted by the HTML parser.
				const vnBubble = document.createElement('div');
				vnBubble.className = 'voice-note-bubble';

				const playBtn = document.createElement('button');
				playBtn.className = 'voice-play-btn';
				playBtn.type = 'button';
				const playIcon = document.createElement('i');
				playIcon.className = 'bi bi-play-fill';
				playBtn.appendChild(playIcon);

				const waveContainer = document.createElement('div');
				waveContainer.className = 'voice-wave-container';

				const durationText = document.createElement('span');
				durationText.className = 'voice-duration';
				durationText.textContent = '0:00';

				// Convert base64 data URL → Blob → Object URL for reliable playback
				const audio = document.createElement('audio');
				audio.preload = 'metadata';
				try {
					if (dataUrl.startsWith('data:') && dataUrl.includes(';base64,')) {
						const [meta, b64] = dataUrl.split(';base64,');
						const mimeType = meta.replace('data:', '');
						const byteChars = atob(b64);
						const byteArr = new Uint8Array(byteChars.length);
						for (let i = 0; i < byteChars.length; i++) byteArr[i] = byteChars.charCodeAt(i);
						const blob = new Blob([byteArr], { type: mimeType });
						audio.src = URL.createObjectURL(blob);
					} else {
						audio.src = dataUrl;
					}
				} catch (e) {
					console.warn('Audio decode error:', e);
					audio.src = dataUrl;
				}

				vnBubble.appendChild(playBtn);
				vnBubble.appendChild(waveContainer);
				vnBubble.appendChild(durationText);
				vnBubble.appendChild(audio);
				content.appendChild(vnBubble);

				if (transcript) {
					const txDiv = document.createElement('div');
					txDiv.className = 'voice-transcript-text';
					txDiv.innerHTML = '🎤 ' + parseMarkdown(transcript);
					content.appendChild(txDiv);
				}

				bubble.appendChild(content);

				// Draw 18 waves with random heights for visual style
				for (let i = 0; i < 18; i++) {
					const bar = document.createElement('div');
					bar.className = 'voice-wave-bar';
					bar.style.height = `${Math.floor(Math.random() * 12) + 6}px`;
					waveContainer.appendChild(bar);
				}

				// Format duration helper
				const formatTime = (secs) => {
					if (!secs || isNaN(secs)) return '0:00';
					const m = Math.floor(secs / 60);
					const s = Math.floor(secs % 60);
					return `${m}:${s < 10 ? '0' : ''}${s}`;
				};

				// Load metadata duration
				audio.addEventListener('loadedmetadata', () => {
					durationText.textContent = formatTime(audio.duration);
				});

				// Toggle playback
				playBtn.addEventListener('click', (e) => {
					e.preventDefault();
					e.stopPropagation();

					// Stop other playing audios
					document.querySelectorAll('audio').forEach(a => {
						if (a !== audio) {
							a.pause();
							const pBtn = a.closest('.voice-note-bubble')?.querySelector('.voice-play-btn i');
							if (pBtn) pBtn.className = 'bi bi-play-fill';
						}
					});

					if (audio.paused) {
						audio.volume = 1;
						audio.muted = false;
						audio.play().catch(err => console.warn('Audio play failed:', err));
						playIcon.className = 'bi bi-pause-fill';
					} else {
						audio.pause();
						playIcon.className = 'bi bi-play-fill';
					}
				});

				// Time updates
				audio.addEventListener('timeupdate', () => {
					durationText.textContent = formatTime(audio.currentTime || 0);
					const pct = audio.currentTime / audio.duration;
					const bars = waveContainer.querySelectorAll('.voice-wave-bar');
					const activeCount = Math.floor(pct * bars.length);
					bars.forEach((bar, idx) => {
						bar.classList.toggle('active', idx <= activeCount);
					});
				});

				// Audio finished
				audio.addEventListener('ended', () => {
					playIcon.className = 'bi bi-play-fill';
					durationText.textContent = formatTime(audio.duration);
					waveContainer.querySelectorAll('.voice-wave-bar').forEach(b => b.classList.remove('active'));
				});

			} else {
				content.innerHTML = parseMarkdown(text);
				bubble.appendChild(content);
			}

			if (role === 'model') {
				const actions = document.createElement('div');
				actions.className = 'fab-bubble-actions';
				actions.innerHTML = `
					<button class="fab-bubble-btn btn-copy"><i class="bi bi-clipboard"></i> Copier</button>
					<button class="fab-bubble-btn btn-speak"><i class="bi bi-volume-up"></i> Lire</button>
				`;
				bubble.appendChild(actions);
			}

			chatArea.appendChild(bubble);
			if (shouldScroll) {
				scrollToBottom();
			}
			return bubble;
		}

		function appendTypingIndicator() {
			const el = document.createElement('div');
			el.className = 'fab-typing align-items-center gap-2 d-inline-flex';
			el.style.cssText = 'background: var(--surface); border: 1px solid var(--line); padding: 8px 14px; border-radius: 16px; margin: 6px 0;';
			el.innerHTML = `
				<div class="fab-typing-indicator me-1">
					<span></span>
					<span></span>
					<span></span>
				</div>
				<span class="fab-status-text small" style="font-size: 0.82rem; color: var(--text-secondary); font-weight: 600; line-height: 1;">Sabrina réfléchit...</span>
			`;
			chatArea.appendChild(el);
			scrollToBottom();
			return el;
		}

		function renderHistory() {
			chatArea.innerHTML = '';
			history.forEach(msg => {
				let text = "";
				if (msg.content) {
					text = msg.content;
				} else if (msg.parts && msg.parts.length > 0) {
					text = msg.parts.filter(p => p.text).map(p => p.text).join('');
				}
				
				if (!text) return;
				
				const role = (msg.role === 'assistant' || msg.role === 'model') ? 'model' : 'user';
				appendMessage(role, text, false);
			});
			scrollToBottom(false);
		}

		function parseMarkdown(md) {
			if (!md) return "";
			let c = md.replace(/\[REDIRECT:[^\]]+\]/gi, '').replace(/\[THEME:[^\]]+\]/gi, '').trim();
			let h = c.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
			h = h.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" class="fw-semibold text-primary text-decoration-underline">$1</a>');
			h = h.replace(/```(sql|json|text|html|)?([\s\S]*?)```/g, '<pre><code>$2</code></pre>');
			h = h.replace(/`([^`]+)`/g, '<code>$1</code>');
			h = h.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
			h = h.replace(/\*([^*]+)\*/g, '<em>$1</em>');
			h = h.replace(/\n/g, '<br>');
			return h;
		}

		// ── Confirmation Bubble ──
		function appendConfirmationBubble(query, messageText) {
			const bubble = document.createElement('div');
			bubble.className = 'fab-chat-bubble system p-3 border-warning';
			bubble.style.cssText = 'background: rgba(255, 193, 7, 0.08); border: 1px solid rgba(255, 193, 7, 0.3); border-radius: 12px; margin: 10px 0; width: 100%; box-sizing: border-box;';

			bubble.innerHTML = `
				<div class="fw-bold text-warning mb-2" style="font-size:0.9rem;"><i class="bi bi-shield-lock-fill"></i> Confirmation requise</div>
				<p class="small mb-2" style="color:var(--text-primary); font-size:0.82rem;">${messageText}</p>
				<pre class="p-2 bg-dark text-light rounded mb-3" style="font-size:0.75rem; overflow-x:auto; font-family: monospace; border:1px solid rgba(255,255,255,0.1);"><code>${query}</code></pre>
				<div class="d-flex gap-2">
					<button class="btn btn-warning btn-sm fw-bold btn-confirm-write" style="font-size:0.78rem; padding: 6px 12px; border-radius: 6px; color: #212529 !important;"><i class="bi bi-check2"></i> Confirmer</button>
					<button class="btn btn-outline-secondary btn-sm btn-cancel-write" style="font-size:0.78rem; padding: 6px 12px; border-radius: 6px;">Annuler</button>
				</div>
			`;
			chatArea.appendChild(bubble);
			scrollToBottom();

			return new Promise((resolve) => {
				bubble.querySelector('.btn-confirm-write').addEventListener('click', () => {
					bubble.remove();
					resolve(true);
				});
				bubble.querySelector('.btn-cancel-write').addEventListener('click', () => {
					bubble.remove();
					resolve(false);
				});
			});
		}

		// ── Send Message ──
		async function sendMessage(text, confirmedQuery = null) {
			if (!text || text.trim() === "") return;
			loadActiveThread();
			showChatView();
			localStorage.setItem('fab_chat_expanded', 'true');

			let fileData = null;
			if (!confirmedQuery) {
				if (selectedFile) {
					fileData = await new Promise((resolve) => {
						const reader = new FileReader();
						reader.onload = (e) => {
							resolve({ mime_type: selectedFile.type, name: selectedFile.name, data: e.target.result.split(',')[1] });
						};
						reader.readAsDataURL(selectedFile);
					});
				}

				appendMessage('user', text);
				let historyText = text;
				if (fileData) historyText = `[Fichier: ${fileData.name}] ${text}`;
				history.push({ role: 'user', parts: [{ text: historyText }] });
				saveActiveThread();
				input.value = '';
				input.style.height = '36px';

				// Clear file preview
				selectedFile = null;
				if (fileInput) fileInput.value = '';
				fileChip.classList.remove('show');
			}

			sendBtn.style.display = 'none';
			stopBtn.style.display = 'inline-flex';

			let indicator = appendTypingIndicator();
			abortController = new AbortController();
			const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || "";

			try {
				const response = await fetch('/assistant/chat', {
					method: 'POST',
					headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest', 'X-CSRF-Token': csrfToken },
					body: JSON.stringify({
						message: text,
						history: history,
						file: fileData,
						confirmed_query: confirmedQuery,
						gemini_api_key: localStorage.getItem('fab_gemini_api_key') || ''
					}),
					signal: abortController.signal
				});
				if (!response.ok) throw new Error("HTTP " + response.status);

				let streamBubble = null;
				const reader = response.body.getReader();
				const decoder = new TextDecoder();
				let buffer = '';

				while (true) {
					const { value, done } = await reader.read();
					if (done) break;
					buffer += decoder.decode(value, { stream: true });
					const lines = buffer.split('\n');
					buffer = lines.pop();

					for (const line of lines) {
						const cl = line.trim();
						if (!cl.startsWith('data: ')) continue;
						let event;
						try { event = JSON.parse(cl.substring(6)); } catch { continue; }

						if (event.type === 'status') {
							if (indicator) {
								const statusEl = indicator.querySelector('.fab-status-text');
								if (statusEl) {
									statusEl.textContent = event.message;
									scrollToBottom();
								}
							}
						} else if (event.type === 'confirmation_required') {
							if (indicator) {
								indicator.remove();
								indicator = null;
							}
							// Reset buttons for pause
							sendBtn.style.display = 'inline-flex';
							stopBtn.style.display = 'none';

							if (event.history) {
								history = event.history;
							}

							const confirmed = await appendConfirmationBubble(event.query, event.message);
							if (confirmed) {
								sendMessage(text, event.query);
							} else {
								appendMessage('system', "Opération d'écriture annulée.");
							}
							return;
						} else if (event.type === 'text_chunk') {
							if (indicator) {
								indicator.remove();
								indicator = null;
							}
							if (!streamBubble) {
								streamBubble = appendMessage('model', '', false);
								history.push({ role: 'model', parts: [{ text: '' }] });
							}
							const cd = streamBubble.querySelector('.bubble-content');
							if (cd) {
								const cur = streamBubble.getAttribute('data-raw-text') || '';
								const nw = cur + event.text;
								streamBubble.setAttribute('data-raw-text', nw);
								cd.innerHTML = parseMarkdown(nw);
								const lastMsg = history[history.length - 1];
								if (lastMsg && (lastMsg.role === 'model' || lastMsg.role === 'assistant')) {
									lastMsg.parts = [{ text: nw }];
								}
								saveActiveThread();
								scrollToBottom(false);
							}
						} else if (event.type === 'final_response') {
							if (indicator) {
								indicator.remove();
								indicator = null;
							}
							const raw = event.text || "";
							if (streamBubble) {
								const cd = streamBubble.querySelector('.bubble-content');
								if (cd) cd.innerHTML = parseMarkdown(raw);
							} else {
								appendMessage('model', raw);
							}
							streamBubble = null;

							if (event.history) {
								history = event.history;
								// Double check if the final response is in history
								const lastMsg = history[history.length - 1];
								const textPart = (lastMsg && lastMsg.parts && lastMsg.parts.find(p => p.text)) ? lastMsg.parts.find(p => p.text).text : "";
								const msgText = lastMsg ? (lastMsg.content || textPart || "") : "";
								if (!lastMsg || (lastMsg.role !== 'model' && lastMsg.role !== 'assistant') || !msgText) {
									history.push({ role: 'model', parts: [{ text: raw }] });
								}
							} else {
								let historyText = text;
								if (fileData) historyText = `[Fichier: ${fileData.name}] ${text}`;
								history.push({ role: 'user', parts: [{ text: historyText }] });
								history.push({ role: 'model', parts: [{ text: raw }] });
							}
							saveActiveThread();

							const themeMatch = raw.match(/\[THEME:(dark|light)\]/i);
							if (themeMatch) {
								const requestedTheme = themeMatch[1].toLowerCase();
								const currentTheme = document.documentElement.getAttribute('data-theme') || 'light';
								if (currentTheme !== requestedTheme) {
									const toggleBtn = document.getElementById('themeToggleBtnNavbar');
									if (toggleBtn) {
										toggleBtn.click();
									} else {
										document.documentElement.setAttribute('data-theme', requestedTheme);
										localStorage.setItem('fab_theme', requestedTheme);
									}
								}
							}

							const redirect = raw.match(/\[REDIRECT:([^\]]+)\]/i);
							if (redirect) {
								appendMessage('system', `Redirection vers : ${redirect[1].trim()}...`);
								setTimeout(() => { window.location.href = redirect[1].trim(); }, 1200);
							}
						} else if (event.type === 'error') {
							if (indicator) {
								indicator.remove();
								indicator = null;
							}
							appendMessage('system', event.error || "Erreur.");
						}
					}
				}
			} catch (err) {
				indicator?.remove();
				if (err.name === 'AbortError') {
					appendMessage('system', "Génération interrompue.");
				} else {
					appendMessage('system', "Erreur de connexion avec Sabrina.");
				}
			} finally {
				sendBtn.style.display = 'inline-flex';
				stopBtn.style.display = 'none';
				abortController = null;
				scrollToBottom();
			}
		}

		// ── Event Bindings ──
		input.addEventListener('keydown', function (e) {
			if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(this.value); }
		});
		input.addEventListener('input', function () {
			this.style.height = '36px';
			this.style.height = Math.min(100, this.scrollHeight) + 'px';
		});
		sendBtn.addEventListener('click', () => sendMessage(input.value));
		stopBtn.addEventListener('click', () => abortController?.abort());

		function clearChat() {
			if (window.speechSynthesis) window.speechSynthesis.cancel();
			history = [];
			saveActiveThread();
			chatArea.innerHTML = '';
			localStorage.setItem('fab_chat_expanded', 'false');
			localStorage.setItem('fab_chat_show_settings', 'false');
			hero.classList.remove('chat-active');
			chatArea.classList.remove('active');
		}
		clearBtn?.addEventListener('click', clearChat);

		// File handling
		attachBtn?.addEventListener('click', () => fileInput?.click());
		fileInput?.addEventListener('change', function (e) {
			const file = e.target.files[0];
			if (!file) return;
			selectedFile = file;
			fileName.textContent = file.name;
			if (file.type.startsWith('image/')) {
				fileIcon.innerHTML = '<i class="bi bi-file-earmark-image-fill text-success"></i>';
			} else if (file.type === 'application/pdf') {
				fileIcon.innerHTML = '<i class="bi bi-file-earmark-pdf-fill text-danger"></i>';
			} else {
				fileIcon.innerHTML = '<i class="bi bi-file-earmark-excel-fill text-success"></i>';
			}
			fileChip.classList.add('show');
		});
		removeFile?.addEventListener('click', () => {
			selectedFile = null;
			fileInput.value = '';
			fileChip.classList.remove('show');
		});

		// Copy & Speech bubble click delegation
		chatArea.addEventListener('click', function (e) {
			const copyBtn = e.target.closest('.btn-copy');
			if (copyBtn) {
				const bubble = copyBtn.closest('.fab-chat-bubble');
				if (!bubble) return;
				let t = bubble.getAttribute('data-raw-text') || bubble.innerText;
				const audioMatch = t.match(/^\[AUDIO:([^|]+)\|(.*)\]$/);
				if (audioMatch) {
					t = audioMatch[2] || "Message vocal";
				} else {
					t = t.replace(/[\n\s]*Copier[\n\s]*Lire/g, '').trim();
				}
				navigator.clipboard.writeText(t).then(() => {
					const orig = copyBtn.innerHTML;
					copyBtn.innerHTML = '<i class="bi bi-check2 text-success"></i> Copié';
					setTimeout(() => copyBtn.innerHTML = orig, 2000);
				});
			}
			const speakBtn = e.target.closest('.btn-speak');
			if (speakBtn) {
				const bubble = speakBtn.closest('.fab-chat-bubble');
				if (!bubble) return;
				let t = bubble.getAttribute('data-raw-text') || bubble.innerText;
				const audioMatch = t.match(/^\[AUDIO:([^|]+)\|(.*)\]$/);
				if (audioMatch) {
					t = audioMatch[2] || "Message vocal";
				} else {
					t = t.replace(/[\n\s]*Copier[\n\s]*Lire/g, '').trim();
				}
				if (window.speechSynthesis.speaking) {
					window.speechSynthesis.cancel();
					speakBtn.innerHTML = '<i class="bi bi-volume-up"></i> Lire';
				} else {
					const u = new SpeechSynthesisUtterance(t);
					u.lang = 'fr-FR';
					u.onend = () => speakBtn.innerHTML = '<i class="bi bi-volume-up"></i> Lire';
					window.speechSynthesis.speak(u);
					speakBtn.innerHTML = '<i class="bi bi-volume-mute"></i> Arrêter';
				}
			}
		});

		// 🎤 Voice Input — getUserMedia + MediaRecorder
		// SpeechRecognition (webkitSpeechRecognition) is blocked on http://127.0.0.1 in Chrome 115+
		// so we use MediaRecorder to capture audio and send the blob to the server.
		let mediaRecorder = null;
		let audioChunks = [];
		let isRecording = false;
		let recordTimer = null;
		let recordDuration = 0;
		let localStream = null;

		const hasMediaSupport = !!(navigator.mediaDevices &&
			navigator.mediaDevices.getUserMedia &&
			window.MediaRecorder);

		// Keep the mic button visible so users know the feature exists and get helpful error fallback messages


		function showMicError(msg) {
			if (micBtn) micBtn.innerHTML = '<i class="bi bi-mic"></i>';
			if (soundwave) soundwave.style.display = 'none';
			if (input) {
				input.disabled = false;
				input.placeholder = msg;
				setTimeout(() => { input.placeholder = 'Posez une question à Sabrina...'; }, 5000);
			}
			isRecording = false;
			clearInterval(recordTimer);
			if (localStream) {
				localStream.getTracks().forEach(t => t.stop());
				localStream = null;
			}
		}

		async function startRecording() {
			if (isRecording) return;
			if (!hasMediaSupport) {
				showMicError('⚠️ Le micro nécessite HTTPS ou localhost.');
				return;
			}
			try {
				const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
				localStream = stream;

				// Pick best supported format
				const mimeType = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg']
					.find(t => MediaRecorder.isTypeSupported(t)) || '';
				mediaRecorder = new MediaRecorder(stream, mimeType ? { mimeType } : {});
				audioChunks = [];

				mediaRecorder.ondataavailable = (e) => {
					if (e.data && e.data.size > 0) audioChunks.push(e.data);
				};

				mediaRecorder.onstop = () => {
					const blob = new Blob(audioChunks, { type: mediaRecorder.mimeType || 'audio/webm' });
					const reader = new FileReader();
					reader.onloadend = () => {
						// Server reads the transcript field; audio blob is included for future STT use
						sendMessage(`[AUDIO:${reader.result}|]`);
					};
					reader.readAsDataURL(blob);
					if (localStream) {
						localStream.getTracks().forEach(t => t.stop());
						localStream = null;
					}
				};

				mediaRecorder.start();
				isRecording = true;

				// UI Feedback
				micBtn.innerHTML = '<i class="bi bi-stop-circle-fill text-danger animate-pulse"></i>';
				soundwave.style.display = 'flex';
				input.disabled = true;
				input.value = '';

				const fmt = s => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
				recordDuration = 0;
				input.placeholder = `🎤 Enregistrement... ${fmt(recordDuration)}`;
				recordTimer = setInterval(() => {
					recordDuration++;
					input.placeholder = `🎤 Enregistrement... ${fmt(recordDuration)}`;
					if (recordDuration >= 60) stopRecording(); // max 60s
				}, 1000);

			} catch (err) {
				console.error('getUserMedia error:', err.name, err.message);
				const n = err.name || '';
				if (n === 'NotAllowedError' || n === 'PermissionDeniedError') {
					showMicError('⚠️ Micro refusé — rechargez la page et autorisez le micro.');
				} else if (n === 'NotFoundError' || n === 'DevicesNotFoundError') {
					showMicError('⚠️ Aucun micro détecté — vérifiez votre matériel.');
				} else if (n === 'NotReadableError' || n === 'TrackStartError') {
					showMicError('⚠️ Micro utilisé par une autre app — fermez Zoom/Teams/etc. et réessayez.');
				} else {
					showMicError(`⚠️ Erreur micro : ${n || err.message}`);
				}
			}
		}

		function stopRecording() {
			clearInterval(recordTimer);
			isRecording = false;
			if (mediaRecorder && mediaRecorder.state !== 'inactive') {
				mediaRecorder.stop();
			}
			if (micBtn) micBtn.innerHTML = '<i class="bi bi-mic"></i>';
			if (soundwave) soundwave.style.display = 'none';
			if (input) {
				input.disabled = false;
				input.placeholder = 'Posez une question à Sabrina...';
			}
		}

		micBtn?.addEventListener('click', (e) => {
			e.preventDefault();
			if (isRecording) {
				stopRecording();
			} else {
				startRecording();
			}
		});

		// Auto-restore chat and settings state on page load
		loadActiveThread();
		if (localStorage.getItem('fab_chat_expanded') === 'true' && history.length > 0) {
			showChatView();
			renderHistory();
		}

		input.addEventListener('focus', function () {
			const wasActive = chatArea.classList.contains('active');
			loadActiveThread();
			showChatView();
			if (!wasActive && history.length > 0) {
				renderHistory();
			}
		});

		input.addEventListener('blur', function () {
			// Small timeout to let clicks on buttons or uploads execute first
			setTimeout(() => {
				if (input.value.trim() === "" && history.length === 0) {
					hero.classList.remove('chat-active');
					chatArea.classList.remove('active');
					localStorage.setItem('fab_chat_expanded', 'false');
				}
			}, 200);
		});

		// Auto-collapse empty assistant when clicking outside
		document.addEventListener('mousedown', function (e) {
			if (hero && !hero.contains(e.target)) {
				// Only collapse if the text area is empty and there is no active chat history
				if (input.value.trim() === "" && history.length === 0) {
					hero.classList.remove('chat-active');
					chatArea.classList.remove('active');
					localStorage.setItem('fab_chat_expanded', 'false');
				}
			}
		});
	})();
