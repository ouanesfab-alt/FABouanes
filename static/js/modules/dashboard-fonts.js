// dashboard-fonts.js — Font picker and typography customization
// Extracted from dashboard.html inline <script> block 2


	(function () {
		const FONTS_POOL = [
			// Sans-serif & Modern
			'Outfit', 'Inter', 'Roboto', 'Open Sans', 'Montserrat', 'Lato', 'Poppins', 'Nunito', 'Raleway',
			'Ubuntu', 'Quicksand', 'Exo 2', 'Work Sans', 'Rubik', 'Dosis', 'Cabin', 'Questrial', 'Fira Sans',
			'Titillium Web', 'Oxygen', 'Kanit', 'Manrope', 'Plus Jakarta Sans', 'Lexend', 'Comfortaa', 'Josefin Sans',
			'Fredoka', 'Signika', 'Secular One', 'Varela Round', 'Jost', 'Sen', 'Catamaran', 'Hind Siliguri',
			// Serif & Editorial
			'Playfair Display', 'Lora', 'Merriweather', 'PT Serif', 'Baskervville', 'Cinzel', 'Crimson Text',
			'Libre Baskerville', 'Cardo', 'Vollkorn', 'Domine', 'EB Garamond', 'Arvo', 'Alegreya', 'DM Serif Display',
			'Cormorant Garamond', 'Sorts Mill Goudy', 'Noto Serif', 'Prata', 'Spectral', 'Fraunces', 'Abhaya Libre',
			'Petrona', 'Cinzel Decorative', 'Libre Caslon Display', 'Playfair', 'Zilla Slab', 'Alegreya SC',
			// Artistic, Display & Brand
			'Oswald', 'Bebas Neue', 'Lobster', 'Lobster Two', 'Pacifico', 'Dancing Script', 'Amatic SC', 'Alfa Slab One',
			'Concert One', 'Teko', 'Russo One', 'VT323', 'Luckiest Guy', 'Righteous', 'Orbitron', 'Great Vibes',
			'Sacramento', 'Permanent Marker', 'Caveat', 'Satisfy', 'Kaushan Script', 'Shadows Into Light',
			'Indie Flower', 'Creepster', 'Press Start 2P', 'Acme', 'Patua One', 'Abril Fatface', 'Almarai',
			'Yellowtail', 'Cookie', 'Special Elite', 'Courgette', 'Architects Daughter', 'Bangers', 'Staatliches',
			'Anton', 'Carter One', 'Changa One', 'Chewy', 'Paytone One', 'Titan One', 'Lilita One', 'Sigmar One',
			'Bowlby One SC', 'Ultra', 'Spicy Rice', 'Fredericka the Great', 'Vampiro One', 'Black Ops One',
			'Monoton', 'Audiowide', 'Megrim', 'Plaster', 'Ewert', 'Faster One', 'Fascinate Inline', 'Glass Antiqua',
			'UnifrakturMaguntia', 'Trade Winds', 'Metal Mania', 'Rye', 'Sancreek', 'Kelly Slab', 'Codystar',
			'Freckle Face', 'Slackey', 'Piedra', 'Eater', 'Frijole', 'Smokum', 'Snowburst One', 'Nosifer',
			'Butcherman', 'Germania One', 'New Rocker', 'Barrio', 'Federant', 'Miniver', 'Diplomata', 'Ranchers',
			'Henny Penny', 'Jolly Lodger', 'Geostar', 'Aladin', 'Akronim', 'Shojumaru', 'Arbutus', 'Astloch',
			'Stint Ultra Condensed', 'Stint Ultra Expanded', 'Wallpoet', 'Macondo', 'Bigelow Rules', 'Sirin Stencil',
			'Crete Round', 'Nova Cut', 'Pirata One', 'Overlock', 'Sniglet', 'Love Ya Like A Sister', 'Kenia',
			'Life Savers', 'Modern Antiqua', 'Nova Slim', 'Ceviche One',
			// Calligraphy & Handwriting
			'Reenie Beanie', 'Loved by the King', 'Coming Soon', 'Give You Glory', 'Just Another Hand', 'Kristi',
			'Gochi Hand', 'Patrick Hand', 'Schoolbell', 'Walter Turncoat', 'Rock Salt', 'Covered By Your Grace',
			'Leckerli One', 'Grand Hotel', 'Niconne', 'Montez', 'Pinyon Script', 'Rochester', 'Herr Von Muellerhoff',
			'Mrs Saint Delafield', 'Alex Brush', 'Allura', 'Italianno', 'Mr De Haviland', 'Parisienne', 'Tangerine',
			'Marck Script', 'League Script', 'Calligraffitti', 'Bad Script', 'Cedarville Cursive', 'Homemade Apple',
			'La Belle Aurore', 'Sue Ellen Francisco', 'Nothing You Could Do', 'Waiting for the Sunrise', 'Gloria Hallelujah',
			'Reenie Beanie', 'Over the Rainbow', 'Dawning of a New Day', 'Short Stack', 'Architects Daughter',
			'Neucha', 'Pangolin', 'Zeyada', 'Beth Ellen', 'Loved by the King', 'Amita', 'Kalam', 'Handlee'
		];

		// 50 premium, modern design colors
		const COLORS_POOL = [
			'#2563EB', '#3B82F6', '#0284C7', '#0EA5E9', '#06B6D4', '#0D9488', '#10B981', '#16A34A', '#84CC16', '#EAB308',
			'#F59E0B', '#D97706', '#EA580C', '#F97316', '#EF4444', '#DC2626', '#E11D48', '#F43F5E', '#EC4899', '#D946EF',
			'#C084FC', '#A855F7', '#8B5CF6', '#7C3AED', '#6366F1', '#4F46E5', '#4338CA', '#312E81', '#1E3A8A', '#0F172A',
			'#0D6EFD', '#198754', '#DC3545', '#FFC107', '#0DCAF0', '#6610F2', '#6F42C1', '#D63384', '#FD7E14', '#20C997',
			'#008080', '#00FFFF', '#FF00FF', '#FF7F50', '#6495ED', '#FF8C00', '#483D8B', '#2E8B57', '#8B008B', '#5F9EA0'
		];

		const logoText = document.querySelector('.fab-logo-text-main');
		if (!logoText) return;

		// Cache the original font name
		const defaultFont = "Outfit";
		let loadedFonts = new Set([defaultFont]);
		let currentFontIdx = -1;
		let currentColorIdx = -1;

		// Apply CSS transition properties for beautiful fluid transitions (including color)
		logoText.style.transition = 'opacity 0.3s ease, font-family 0.3s ease, color 0.8s ease';

		// Retrieve script CSP nonce if present
		const nonce = document.querySelector('script[nonce]')?.getAttribute('nonce') || '';

		function rotateFont() {
			if (FONTS_POOL.length <= 1) return;
			let randomIdx;
			do {
				randomIdx = Math.floor(Math.random() * FONTS_POOL.length);
			} while (randomIdx === currentFontIdx);
			currentFontIdx = randomIdx;
			const nextFont = FONTS_POOL[randomIdx];

			const fontId = `gfont-${nextFont.replace(/\s+/g, '-').toLowerCase()}`;

			const applyFontChange = () => {
				logoText.style.opacity = '0.08';
				setTimeout(() => {
					logoText.style.fontFamily = `"${nextFont}", system-ui, sans-serif`;
					logoText.style.opacity = '1';
				}, 300);
			};

			// If already loaded, transition directly
			if (document.getElementById(fontId) || loadedFonts.has(nextFont)) {
				applyFontChange();
				return;
			}

			// Load dynamically
			const link = document.createElement('link');
			link.id = fontId;
			link.rel = 'stylesheet';
			link.href = `https://fonts.googleapis.com/css2?family=${encodeURIComponent(nextFont)}:wght@400;700;900&display=swap`;
			if (nonce) {
				link.setAttribute('nonce', nonce);
			}

			link.onload = () => {
				loadedFonts.add(nextFont);
				if (document.fonts && document.fonts.load) {
					document.fonts.load(`900 1em "${nextFont}"`)
						.then(applyFontChange)
						.catch(applyFontChange);
				} else {
					applyFontChange();
				}
			};

			link.onerror = () => {
				applyFontChange();
			};

			document.head.appendChild(link);
		}

		function rotateColor() {
			if (COLORS_POOL.length <= 1) return;
			let randomIdx;
			do {
				randomIdx = Math.floor(Math.random() * COLORS_POOL.length);
			} while (randomIdx === currentColorIdx);
			currentColorIdx = randomIdx;
			const nextColor = COLORS_POOL[randomIdx];
			// Inline color style overrides both stylesheet color and dark mode colors
			logoText.style.setProperty('color', nextColor, 'important');
		}

		// Trigger immediately on load
		rotateFont();
		rotateColor();

		// Rotates the font every 60 seconds
		setInterval(rotateFont, 60000);

		// Rotates the color every 50 seconds
		setInterval(rotateColor, 50000);
	})();

	// ─── Mobile Hero Clock ───────────────────────────────────────
	(function mobileHeroClock() {
		const timeEl = document.getElementById('mobileClockTime');
		const dateEl = document.getElementById('mobileClockDate');
		if (!timeEl && !dateEl) return;

		const DAYS_FR = ['Dim.', 'Lun.', 'Mar.', 'Mer.', 'Jeu.', 'Ven.', 'Sam.'];
		const MONTHS_FR = ['Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Jun', 'Jul', 'Aoû', 'Sep', 'Oct', 'Nov', 'Déc'];

		// Rotating accent colors — matches the desktop clock palette
		const CLOCK_COLORS = [
			'#2563EB', '#0EA5E9', '#10B981', '#F59E0B', '#EF4444', '#D946EF', '#8B5CF6', '#F97316', '#0D9488'
		];
		let colorIdx = 0;

		function tick() {
			const now = new Date();
			const hh = String(now.getHours()).padStart(2, '0');
			const mm = String(now.getMinutes()).padStart(2, '0');

			if (timeEl) {
				timeEl.textContent = `${hh}:${mm}`;
				// Rotate color every minute
				if (now.getSeconds() === 0) {
					colorIdx = (colorIdx + 1) % CLOCK_COLORS.length;
					timeEl.style.color = CLOCK_COLORS[colorIdx];
					const badge = document.getElementById('mobileClockBadge');
					if (badge) {
						badge.style.borderColor = CLOCK_COLORS[colorIdx] + '30';
						badge.style.background = CLOCK_COLORS[colorIdx] + '12';
					}
				}
			}

			if (dateEl) {
				const day = DAYS_FR[now.getDay()];
				const d = now.getDate();
				const month = MONTHS_FR[now.getMonth()];
				dateEl.textContent = `${day} ${d} ${month}`;
			}
		}

		// Initialize immediately, then every second
		tick();
		setInterval(tick, 1000);
	})();
