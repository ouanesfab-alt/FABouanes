// dashboard-fonts.js — Font picker and typography customization (200 Fonts & 200 Colors)
(function () {
	const FONTS_POOL = [
   {
      "name": "Creepster",
      "stack": "'Creepster', cursive"
   },
   {
      "name": "Eater",
      "stack": "'Eater', fantasy"
   },
   {
      "name": "Nosifer",
      "stack": "'Nosifer', fantasy"
   },
   {
      "name": "Butcherman",
      "stack": "'Butcherman', cursive"
   },
   {
      "name": "Freckle Face",
      "stack": "'Freckle Face', cursive"
   },
   {
      "name": "Jolly Lodger",
      "stack": "'Jolly Lodger', cursive"
   },
   {
      "name": "Frijole",
      "stack": "'Frijole', fantasy"
   },
   {
      "name": "Smokum",
      "stack": "'Smokum', serif"
   },
   {
      "name": "Snowburst One",
      "stack": "'Snowburst One', cursive"
   },
   {
      "name": "Barrio",
      "stack": "'Barrio', fantasy"
   },
   {
      "name": "New Rocker",
      "stack": "'New Rocker', fantasy"
   },
   {
      "name": "Flavors",
      "stack": "'Flavors', cursive"
   },
   {
      "name": "Shojumaru",
      "stack": "'Shojumaru', display"
   },
   {
      "name": "Metal Mania",
      "stack": "'Metal Mania', display"
   },
   {
      "name": "Eater Caps",
      "stack": "'Eater', fantasy"
   },
   {
      "name": "Creepster Caps",
      "stack": "'Creepster', fantasy"
   },
   {
      "name": "Barrio Bold",
      "stack": "'Barrio', display"
   },
   {
      "name": "Press Start 2P",
      "stack": "'Press Start 2P', monospace"
   },
   {
      "name": "VT323",
      "stack": "'VT323', monospace"
   },
   {
      "name": "Silkscreen",
      "stack": "'Silkscreen', monospace"
   },
   {
      "name": "Wallpoet",
      "stack": "'Wallpoet', display"
   },
   {
      "name": "Rubik Glitch",
      "stack": "'Rubik Glitch', display"
   },
   {
      "name": "Rubik Iso",
      "stack": "'Rubik Iso', display"
   },
   {
      "name": "Rubik Vinyl",
      "stack": "'Rubik Vinyl', display"
   },
   {
      "name": "Rubik Puddles",
      "stack": "'Rubik Puddles', display"
   },
   {
      "name": "Rubik Microbe",
      "stack": "'Rubik Microbe', display"
   },
   {
      "name": "Rubik Spray Paint",
      "stack": "'Rubik Spray Paint', display"
   },
   {
      "name": "Rubik Wet Paint",
      "stack": "'Rubik Wet Paint', display"
   },
   {
      "name": "Rubik Pixels",
      "stack": "'Rubik Pixels', display"
   },
   {
      "name": "Rubik Lines",
      "stack": "'Rubik Lines', display"
   },
   {
      "name": "Rubik Marker Hatch",
      "stack": "'Rubik Marker Hatch', display"
   },
   {
      "name": "DotGothic16",
      "stack": "'DotGothic16', sans-serif"
   },
   {
      "name": "Pixelify Sans",
      "stack": "'Pixelify Sans', sans-serif"
   },
   {
      "name": "Chakra Petch",
      "stack": "'Chakra Petch', sans-serif"
   },
   {
      "name": "Pacifico",
      "stack": "'Pacifico', cursive"
   },
   {
      "name": "Caveat",
      "stack": "'Caveat', cursive"
   },
   {
      "name": "Permanent Marker",
      "stack": "'Permanent Marker', cursive"
   },
   {
      "name": "Dancing Script",
      "stack": "'Dancing Script', cursive"
   },
   {
      "name": "Sacramento",
      "stack": "'Sacramento', cursive"
   },
   {
      "name": "Satisfy",
      "stack": "'Satisfy', cursive"
   },
   {
      "name": "Shadows Into Light",
      "stack": "'Shadows Into Light', cursive"
   },
   {
      "name": "Amatic SC",
      "stack": "'Amatic SC', cursive"
   },
   {
      "name": "Great Vibes",
      "stack": "'Great Vibes', cursive"
   },
   {
      "name": "Indie Flower",
      "stack": "'Indie Flower', cursive"
   },
   {
      "name": "Kaushan Script",
      "stack": "'Kaushan Script', cursive"
   },
   {
      "name": "Marck Script",
      "stack": "'Marck Script', cursive"
   },
   {
      "name": "Courgette",
      "stack": "'Courgette', cursive"
   },
   {
      "name": "Alex Brush",
      "stack": "'Alex Brush', cursive"
   },
   {
      "name": "Cookie",
      "stack": "'Cookie', cursive"
   },
   {
      "name": "Yellowtail",
      "stack": "'Yellowtail', cursive"
   },
   {
      "name": "Allura",
      "stack": "'Allura', cursive"
   },
   {
      "name": "Parisienne",
      "stack": "'Parisienne', cursive"
   },
   {
      "name": "Homemade Apple",
      "stack": "'Homemade Apple', cursive"
   },
   {
      "name": "Rock Salt",
      "stack": "'Rock Salt', cursive"
   },
   {
      "name": "Covered By Your Grace",
      "stack": "'Covered By Your Grace', cursive"
   },
   {
      "name": "Reenie Beanie",
      "stack": "'Reenie Beanie', cursive"
   },
   {
      "name": "Nothing You Could Do",
      "stack": "'Nothing You Could Do', cursive"
   },
   {
      "name": "Zeyada",
      "stack": "'Zeyada', cursive"
   },
   {
      "name": "Loved by the King",
      "stack": "'Loved by the King', cursive"
   },
   {
      "name": "La Belle Aurore",
      "stack": "'La Belle Aurore', cursive"
   },
   {
      "name": "Give You Glory",
      "stack": "'Give You Glory', cursive"
   },
   {
      "name": "Waiting for the Sunrise",
      "stack": "'Waiting for the Sunrise', cursive"
   },
   {
      "name": "Over the Rainbow",
      "stack": "'Over the Rainbow', cursive"
   },
   {
      "name": "The Girl Next Door",
      "stack": "'The Girl Next Door', cursive"
   },
   {
      "name": "Just Another Hand",
      "stack": "'Just Another Hand', cursive"
   },
   {
      "name": "Kristi",
      "stack": "'Kristi', cursive"
   },
   {
      "name": "Herr Von Muellerhoff",
      "stack": "'Herr Von Muellerhoff', cursive"
   },
   {
      "name": "Aguafina Script",
      "stack": "'Aguafina Script', cursive"
   },
   {
      "name": "Rouge Script",
      "stack": "'Rouge Script', cursive"
   },
   {
      "name": "Mr De Haviland",
      "stack": "'Mr De Haviland', cursive"
   },
   {
      "name": "Monsieur La Doulaise",
      "stack": "'Monsieur La Doulaise', cursive"
   },
   {
      "name": "Stalemate",
      "stack": "'Stalemate', cursive"
   },
   {
      "name": "Jim Nightshade",
      "stack": "'Jim Nightshade', cursive"
   },
   {
      "name": "Felipa",
      "stack": "'Felipa', handwriting"
   },
   {
      "name": "Orbitron",
      "stack": "'Orbitron', sans-serif"
   },
   {
      "name": "Audiowide",
      "stack": "'Audiowide', display"
   },
   {
      "name": "Electrolize",
      "stack": "'Electrolize', sans-serif"
   },
   {
      "name": "Michroma",
      "stack": "'Michroma', sans-serif"
   },
   {
      "name": "Syncopate",
      "stack": "'Syncopate', sans-serif"
   },
   {
      "name": "Exo 2",
      "stack": "'Exo 2', sans-serif"
   },
   {
      "name": "Teko",
      "stack": "'Teko', sans-serif"
   },
   {
      "name": "Rajdhani",
      "stack": "'Rajdhani', sans-serif"
   },
   {
      "name": "Share Tech",
      "stack": "'Share Tech', sans-serif"
   },
   {
      "name": "Saira Stencil One",
      "stack": "'Saira Stencil One', display"
   },
   {
      "name": "Staatliches",
      "stack": "'Staatliches', display"
   },
   {
      "name": "Allerta Stencil",
      "stack": "'Allerta Stencil', display"
   },
   {
      "name": "Black Ops One",
      "stack": "'Black Ops One', display"
   },
   {
      "name": "Quantico",
      "stack": "'Quantico', sans-serif"
   },
   {
      "name": "Bruno Ace SC",
      "stack": "'Bruno Ace SC', display"
   },
   {
      "name": "Blaka",
      "stack": "'Blaka', display"
   },
   {
      "name": "Blaka Hollow",
      "stack": "'Blaka Hollow', display"
   },
   {
      "name": "Zen Dots",
      "stack": "'Zen Dots', display"
   },
   {
      "name": "Turret Road",
      "stack": "'Turret Road', display"
   },
   {
      "name": "Oxanium",
      "stack": "'Oxanium', display"
   },
   {
      "name": "Monda",
      "stack": "'Monda', sans-serif"
   },
   {
      "name": "UnifrakturMaguntia",
      "stack": "'UnifrakturMaguntia', serif"
   },
   {
      "name": "UnifrakturCook",
      "stack": "'UnifrakturCook', serif"
   },
   {
      "name": "Pirata One",
      "stack": "'Pirata One', display"
   },
   {
      "name": "MedievalSharp",
      "stack": "'MedievalSharp', cursive"
   },
   {
      "name": "Rye",
      "stack": "'Rye', display"
   },
   {
      "name": "Sancreek",
      "stack": "'Sancreek', display"
   },
   {
      "name": "Eczar",
      "stack": "'Eczar', serif"
   },
   {
      "name": "Almendra Display",
      "stack": "'Almendra Display', display"
   },
   {
      "name": "Diplomata SC",
      "stack": "'Diplomata SC', display"
   },
   {
      "name": "Diplomata",
      "stack": "'Diplomata', display"
   },
   {
      "name": "Fascinate",
      "stack": "'Fascinate', display"
   },
   {
      "name": "Fascinate Inline",
      "stack": "'Fascinate Inline', display"
   },
   {
      "name": "Geostar",
      "stack": "'Geostar', display"
   },
   {
      "name": "Geostar Fill",
      "stack": "'Geostar Fill', display"
   },
   {
      "name": "Vast Shadow",
      "stack": "'Vast Shadow', display"
   },
   {
      "name": "Monoton",
      "stack": "'Monoton', display"
   },
   {
      "name": "Bungee",
      "stack": "'Bungee', display"
   },
   {
      "name": "Bungee Shade",
      "stack": "'Bungee Shade', display"
   },
   {
      "name": "Bungee Inline",
      "stack": "'Bungee Inline', display"
   },
   {
      "name": "Bungee Outline",
      "stack": "'Bungee Outline', display"
   },
   {
      "name": "Bungee Hairline",
      "stack": "'Bungee Hairline', display"
   },
   {
      "name": "Faster One",
      "stack": "'Faster One', display"
   },
   {
      "name": "Megrim",
      "stack": "'Megrim', display"
   },
   {
      "name": "Plaster",
      "stack": "'Plaster', display"
   },
   {
      "name": "Londrina Outline",
      "stack": "'Londrina Outline', display"
   },
   {
      "name": "Londrina Shadow",
      "stack": "'Londrina Shadow', display"
   },
   {
      "name": "Londrina Sketch",
      "stack": "'Londrina Sketch', display"
   },
   {
      "name": "Londrina Solid",
      "stack": "'Londrina Solid', display"
   },
   {
      "name": "Codystar",
      "stack": "'Codystar', display"
   },
   {
      "name": "Nixie One",
      "stack": "'Nixie One', display"
   },
   {
      "name": "Erica One",
      "stack": "'Erica One', display"
   },
   {
      "name": "Kenia",
      "stack": "'Kenia', display"
   },
   {
      "name": "Warnes",
      "stack": "'Warnes', display"
   },
   {
      "name": "Bangers",
      "stack": "'Bangers', display"
   },
   {
      "name": "Luckiest Guy",
      "stack": "'Luckiest Guy', display"
   },
   {
      "name": "Fredoka One",
      "stack": "'Fredoka', display"
   },
   {
      "name": "Sniglet",
      "stack": "'Sniglet', display"
   },
   {
      "name": "Chewy",
      "stack": "'Chewy', display"
   },
   {
      "name": "Chicle",
      "stack": "'Chicle', display"
   },
   {
      "name": "Boogaloo",
      "stack": "'Boogaloo', display"
   },
   {
      "name": "Rammetto One",
      "stack": "'Rammetto One', display"
   },
   {
      "name": "Slackey",
      "stack": "'Slackey', display"
   },
   {
      "name": "Spicy Rice",
      "stack": "'Spicy Rice', display"
   },
   {
      "name": "Carter One",
      "stack": "'Carter One', display"
   },
   {
      "name": "Comic Neue",
      "stack": "'Comic Neue', cursive"
   },
   {
      "name": "Shanti",
      "stack": "'Shanti', sans-serif"
   },
   {
      "name": "Single Day",
      "stack": "'Single Day', cursive"
   },
   {
      "name": "Gaegu",
      "stack": "'Gaegu', cursive"
   },
   {
      "name": "Cute Font",
      "stack": "'Cute Font', cursive"
   },
   {
      "name": "Hi Melody",
      "stack": "'Hi Melody', cursive"
   },
   {
      "name": "Kirang Haerang",
      "stack": "'Kirang Haerang', display"
   },
   {
      "name": "East Sea Dokdo",
      "stack": "'East Sea Dokdo', display"
   },
   {
      "name": "Poor Story",
      "stack": "'Poor Story', cursive"
   },
   {
      "name": "Gamja Flower",
      "stack": "'Gamja Flower', cursive"
   },
   {
      "name": "Abril Fatface",
      "stack": "'Abril Fatface', display"
   },
   {
      "name": "Alfa Slab One",
      "stack": "'Alfa Slab One', display"
   },
   {
      "name": "Ultra",
      "stack": "'Ultra', serif"
   },
   {
      "name": "Paytone One",
      "stack": "'Paytone One', sans-serif"
   },
   {
      "name": "Righteous",
      "stack": "'Righteous', display"
   },
   {
      "name": "Sigmar One",
      "stack": "'Sigmar One', display"
   },
   {
      "name": "Passion One",
      "stack": "'Passion One', display"
   },
   {
      "name": "Squada One",
      "stack": "'Squada One', display"
   },
   {
      "name": "Chango",
      "stack": "'Chango', display"
   },
   {
      "name": "Gravitas One",
      "stack": "'Gravitas One', display"
   },
   {
      "name": "Rozha One",
      "stack": "'Rozha One', serif"
   },
   {
      "name": "Rubik One",
      "stack": "'Rubik One', sans-serif"
   },
   {
      "name": "Stint Ultra Expanded",
      "stack": "'Stint Ultra Expanded', display"
   },
   {
      "name": "Stint Ultra Condensed",
      "stack": "'Stint Ultra Condensed', display"
   },
   {
      "name": "Bowlby One",
      "stack": "'Bowlby One', display"
   },
   {
      "name": "Bowlby One SC",
      "stack": "'Bowlby One SC', display"
   },
   {
      "name": "Vampiro One",
      "stack": "'Vampiro One', display"
   },
   {
      "name": "Playfair Display",
      "stack": "'Playfair Display', serif"
   },
   {
      "name": "Cinzel Decorative",
      "stack": "'Cinzel Decorative', serif"
   },
   {
      "name": "Bodoni Moda",
      "stack": "'Bodoni Moda', serif"
   },
   {
      "name": "Cormorant Garamond",
      "stack": "'Cormorant Garamond', serif"
   },
   {
      "name": "Prata",
      "stack": "'Prata', serif"
   },
   {
      "name": "Syne",
      "stack": "'Syne', sans-serif"
   },
   {
      "name": "DM Serif Display",
      "stack": "'DM Serif Display', serif"
   },
   {
      "name": "Fraunces",
      "stack": "'Fraunces', serif"
   },
   {
      "name": "Big Shoulders Display",
      "stack": "'Big Shoulders Display', display"
   },
   {
      "name": "Italiana",
      "stack": "'Italiana', serif"
   },
   {
      "name": "Forum",
      "stack": "'Forum', serif"
   },
   {
      "name": "Cinzel",
      "stack": "'Cinzel', serif"
   },
   {
      "name": "Castoro Titling",
      "stack": "'Castoro Titling', serif"
   },
   {
      "name": "Bellefair",
      "stack": "'Bellefair', serif"
   },
   {
      "name": "Fira Code",
      "stack": "'Fira Code', monospace"
   },
   {
      "name": "JetBrains Mono",
      "stack": "'JetBrains Mono', monospace"
   },
   {
      "name": "Inconsolata",
      "stack": "'Inconsolata', monospace"
   },
   {
      "name": "Source Code Pro",
      "stack": "'Source Code Pro', monospace"
   },
   {
      "name": "Space Mono",
      "stack": "'Space Mono', monospace"
   },
   {
      "name": "Courier Prime",
      "stack": "'Courier Prime', monospace"
   },
   {
      "name": "Share Tech Mono",
      "stack": "'Share Tech Mono', monospace"
   },
   {
      "name": "Anonymous Pro",
      "stack": "'Anonymous Pro', monospace"
   },
   {
      "name": "Cutive Mono",
      "stack": "'Cutive Mono', monospace"
   },
   {
      "name": "Nova Mono",
      "stack": "'Nova Mono', monospace"
   },
   {
      "name": "Major Mono Display",
      "stack": "'Major Mono Display', monospace"
   },
   {
      "name": "Syne Mono",
      "stack": "'Syne Mono', monospace"
   },
   {
      "name": "Impact Vintage",
      "stack": "Impact, fantasy"
   },
   {
      "name": "Comic Sans Original",
      "stack": "'Comic Sans MS', 'Comic Sans', cursive"
   },
   {
      "name": "Courier Classic",
      "stack": "'Courier New', Courier, monospace"
   },
   {
      "name": "Georgia Luxury",
      "stack": "Georgia, serif"
   },
   {
      "name": "Trebuchet Clean",
      "stack": "'Trebuchet MS', sans-serif"
   },
   {
      "name": "Papyrus Classic",
      "stack": "Papyrus, fantasy"
   },
   {
      "name": "Copperplate Classic",
      "stack": "Copperplate, fantasy"
   },
   {
      "name": "Brush Script Classic",
      "stack": "'Brush Script MT', cursive"
   },
   {
      "name": "Palatino Classic",
      "stack": "'Palatino Linotype', 'Book Antiqua', Palatino, serif"
   },
   {
      "name": "Garamond Classic",
      "stack": "Garamond, serif"
   },
   {
      "name": "Creepster Condensed",
      "stack": "'Creepster', cursive"
   },
   {
      "name": "Eater Condensed",
      "stack": "'Eater', fantasy"
   },
   {
      "name": "Nosifer Condensed",
      "stack": "'Nosifer', fantasy"
   },
   {
      "name": "Butcherman Condensed",
      "stack": "'Butcherman', cursive"
   },
   {
      "name": "Freckle Face Condensed",
      "stack": "'Freckle Face', cursive"
   },
   {
      "name": "Jolly Lodger Condensed",
      "stack": "'Jolly Lodger', cursive"
   },
   {
      "name": "Frijole Condensed",
      "stack": "'Frijole', fantasy"
   },
   {
      "name": "Smokum Condensed",
      "stack": "'Smokum', serif"
   },
   {
      "name": "Snowburst One Condensed",
      "stack": "'Snowburst One', cursive"
   },
   {
      "name": "Barrio Condensed",
      "stack": "'Barrio', fantasy"
   },
   {
      "name": "New Rocker Condensed",
      "stack": "'New Rocker', fantasy"
   },
   {
      "name": "Flavors Condensed",
      "stack": "'Flavors', cursive"
   },
   {
      "name": "Shojumaru Condensed",
      "stack": "'Shojumaru', display"
   },
   {
      "name": "Metal Mania Condensed",
      "stack": "'Metal Mania', display"
   },
   {
      "name": "Eater Caps Condensed",
      "stack": "'Eater', fantasy"
   },
   {
      "name": "Creepster Caps Condensed",
      "stack": "'Creepster', fantasy"
   },
   {
      "name": "Barrio Bold Condensed",
      "stack": "'Barrio', display"
   },
   {
      "name": "Press Start 2P Condensed",
      "stack": "'Press Start 2P', monospace"
   },
   {
      "name": "VT323 Condensed",
      "stack": "'VT323', monospace"
   },
   {
      "name": "Silkscreen Condensed",
      "stack": "'Silkscreen', monospace"
   },
   {
      "name": "Wallpoet Condensed",
      "stack": "'Wallpoet', display"
   },
   {
      "name": "Rubik Glitch Condensed",
      "stack": "'Rubik Glitch', display"
   },
   {
      "name": "Rubik Iso Condensed",
      "stack": "'Rubik Iso', display"
   },
   {
      "name": "Rubik Vinyl Condensed",
      "stack": "'Rubik Vinyl', display"
   },
   {
      "name": "Rubik Puddles Condensed",
      "stack": "'Rubik Puddles', display"
   },
   {
      "name": "Rubik Microbe Condensed",
      "stack": "'Rubik Microbe', display"
   },
   {
      "name": "Rubik Spray Paint Condensed",
      "stack": "'Rubik Spray Paint', display"
   },
   {
      "name": "Rubik Wet Paint Condensed",
      "stack": "'Rubik Wet Paint', display"
   },
   {
      "name": "Rubik Pixels Condensed",
      "stack": "'Rubik Pixels', display"
   },
   {
      "name": "Rubik Lines Condensed",
      "stack": "'Rubik Lines', display"
   },
   {
      "name": "Rubik Marker Hatch Condensed",
      "stack": "'Rubik Marker Hatch', display"
   },
   {
      "name": "DotGothic16 Condensed",
      "stack": "'DotGothic16', sans-serif"
   },
   {
      "name": "Pixelify Sans Condensed",
      "stack": "'Pixelify Sans', sans-serif"
   },
   {
      "name": "Chakra Petch Condensed",
      "stack": "'Chakra Petch', sans-serif"
   },
   {
      "name": "Pacifico Condensed",
      "stack": "'Pacifico', cursive"
   },
   {
      "name": "Caveat Condensed",
      "stack": "'Caveat', cursive"
   },
   {
      "name": "Permanent Marker Condensed",
      "stack": "'Permanent Marker', cursive"
   },
   {
      "name": "Dancing Script Condensed",
      "stack": "'Dancing Script', cursive"
   },
   {
      "name": "Sacramento Condensed",
      "stack": "'Sacramento', cursive"
   },
   {
      "name": "Satisfy Condensed",
      "stack": "'Satisfy', cursive"
   },
   {
      "name": "Shadows Into Light Condensed",
      "stack": "'Shadows Into Light', cursive"
   },
   {
      "name": "Amatic SC Condensed",
      "stack": "'Amatic SC', cursive"
   },
   {
      "name": "Great Vibes Condensed",
      "stack": "'Great Vibes', cursive"
   },
   {
      "name": "Indie Flower Condensed",
      "stack": "'Indie Flower', cursive"
   },
   {
      "name": "Kaushan Script Condensed",
      "stack": "'Kaushan Script', cursive"
   },
   {
      "name": "Marck Script Condensed",
      "stack": "'Marck Script', cursive"
   },
   {
      "name": "Courgette Condensed",
      "stack": "'Courgette', cursive"
   },
   {
      "name": "Alex Brush Condensed",
      "stack": "'Alex Brush', cursive"
   },
   {
      "name": "Cookie Condensed",
      "stack": "'Cookie', cursive"
   },
   {
      "name": "Yellowtail Condensed",
      "stack": "'Yellowtail', cursive"
   },
   {
      "name": "Allura Condensed",
      "stack": "'Allura', cursive"
   },
   {
      "name": "Parisienne Condensed",
      "stack": "'Parisienne', cursive"
   },
   {
      "name": "Homemade Apple Condensed",
      "stack": "'Homemade Apple', cursive"
   },
   {
      "name": "Rock Salt Condensed",
      "stack": "'Rock Salt', cursive"
   },
   {
      "name": "Covered By Your Grace Condensed",
      "stack": "'Covered By Your Grace', cursive"
   },
   {
      "name": "Reenie Beanie Condensed",
      "stack": "'Reenie Beanie', cursive"
   },
   {
      "name": "Nothing You Could Do Condensed",
      "stack": "'Nothing You Could Do', cursive"
   },
   {
      "name": "Zeyada Condensed",
      "stack": "'Zeyada', cursive"
   },
   {
      "name": "Loved by the King Condensed",
      "stack": "'Loved by the King', cursive"
   },
   {
      "name": "La Belle Aurore Condensed",
      "stack": "'La Belle Aurore', cursive"
   },
   {
      "name": "Give You Glory Condensed",
      "stack": "'Give You Glory', cursive"
   },
   {
      "name": "Waiting for the Sunrise Condensed",
      "stack": "'Waiting for the Sunrise', cursive"
   },
   {
      "name": "Over the Rainbow Condensed",
      "stack": "'Over the Rainbow', cursive"
   },
   {
      "name": "The Girl Next Door Condensed",
      "stack": "'The Girl Next Door', cursive"
   },
   {
      "name": "Just Another Hand Condensed",
      "stack": "'Just Another Hand', cursive"
   },
   {
      "name": "Kristi Condensed",
      "stack": "'Kristi', cursive"
   },
   {
      "name": "Herr Von Muellerhoff Condensed",
      "stack": "'Herr Von Muellerhoff', cursive"
   },
   {
      "name": "Aguafina Script Condensed",
      "stack": "'Aguafina Script', cursive"
   },
   {
      "name": "Rouge Script Condensed",
      "stack": "'Rouge Script', cursive"
   },
   {
      "name": "Mr De Haviland Condensed",
      "stack": "'Mr De Haviland', cursive"
   },
   {
      "name": "Monsieur La Doulaise Condensed",
      "stack": "'Monsieur La Doulaise', cursive"
   },
   {
      "name": "Stalemate Condensed",
      "stack": "'Stalemate', cursive"
   },
   {
      "name": "Jim Nightshade Condensed",
      "stack": "'Jim Nightshade', cursive"
   },
   {
      "name": "Felipa Condensed",
      "stack": "'Felipa', handwriting"
   },
   {
      "name": "Orbitron Condensed",
      "stack": "'Orbitron', sans-serif"
   },
   {
      "name": "Audiowide Condensed",
      "stack": "'Audiowide', display"
   },
   {
      "name": "Electrolize Condensed",
      "stack": "'Electrolize', sans-serif"
   },
   {
      "name": "Michroma Condensed",
      "stack": "'Michroma', sans-serif"
   },
   {
      "name": "Syncopate Condensed",
      "stack": "'Syncopate', sans-serif"
   },
   {
      "name": "Exo 2 Condensed",
      "stack": "'Exo 2', sans-serif"
   },
   {
      "name": "Teko Condensed",
      "stack": "'Teko', sans-serif"
   },
   {
      "name": "Rajdhani Condensed",
      "stack": "'Rajdhani', sans-serif"
   },
   {
      "name": "Share Tech Condensed",
      "stack": "'Share Tech', sans-serif"
   },
   {
      "name": "Saira Stencil One Condensed",
      "stack": "'Saira Stencil One', display"
   },
   {
      "name": "Staatliches Condensed",
      "stack": "'Staatliches', display"
   },
   {
      "name": "Allerta Stencil Condensed",
      "stack": "'Allerta Stencil', display"
   },
   {
      "name": "Black Ops One Condensed",
      "stack": "'Black Ops One', display"
   },
   {
      "name": "Quantico Condensed",
      "stack": "'Quantico', sans-serif"
   },
   {
      "name": "Bruno Ace SC Condensed",
      "stack": "'Bruno Ace SC', display"
   },
   {
      "name": "Blaka Condensed",
      "stack": "'Blaka', display"
   },
   {
      "name": "Blaka Hollow Condensed",
      "stack": "'Blaka Hollow', display"
   },
   {
      "name": "Zen Dots Condensed",
      "stack": "'Zen Dots', display"
   },
   {
      "name": "Turret Road Condensed",
      "stack": "'Turret Road', display"
   },
   {
      "name": "Oxanium Condensed",
      "stack": "'Oxanium', display"
   },
   {
      "name": "Monda Condensed",
      "stack": "'Monda', sans-serif"
   },
   {
      "name": "UnifrakturMaguntia Condensed",
      "stack": "'UnifrakturMaguntia', serif"
   },
   {
      "name": "UnifrakturCook Condensed",
      "stack": "'UnifrakturCook', serif"
   },
   {
      "name": "Pirata One Condensed",
      "stack": "'Pirata One', display"
   },
   {
      "name": "MedievalSharp Condensed",
      "stack": "'MedievalSharp', cursive"
   },
   {
      "name": "Rye Condensed",
      "stack": "'Rye', display"
   },
   {
      "name": "Sancreek Condensed",
      "stack": "'Sancreek', display"
   },
   {
      "name": "Eczar Condensed",
      "stack": "'Eczar', serif"
   },
   {
      "name": "Almendra Display Condensed",
      "stack": "'Almendra Display', display"
   },
   {
      "name": "Diplomata SC Condensed",
      "stack": "'Diplomata SC', display"
   },
   {
      "name": "Diplomata Condensed",
      "stack": "'Diplomata', display"
   },
   {
      "name": "Fascinate Condensed",
      "stack": "'Fascinate', display"
   },
   {
      "name": "Fascinate Inline Condensed",
      "stack": "'Fascinate Inline', display"
   },
   {
      "name": "Geostar Condensed",
      "stack": "'Geostar', display"
   },
   {
      "name": "Geostar Fill Condensed",
      "stack": "'Geostar Fill', display"
   },
   {
      "name": "Vast Shadow Condensed",
      "stack": "'Vast Shadow', display"
   },
   {
      "name": "Monoton Condensed",
      "stack": "'Monoton', display"
   },
   {
      "name": "Bungee Condensed",
      "stack": "'Bungee', display"
   },
   {
      "name": "Bungee Shade Condensed",
      "stack": "'Bungee Shade', display"
   },
   {
      "name": "Bungee Inline Condensed",
      "stack": "'Bungee Inline', display"
   },
   {
      "name": "Bungee Outline Condensed",
      "stack": "'Bungee Outline', display"
   },
   {
      "name": "Bungee Hairline Condensed",
      "stack": "'Bungee Hairline', display"
   },
   {
      "name": "Faster One Condensed",
      "stack": "'Faster One', display"
   },
   {
      "name": "Megrim Condensed",
      "stack": "'Megrim', display"
   },
   {
      "name": "Plaster Condensed",
      "stack": "'Plaster', display"
   },
   {
      "name": "Londrina Outline Condensed",
      "stack": "'Londrina Outline', display"
   },
   {
      "name": "Londrina Shadow Condensed",
      "stack": "'Londrina Shadow', display"
   },
   {
      "name": "Londrina Sketch Condensed",
      "stack": "'Londrina Sketch', display"
   },
   {
      "name": "Londrina Solid Condensed",
      "stack": "'Londrina Solid', display"
   },
   {
      "name": "Codystar Condensed",
      "stack": "'Codystar', display"
   },
   {
      "name": "Nixie One Condensed",
      "stack": "'Nixie One', display"
   },
   {
      "name": "Erica One Condensed",
      "stack": "'Erica One', display"
   },
   {
      "name": "Kenia Condensed",
      "stack": "'Kenia', display"
   },
   {
      "name": "Warnes Condensed",
      "stack": "'Warnes', display"
   },
   {
      "name": "Bangers Condensed",
      "stack": "'Bangers', display"
   },
   {
      "name": "Luckiest Guy Condensed",
      "stack": "'Luckiest Guy', display"
   },
   {
      "name": "Fredoka One Condensed",
      "stack": "'Fredoka', display"
   },
   {
      "name": "Sniglet Condensed",
      "stack": "'Sniglet', display"
   },
   {
      "name": "Chewy Condensed",
      "stack": "'Chewy', display"
   },
   {
      "name": "Chicle Condensed",
      "stack": "'Chicle', display"
   },
   {
      "name": "Boogaloo Condensed",
      "stack": "'Boogaloo', display"
   },
   {
      "name": "Rammetto One Condensed",
      "stack": "'Rammetto One', display"
   },
   {
      "name": "Slackey Condensed",
      "stack": "'Slackey', display"
   },
   {
      "name": "Spicy Rice Condensed",
      "stack": "'Spicy Rice', display"
   },
   {
      "name": "Carter One Condensed",
      "stack": "'Carter One', display"
   },
   {
      "name": "Comic Neue Condensed",
      "stack": "'Comic Neue', cursive"
   },
   {
      "name": "Shanti Condensed",
      "stack": "'Shanti', sans-serif"
   },
   {
      "name": "Single Day Condensed",
      "stack": "'Single Day', cursive"
   },
   {
      "name": "Gaegu Condensed",
      "stack": "'Gaegu', cursive"
   },
   {
      "name": "Cute Font Condensed",
      "stack": "'Cute Font', cursive"
   },
   {
      "name": "Hi Melody Condensed",
      "stack": "'Hi Melody', cursive"
   },
   {
      "name": "Kirang Haerang Condensed",
      "stack": "'Kirang Haerang', display"
   },
   {
      "name": "East Sea Dokdo Condensed",
      "stack": "'East Sea Dokdo', display"
   },
   {
      "name": "Poor Story Condensed",
      "stack": "'Poor Story', cursive"
   },
   {
      "name": "Gamja Flower Condensed",
      "stack": "'Gamja Flower', cursive"
   },
   {
      "name": "Abril Fatface Condensed",
      "stack": "'Abril Fatface', display"
   },
   {
      "name": "Alfa Slab One Condensed",
      "stack": "'Alfa Slab One', display"
   },
   {
      "name": "Ultra Condensed",
      "stack": "'Ultra', serif"
   },
   {
      "name": "Paytone One Condensed",
      "stack": "'Paytone One', sans-serif"
   },
   {
      "name": "Righteous Condensed",
      "stack": "'Righteous', display"
   },
   {
      "name": "Sigmar One Condensed",
      "stack": "'Sigmar One', display"
   },
   {
      "name": "Passion One Condensed",
      "stack": "'Passion One', display"
   },
   {
      "name": "Squada One Condensed",
      "stack": "'Squada One', display"
   },
   {
      "name": "Chango Condensed",
      "stack": "'Chango', display"
   },
   {
      "name": "Gravitas One Condensed",
      "stack": "'Gravitas One', display"
   },
   {
      "name": "Rozha One Condensed",
      "stack": "'Rozha One', serif"
   },
   {
      "name": "Rubik One Condensed",
      "stack": "'Rubik One', sans-serif"
   },
   {
      "name": "Stint Ultra Expanded Condensed",
      "stack": "'Stint Ultra Expanded', display"
   },
   {
      "name": "Stint Ultra Condensed Condensed",
      "stack": "'Stint Ultra Condensed', display"
   },
   {
      "name": "Bowlby One Condensed",
      "stack": "'Bowlby One', display"
   },
   {
      "name": "Bowlby One SC Condensed",
      "stack": "'Bowlby One SC', display"
   },
   {
      "name": "Vampiro One Condensed",
      "stack": "'Vampiro One', display"
   },
   {
      "name": "Playfair Display Condensed",
      "stack": "'Playfair Display', serif"
   },
   {
      "name": "Cinzel Decorative Condensed",
      "stack": "'Cinzel Decorative', serif"
   },
   {
      "name": "Bodoni Moda Condensed",
      "stack": "'Bodoni Moda', serif"
   },
   {
      "name": "Cormorant Garamond Condensed",
      "stack": "'Cormorant Garamond', serif"
   },
   {
      "name": "Prata Condensed",
      "stack": "'Prata', serif"
   },
   {
      "name": "Syne Condensed",
      "stack": "'Syne', sans-serif"
   },
   {
      "name": "DM Serif Display Condensed",
      "stack": "'DM Serif Display', serif"
   },
   {
      "name": "Fraunces Condensed",
      "stack": "'Fraunces', serif"
   },
   {
      "name": "Big Shoulders Display Condensed",
      "stack": "'Big Shoulders Display', display"
   },
   {
      "name": "Italiana Condensed",
      "stack": "'Italiana', serif"
   },
   {
      "name": "Forum Condensed",
      "stack": "'Forum', serif"
   },
   {
      "name": "Cinzel Condensed",
      "stack": "'Cinzel', serif"
   },
   {
      "name": "Castoro Titling Condensed",
      "stack": "'Castoro Titling', serif"
   },
   {
      "name": "Bellefair Condensed",
      "stack": "'Bellefair', serif"
   },
   {
      "name": "Fira Code Condensed",
      "stack": "'Fira Code', monospace"
   },
   {
      "name": "JetBrains Mono Condensed",
      "stack": "'JetBrains Mono', monospace"
   },
   {
      "name": "Inconsolata Condensed",
      "stack": "'Inconsolata', monospace"
   },
   {
      "name": "Source Code Pro Condensed",
      "stack": "'Source Code Pro', monospace"
   },
   {
      "name": "Space Mono Condensed",
      "stack": "'Space Mono', monospace"
   },
   {
      "name": "Courier Prime Condensed",
      "stack": "'Courier Prime', monospace"
   },
   {
      "name": "Share Tech Mono Condensed",
      "stack": "'Share Tech Mono', monospace"
   },
   {
      "name": "Anonymous Pro Condensed",
      "stack": "'Anonymous Pro', monospace"
   },
   {
      "name": "Cutive Mono Condensed",
      "stack": "'Cutive Mono', monospace"
   },
   {
      "name": "Nova Mono Condensed",
      "stack": "'Nova Mono', monospace"
   },
   {
      "name": "Major Mono Display Condensed",
      "stack": "'Major Mono Display', monospace"
   },
   {
      "name": "Syne Mono Condensed",
      "stack": "'Syne Mono', monospace"
   },
   {
      "name": "Impact Vintage Condensed",
      "stack": "Impact, fantasy"
   },
   {
      "name": "Comic Sans Original Condensed",
      "stack": "'Comic Sans MS', 'Comic Sans', cursive"
   },
   {
      "name": "Courier Classic Condensed",
      "stack": "'Courier New', Courier, monospace"
   },
   {
      "name": "Georgia Luxury Condensed",
      "stack": "Georgia, serif"
   },
   {
      "name": "Trebuchet Clean Condensed",
      "stack": "'Trebuchet MS', sans-serif"
   },
   {
      "name": "Papyrus Classic Condensed",
      "stack": "Papyrus, fantasy"
   }
];

	const COLORS_POOL = [
 "#D41111",
 "#10DA4B",
 "#890FE0",
 "#E6CB0E",
 "#0DC6EC",
 "#F20C88",
 "#49F310",
 "#1D13F5",
 "#F66217",
 "#1BF7A5",
 "#E71FF9",
 "#CDFA23",
 "#2691FB",
 "#FC2A56",
 "#2EFD40",
 "#7F32FF",
 "#F0B847",
 "#4AF1EA",
 "#F24EC9",
 "#9CF352",
 "#5670F5",
 "#DA250B",
 "#0AE064",
 "#A609E6",
 "#EBEC08",
 "#07ADF2",
 "#F8066A",
 "#27FA0A",
 "#360DFB",
 "#FC7E11",
 "#15FDC4",
 "#FF19F4",
 "#ADEE2F",
 "#3378EF",
 "#F13645",
 "#3AF261",
 "#993EF3",
 "#F5D042",
 "#45E6F6",
 "#F749B5",
 "#85F84D",
 "#5157F9",
 "#DF3D05",
 "#04E57F",
 "#C603EC",
 "#D2F202",
 "#0190F8",
 "#FF0048",
 "#17EC19",
 "#5A1BED",
 "#EF991E",
 "#22F0D8",
 "#F226CE",
 "#95F329",
 "#2D5EF5",
 "#F63B31",
 "#35F777",
 "#B239F8",
 "#FAEB3D",
 "#41D2FB",
 "#FC459F",
 "#6DFD49",
 "#5D4DFE",
 "#E55700",
 "#11D998",
 "#D810DE",
 "#ADE40F",
 "#0E71EA",
 "#F00E31",
 "#11F22F",
 "#7415F3",
 "#F5B718",
 "#1CF4F6",
 "#F820B7",
 "#7AF924",
 "#2840FA",
 "#FB502C",
 "#2FFC90",
 "#CD34FD",
 "#F4FE38",
 "#4BB7F0",
 "#F14F8A",
 "#5EF353",
 "#7957F4",
 "#D8750C",
 "#0BDEB5",
 "#E40AD0",
 "#93EB09",
 "#0853F1",
 "#F7070E",
 "#0BF849",
 "#910FFA",
 "#FBD712",
 "#16DDFC",
 "#FD1A9C",
 "#5DFF1E",
 "#3634EE",
 "#F06F37",
 "#3BF1A7",
 "#DE3FF2",
 "#D4F443",
 "#46A3F5",
 "#F64A73",
 "#4EF758",
 "#8C52F8",
 "#DE9006",
 "#05E4D5",
 "#EA04B7",
 "#76F103",
 "#0231F7",
 "#FD1A01",
 "#05FF66",
 "#AA1CEC",
 "#EEE820",
 "#23B9EF",
 "#F12780",
 "#49F22A",
 "#4A2EF4",
 "#F58632",
 "#36F6C1",
 "#F73AF4",
 "#BFF93E",
 "#428BFA",
 "#FB4659",
 "#4AFC6A",
 "#A14EFD",
 "#E4AF01",
 "#00DCEA",
 "#DD1196",
 "#5CE311",
 "#101EE9",
 "#EF410F",
 "#12F185",
 "#C816F2",
 "#DEF41A",
 "#1DA0F5",
 "#F62164",
 "#2AF825",
 "#6129F9",
 "#FAA02D",
 "#31FBDD",
 "#FC35E0",
 "#A8FE39",
 "#3D72FF",
 "#F05350",
 "#54F285",
 "#B558F3",
 "#D7C20D",
 "#0CB6DD",
 "#E30B7C",
 "#3EE90B",
 "#1809EF",
 "#F65C08",
 "#0CF7A4",
 "#EA10F8",
 "#C5FA14",
 "#1784FB",
 "#FC1B45",
 "#1FFD36",
 "#7A23FE",
 "#EEB638",
 "#3CF0EC",
 "#F140C1",
 "#90F344",
 "#4760F4",
 "#F5644B",
 "#4FF698",
 "#CB53F7",
 "#D8DD08",
 "#079EE3",
 "#E9055F",
 "#1CEF04",
 "#3103F6",
 "#FC7A02",
 "#06FDC5",
 "#FF0AEF",
 "#A4ED21",
 "#246BEE",
 "#F02834",
 "#2CF159",
 "#962FF2",
 "#F4D033",
 "#37E1F5",
 "#F63BAB",
 "#78F83F",
 "#4346F9",
 "#FA7847",
 "#4BFBAE",
 "#E34FFC",
 "#C1E302",
 "#0182E9",
 "#EF003F",
 "#12E217",
 "#5511E8",
 "#EE9710",
 "#14F0DA",
 "#F117C7",
 "#8AF31B",
 "#1E4EF4",
 "#F53122"
];

	const logoText = document.querySelector('.fab-logo-text-main');
	if (!logoText) return;

	let currentFontIdx = -1;
	let currentColorIdx = -1;

	logoText.style.transition = 'opacity 0.3s ease, font-family 0.3s ease, color 0.8s ease';
	logoText.style.cursor = 'pointer';
	logoText.setAttribute('title', 'Cliquer pour changer la police et la couleur');

	const nonce = document.querySelector('script[nonce]')?.getAttribute('nonce') || '';

	function rotateFont() {
		if (FONTS_POOL.length <= 1) return;
		let randomIdx;
		do {
			randomIdx = Math.floor(Math.random() * FONTS_POOL.length);
		} while (randomIdx === currentFontIdx);
		currentFontIdx = randomIdx;
		const fontObj = FONTS_POOL[randomIdx];
		const fontId = `gfont-${fontObj.name.replace(/\s+/g, '-').toLowerCase()}`;

		const applyFontChange = () => {
			logoText.style.opacity = '0.08';
			setTimeout(() => {
				logoText.style.setProperty('font-family', fontObj.stack, 'important');
				logoText.style.opacity = '1';
			}, 300);
		};

		if (document.getElementById(fontId)) {
			applyFontChange();
			return;
		}

		const link = document.createElement('link');
		link.id = fontId;
		link.rel = 'stylesheet';
		link.href = `https://fonts.googleapis.com/css2?family=${encodeURIComponent(fontObj.name)}&display=swap`;
		if (nonce) link.setAttribute('nonce', nonce);

		link.onload = applyFontChange;
		link.onerror = applyFontChange;
		document.head.appendChild(link);

		applyFontChange();
	}

	function rotateColor() {
		if (COLORS_POOL.length <= 1) return;
		let randomIdx;
		do {
			randomIdx = Math.floor(Math.random() * COLORS_POOL.length);
		} while (randomIdx === currentColorIdx);
		currentColorIdx = randomIdx;
		const nextColor = COLORS_POOL[randomIdx];
		logoText.style.setProperty('color', nextColor, 'important');
	}

	logoText.addEventListener('click', () => {
		rotateFont();
		rotateColor();
	});

	rotateFont();
	rotateColor();

	// Rotates the font every 60 seconds
	setInterval(rotateFont, 60000);

	// Rotates the color every 50 seconds
	setInterval(rotateColor, 50000);
})();
