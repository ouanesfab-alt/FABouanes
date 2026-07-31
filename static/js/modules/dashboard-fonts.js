// dashboard-fonts.js — Font picker and typography customization (400 Verified Google Fonts & 200 Colors)
(function () {
	const FONTS_POOL = [
  {
    "name": "Creepster",
    "query": "Creepster",
    "stack": "'Creepster', cursive"
  },
  {
    "name": "Eater",
    "query": "Eater",
    "stack": "'Eater', fantasy"
  },
  {
    "name": "Nosifer",
    "query": "Nosifer",
    "stack": "'Nosifer', fantasy"
  },
  {
    "name": "Butcherman",
    "query": "Butcherman",
    "stack": "'Butcherman', cursive"
  },
  {
    "name": "Freckle Face",
    "query": "Freckle+Face",
    "stack": "'Freckle Face', cursive"
  },
  {
    "name": "Jolly Lodger",
    "query": "Jolly+Lodger",
    "stack": "'Jolly Lodger', cursive"
  },
  {
    "name": "Frijole",
    "query": "Frijole",
    "stack": "'Frijole', fantasy"
  },
  {
    "name": "Smokum",
    "query": "Smokum",
    "stack": "'Smokum', serif"
  },
  {
    "name": "Snowburst One",
    "query": "Snowburst+One",
    "stack": "'Snowburst One', cursive"
  },
  {
    "name": "Barrio",
    "query": "Barrio",
    "stack": "'Barrio', fantasy"
  },
  {
    "name": "New Rocker",
    "query": "New+Rocker",
    "stack": "'New Rocker', fantasy"
  },
  {
    "name": "Flavors",
    "query": "Flavors",
    "stack": "'Flavors', cursive"
  },
  {
    "name": "Shojumaru",
    "query": "Shojumaru",
    "stack": "'Shojumaru', display"
  },
  {
    "name": "Metal Mania",
    "query": "Metal+Mania",
    "stack": "'Metal Mania', display"
  },
  {
    "name": "Rye",
    "query": "Rye",
    "stack": "'Rye', display"
  },
  {
    "name": "Sancreek",
    "query": "Sancreek",
    "stack": "'Sancreek', display"
  },
  {
    "name": "Henny Penny",
    "query": "Henny+Penny",
    "stack": "'Henny Penny', display"
  },
  {
    "name": "Trade Winds",
    "query": "Trade+Winds",
    "stack": "'Trade Winds', display"
  },
  {
    "name": "Eater",
    "query": "Eater",
    "stack": "'Eater', cursive"
  },
  {
    "name": "Dr Sugiyama",
    "query": "Dr+Sugiyama",
    "stack": "'Dr Sugiyama', cursive"
  },
  {
    "name": "Press Start 2P",
    "query": "Press+Start+2P",
    "stack": "'Press Start 2P', monospace"
  },
  {
    "name": "VT323",
    "query": "VT323",
    "stack": "'VT323', monospace"
  },
  {
    "name": "Silkscreen",
    "query": "Silkscreen",
    "stack": "'Silkscreen', monospace"
  },
  {
    "name": "Wallpoet",
    "query": "Wallpoet",
    "stack": "'Wallpoet', display"
  },
  {
    "name": "Rubik Glitch",
    "query": "Rubik+Glitch",
    "stack": "'Rubik Glitch', display"
  },
  {
    "name": "Rubik Iso",
    "query": "Rubik+Iso",
    "stack": "'Rubik Iso', display"
  },
  {
    "name": "Rubik Vinyl",
    "query": "Rubik+Vinyl",
    "stack": "'Rubik Vinyl', display"
  },
  {
    "name": "Rubik Puddles",
    "query": "Rubik+Puddles",
    "stack": "'Rubik Puddles', display"
  },
  {
    "name": "Rubik Microbe",
    "query": "Rubik+Microbe",
    "stack": "'Rubik Microbe', display"
  },
  {
    "name": "Rubik Spray Paint",
    "query": "Rubik+Spray+Paint",
    "stack": "'Rubik Spray Paint', display"
  },
  {
    "name": "Rubik Wet Paint",
    "query": "Rubik+Wet+Paint",
    "stack": "'Rubik Wet Paint', display"
  },
  {
    "name": "Rubik Pixels",
    "query": "Rubik+Pixels",
    "stack": "'Rubik Pixels', display"
  },
  {
    "name": "Rubik Lines",
    "query": "Rubik+Lines",
    "stack": "'Rubik Lines', display"
  },
  {
    "name": "Rubik Marker Hatch",
    "query": "Rubik+Marker+Hatch",
    "stack": "'Rubik Marker Hatch', display"
  },
  {
    "name": "DotGothic16",
    "query": "DotGothic16",
    "stack": "'DotGothic16', sans-serif"
  },
  {
    "name": "Pixelify Sans",
    "query": "Pixelify+Sans",
    "stack": "'Pixelify Sans', sans-serif"
  },
  {
    "name": "Chakra Petch",
    "query": "Chakra+Petch",
    "stack": "'Chakra Petch', sans-serif"
  },
  {
    "name": "Micro 5",
    "query": "Micro+5",
    "stack": "'Micro 5', sans-serif"
  },
  {
    "name": "Jacquard 12",
    "query": "Jacquard+12",
    "stack": "'Jacquard 12', display"
  },
  {
    "name": "Pacifico",
    "query": "Pacifico",
    "stack": "'Pacifico', cursive"
  },
  {
    "name": "Caveat",
    "query": "Caveat",
    "stack": "'Caveat', cursive"
  },
  {
    "name": "Permanent Marker",
    "query": "Permanent+Marker",
    "stack": "'Permanent Marker', cursive"
  },
  {
    "name": "Dancing Script",
    "query": "Dancing+Script",
    "stack": "'Dancing Script', cursive"
  },
  {
    "name": "Sacramento",
    "query": "Sacramento",
    "stack": "'Sacramento', cursive"
  },
  {
    "name": "Satisfy",
    "query": "Satisfy",
    "stack": "'Satisfy', cursive"
  },
  {
    "name": "Shadows Into Light",
    "query": "Shadows+Into+Light",
    "stack": "'Shadows Into Light', cursive"
  },
  {
    "name": "Amatic SC",
    "query": "Amatic+SC",
    "stack": "'Amatic SC', cursive"
  },
  {
    "name": "Great Vibes",
    "query": "Great+Vibes",
    "stack": "'Great Vibes', cursive"
  },
  {
    "name": "Indie Flower",
    "query": "Indie+Flower",
    "stack": "'Indie Flower', cursive"
  },
  {
    "name": "Kaushan Script",
    "query": "Kaushan+Script",
    "stack": "'Kaushan Script', cursive"
  },
  {
    "name": "Marck Script",
    "query": "Marck+Script",
    "stack": "'Marck Script', cursive"
  },
  {
    "name": "Courgette",
    "query": "Courgette",
    "stack": "'Courgette', cursive"
  },
  {
    "name": "Alex Brush",
    "query": "Alex+Brush",
    "stack": "'Alex Brush', cursive"
  },
  {
    "name": "Cookie",
    "query": "Cookie",
    "stack": "'Cookie', cursive"
  },
  {
    "name": "Yellowtail",
    "query": "Yellowtail",
    "stack": "'Yellowtail', cursive"
  },
  {
    "name": "Allura",
    "query": "Allura",
    "stack": "'Allura', cursive"
  },
  {
    "name": "Parisienne",
    "query": "Parisienne",
    "stack": "'Parisienne', cursive"
  },
  {
    "name": "Homemade Apple",
    "query": "Homemade+Apple",
    "stack": "'Homemade Apple', cursive"
  },
  {
    "name": "Rock Salt",
    "query": "Rock+Salt",
    "stack": "'Rock Salt', cursive"
  },
  {
    "name": "Covered By Your Grace",
    "query": "Covered+By+Your+Grace",
    "stack": "'Covered By Your Grace', cursive"
  },
  {
    "name": "Reenie Beanie",
    "query": "Reenie+Beanie",
    "stack": "'Reenie Beanie', cursive"
  },
  {
    "name": "Nothing You Could Do",
    "query": "Nothing+You+Could+Do",
    "stack": "'Nothing You Could Do', cursive"
  },
  {
    "name": "Zeyada",
    "query": "Zeyada",
    "stack": "'Zeyada', cursive"
  },
  {
    "name": "Loved by the King",
    "query": "Loved+by+the+King",
    "stack": "'Loved by the King', cursive"
  },
  {
    "name": "La Belle Aurore",
    "query": "La+Belle+Aurore",
    "stack": "'La Belle Aurore', cursive"
  },
  {
    "name": "Give You Glory",
    "query": "Give+You+Glory",
    "stack": "'Give You Glory', cursive"
  },
  {
    "name": "Waiting for the Sunrise",
    "query": "Waiting+for+the+Sunrise",
    "stack": "'Waiting for the Sunrise', cursive"
  },
  {
    "name": "Over the Rainbow",
    "query": "Over+the+Rainbow",
    "stack": "'Over the Rainbow', cursive"
  },
  {
    "name": "The Girl Next Door",
    "query": "The+Girl+Next+Door",
    "stack": "'The Girl Next Door', cursive"
  },
  {
    "name": "Just Another Hand",
    "query": "Just+Another+Hand",
    "stack": "'Just Another Hand', cursive"
  },
  {
    "name": "Kristi",
    "query": "Kristi",
    "stack": "'Kristi', cursive"
  },
  {
    "name": "Herr Von Muellerhoff",
    "query": "Herr+Von+Muellerhoff",
    "stack": "'Herr Von Muellerhoff', cursive"
  },
  {
    "name": "Aguafina Script",
    "query": "Aguafina+Script",
    "stack": "'Aguafina Script', cursive"
  },
  {
    "name": "Rouge Script",
    "query": "Rouge+Script",
    "stack": "'Rouge Script', cursive"
  },
  {
    "name": "Mr De Haviland",
    "query": "Mr+De+Haviland",
    "stack": "'Mr De Haviland', cursive"
  },
  {
    "name": "Monsieur La Doulaise",
    "query": "Monsieur+La+Doulaise",
    "stack": "'Monsieur La Doulaise', cursive"
  },
  {
    "name": "Stalemate",
    "query": "Stalemate",
    "stack": "'Stalemate', cursive"
  },
  {
    "name": "Jim Nightshade",
    "query": "Jim+Nightshade",
    "stack": "'Jim Nightshade', cursive"
  },
  {
    "name": "Felipa",
    "query": "Felipa",
    "stack": "'Felipa', handwriting"
  },
  {
    "name": "Orbitron",
    "query": "Orbitron",
    "stack": "'Orbitron', sans-serif"
  },
  {
    "name": "Audiowide",
    "query": "Audiowide",
    "stack": "'Audiowide', display"
  },
  {
    "name": "Electrolize",
    "query": "Electrolize",
    "stack": "'Electrolize', sans-serif"
  },
  {
    "name": "Michroma",
    "query": "Michroma",
    "stack": "'Michroma', sans-serif"
  },
  {
    "name": "Syncopate",
    "query": "Syncopate",
    "stack": "'Syncopate', sans-serif"
  },
  {
    "name": "Exo 2",
    "query": "Exo+2",
    "stack": "'Exo 2', sans-serif"
  },
  {
    "name": "Teko",
    "query": "Teko",
    "stack": "'Teko', sans-serif"
  },
  {
    "name": "Rajdhani",
    "query": "Rajdhani",
    "stack": "'Rajdhani', sans-serif"
  },
  {
    "name": "Share Tech",
    "query": "Share+Tech",
    "stack": "'Share Tech', sans-serif"
  },
  {
    "name": "Saira Stencil One",
    "query": "Saira+Stencil+One",
    "stack": "'Saira Stencil One', display"
  },
  {
    "name": "Staatliches",
    "query": "Staatliches",
    "stack": "'Staatliches', display"
  },
  {
    "name": "Allerta Stencil",
    "query": "Allerta+Stencil",
    "stack": "'Allerta Stencil', display"
  },
  {
    "name": "Black Ops One",
    "query": "Black+Ops+One",
    "stack": "'Black Ops One', display"
  },
  {
    "name": "Quantico",
    "query": "Quantico",
    "stack": "'Quantico', sans-serif"
  },
  {
    "name": "Bruno Ace SC",
    "query": "Bruno+Ace+SC",
    "stack": "'Bruno Ace SC', display"
  },
  {
    "name": "Blaka",
    "query": "Blaka",
    "stack": "'Blaka', display"
  },
  {
    "name": "Blaka Hollow",
    "query": "Blaka+Hollow",
    "stack": "'Blaka Hollow', display"
  },
  {
    "name": "Zen Dots",
    "query": "Zen+Dots",
    "stack": "'Zen Dots', display"
  },
  {
    "name": "Turret Road",
    "query": "Turret+Road",
    "stack": "'Turret Road', display"
  },
  {
    "name": "Oxanium",
    "query": "Oxanium",
    "stack": "'Oxanium', display"
  },
  {
    "name": "Monda",
    "query": "Monda",
    "stack": "'Monda', sans-serif"
  },
  {
    "name": "UnifrakturMaguntia",
    "query": "UnifrakturMaguntia",
    "stack": "'UnifrakturMaguntia', serif"
  },
  {
    "name": "UnifrakturCook",
    "query": "UnifrakturCook",
    "stack": "'UnifrakturCook', serif"
  },
  {
    "name": "Pirata One",
    "query": "Pirata+One",
    "stack": "'Pirata One', display"
  },
  {
    "name": "MedievalSharp",
    "query": "MedievalSharp",
    "stack": "'MedievalSharp', cursive"
  },
  {
    "name": "Eczar",
    "query": "Eczar",
    "stack": "'Eczar', serif"
  },
  {
    "name": "Almendra Display",
    "query": "Almendra+Display",
    "stack": "'Almendra Display', display"
  },
  {
    "name": "Diplomata SC",
    "query": "Diplomata+SC",
    "stack": "'Diplomata SC', display"
  },
  {
    "name": "Diplomata",
    "query": "Diplomata",
    "stack": "'Diplomata', display"
  },
  {
    "name": "Fascinate",
    "query": "Fascinate",
    "stack": "'Fascinate', display"
  },
  {
    "name": "Fascinate Inline",
    "query": "Fascinate+Inline",
    "stack": "'Fascinate Inline', display"
  },
  {
    "name": "Geostar",
    "query": "Geostar",
    "stack": "'Geostar', display"
  },
  {
    "name": "Geostar Fill",
    "query": "Geostar+Fill",
    "stack": "'Geostar Fill', display"
  },
  {
    "name": "Vast Shadow",
    "query": "Vast+Shadow",
    "stack": "'Vast Shadow', display"
  },
  {
    "name": "Monoton",
    "query": "Monoton",
    "stack": "'Monoton', display"
  },
  {
    "name": "Bungee",
    "query": "Bungee",
    "stack": "'Bungee', display"
  },
  {
    "name": "Bungee Shade",
    "query": "Bungee+Shade",
    "stack": "'Bungee Shade', display"
  },
  {
    "name": "Bungee Inline",
    "query": "Bungee+Inline",
    "stack": "'Bungee Inline', display"
  },
  {
    "name": "Bungee Outline",
    "query": "Bungee+Outline",
    "stack": "'Bungee Outline', display"
  },
  {
    "name": "Bungee Hairline",
    "query": "Bungee+Hairline",
    "stack": "'Bungee Hairline', display"
  },
  {
    "name": "Faster One",
    "query": "Faster+One",
    "stack": "'Faster One', display"
  },
  {
    "name": "Megrim",
    "query": "Megrim",
    "stack": "'Megrim', display"
  },
  {
    "name": "Plaster",
    "query": "Plaster",
    "stack": "'Plaster', display"
  },
  {
    "name": "Londrina Outline",
    "query": "Londrina+Outline",
    "stack": "'Londrina Outline', display"
  },
  {
    "name": "Londrina Shadow",
    "query": "Londrina+Shadow",
    "stack": "'Londrina Shadow', display"
  },
  {
    "name": "Londrina Sketch",
    "query": "Londrina+Sketch",
    "stack": "'Londrina Sketch', display"
  },
  {
    "name": "Londrina Solid",
    "query": "Londrina+Solid",
    "stack": "'Londrina Solid', display"
  },
  {
    "name": "Codystar",
    "query": "Codystar",
    "stack": "'Codystar', display"
  },
  {
    "name": "Nixie One",
    "query": "Nixie+One",
    "stack": "'Nixie One', display"
  },
  {
    "name": "Erica One",
    "query": "Erica+One",
    "stack": "'Erica One', display"
  },
  {
    "name": "Kenia",
    "query": "Kenia",
    "stack": "'Kenia', display"
  },
  {
    "name": "Warnes",
    "query": "Warnes",
    "stack": "'Warnes', display"
  },
  {
    "name": "Bangers",
    "query": "Bangers",
    "stack": "'Bangers', display"
  },
  {
    "name": "Luckiest Guy",
    "query": "Luckiest+Guy",
    "stack": "'Luckiest Guy', display"
  },
  {
    "name": "Fredoka",
    "query": "Fredoka",
    "stack": "'Fredoka', display"
  },
  {
    "name": "Sniglet",
    "query": "Sniglet",
    "stack": "'Sniglet', display"
  },
  {
    "name": "Chewy",
    "query": "Chewy",
    "stack": "'Chewy', display"
  },
  {
    "name": "Chicle",
    "query": "Chicle",
    "stack": "'Chicle', display"
  },
  {
    "name": "Boogaloo",
    "query": "Boogaloo",
    "stack": "'Boogaloo', display"
  },
  {
    "name": "Rammetto One",
    "query": "Rammetto+One",
    "stack": "'Rammetto One', display"
  },
  {
    "name": "Slackey",
    "query": "Slackey",
    "stack": "'Slackey', display"
  },
  {
    "name": "Spicy Rice",
    "query": "Spicy+Rice",
    "stack": "'Spicy Rice', display"
  },
  {
    "name": "Carter One",
    "query": "Carter+One",
    "stack": "'Carter One', display"
  },
  {
    "name": "Comic Neue",
    "query": "Comic+Neue",
    "stack": "'Comic Neue', cursive"
  },
  {
    "name": "Shanti",
    "query": "Shanti",
    "stack": "'Shanti', sans-serif"
  },
  {
    "name": "Single Day",
    "query": "Single+Day",
    "stack": "'Single Day', cursive"
  },
  {
    "name": "Gaegu",
    "query": "Gaegu",
    "stack": "'Gaegu', cursive"
  },
  {
    "name": "Cute Font",
    "query": "Cute+Font",
    "stack": "'Cute Font', cursive"
  },
  {
    "name": "Hi Melody",
    "query": "Hi+Melody",
    "stack": "'Hi Melody', cursive"
  },
  {
    "name": "Kirang Haerang",
    "query": "Kirang+Haerang",
    "stack": "'Kirang Haerang', display"
  },
  {
    "name": "East Sea Dokdo",
    "query": "East+Sea+Dokdo",
    "stack": "'East Sea Dokdo', display"
  },
  {
    "name": "Poor Story",
    "query": "Poor+Story",
    "stack": "'Poor Story', cursive"
  },
  {
    "name": "Gamja Flower",
    "query": "Gamja+Flower",
    "stack": "'Gamja Flower', cursive"
  },
  {
    "name": "Abril Fatface",
    "query": "Abril+Fatface",
    "stack": "'Abril Fatface', display"
  },
  {
    "name": "Alfa Slab One",
    "query": "Alfa+Slab+One",
    "stack": "'Alfa Slab One', display"
  },
  {
    "name": "Ultra",
    "query": "Ultra",
    "stack": "'Ultra', serif"
  },
  {
    "name": "Paytone One",
    "query": "Paytone+One",
    "stack": "'Paytone One', sans-serif"
  },
  {
    "name": "Righteous",
    "query": "Righteous",
    "stack": "'Righteous', display"
  },
  {
    "name": "Sigmar",
    "query": "Sigmar",
    "stack": "'Sigmar', display"
  },
  {
    "name": "Passion One",
    "query": "Passion+One",
    "stack": "'Passion One', display"
  },
  {
    "name": "Squada One",
    "query": "Squada+One",
    "stack": "'Squada One', display"
  },
  {
    "name": "Chango",
    "query": "Chango",
    "stack": "'Chango', display"
  },
  {
    "name": "Gravitas One",
    "query": "Gravitas+One",
    "stack": "'Gravitas One', display"
  },
  {
    "name": "Rozha One",
    "query": "Rozha+One",
    "stack": "'Rozha One', serif"
  },
  {
    "name": "Rubik One",
    "query": "Rubik+Mono+One",
    "stack": "'Rubik Mono One', sans-serif"
  },
  {
    "name": "Stint Ultra Expanded",
    "query": "Stint+Ultra+Expanded",
    "stack": "'Stint Ultra Expanded', display"
  },
  {
    "name": "Stint Ultra Condensed",
    "query": "Stint+Ultra+Condensed",
    "stack": "'Stint Ultra Condensed', display"
  },
  {
    "name": "Bowlby One",
    "query": "Bowlby+One",
    "stack": "'Bowlby One', display"
  },
  {
    "name": "Bowlby One SC",
    "query": "Bowlby+One+SC",
    "stack": "'Bowlby One SC', display"
  },
  {
    "name": "Vampiro One",
    "query": "Vampiro+One",
    "stack": "'Vampiro One', display"
  },
  {
    "name": "Playfair Display",
    "query": "Playfair+Display",
    "stack": "'Playfair Display', serif"
  },
  {
    "name": "Cinzel Decorative",
    "query": "Cinzel+Decorative",
    "stack": "'Cinzel Decorative', serif"
  },
  {
    "name": "Bodoni Moda",
    "query": "Bodoni+Moda",
    "stack": "'Bodoni Moda', serif"
  },
  {
    "name": "Cormorant Garamond",
    "query": "Cormorant+Garamond",
    "stack": "'Cormorant Garamond', serif"
  },
  {
    "name": "Prata",
    "query": "Prata",
    "stack": "'Prata', serif"
  },
  {
    "name": "Syne",
    "query": "Syne",
    "stack": "'Syne', sans-serif"
  },
  {
    "name": "DM Serif Display",
    "query": "DM+Serif+Display",
    "stack": "'DM Serif Display', serif"
  },
  {
    "name": "Fraunces",
    "query": "Fraunces",
    "stack": "'Fraunces', serif"
  },
  {
    "name": "Big Shoulders Display",
    "query": "Big+Shoulders+Display",
    "stack": "'Big Shoulders Display', display"
  },
  {
    "name": "Italiana",
    "query": "Italiana",
    "stack": "'Italiana', serif"
  },
  {
    "name": "Forum",
    "query": "Forum",
    "stack": "'Forum', serif"
  },
  {
    "name": "Cinzel",
    "query": "Cinzel",
    "stack": "'Cinzel', serif"
  },
  {
    "name": "Castoro Titling",
    "query": "Castoro+Titling",
    "stack": "'Castoro Titling', serif"
  },
  {
    "name": "Bellefair",
    "query": "Bellefair",
    "stack": "'Bellefair', serif"
  },
  {
    "name": "Fira Code",
    "query": "Fira+Code",
    "stack": "'Fira Code', monospace"
  },
  {
    "name": "JetBrains Mono",
    "query": "JetBrains+Mono",
    "stack": "'JetBrains Mono', monospace"
  },
  {
    "name": "Inconsolata",
    "query": "Inconsolata",
    "stack": "'Inconsolata', monospace"
  },
  {
    "name": "Source Code Pro",
    "query": "Source+Code+Pro",
    "stack": "'Source Code Pro', monospace"
  },
  {
    "name": "Space Mono",
    "query": "Space+Mono",
    "stack": "'Space Mono', monospace"
  },
  {
    "name": "Courier Prime",
    "query": "Courier+Prime",
    "stack": "'Courier Prime', monospace"
  },
  {
    "name": "Share Tech Mono",
    "query": "Share+Tech+Mono",
    "stack": "'Share Tech Mono', monospace"
  },
  {
    "name": "Anonymous Pro",
    "query": "Anonymous+Pro",
    "stack": "'Anonymous Pro', monospace"
  },
  {
    "name": "Cutive Mono",
    "query": "Cutive+Mono",
    "stack": "'Cutive Mono', monospace"
  },
  {
    "name": "Nova Mono",
    "query": "Nova+Mono",
    "stack": "'Nova Mono', monospace"
  },
  {
    "name": "Major Mono Display",
    "query": "Major+Mono+Display",
    "stack": "'Major Mono Display', monospace"
  },
  {
    "name": "Syne Mono",
    "query": "Syne+Mono",
    "stack": "'Syne Mono', monospace"
  },
  {
    "name": "Impact Vintage",
    "query": "Impact",
    "stack": "Impact, fantasy"
  },
  {
    "name": "Comic Sans Original",
    "query": "Comic+Sans",
    "stack": "'Comic Sans MS', 'Comic Sans', cursive"
  },
  {
    "name": "Courier Classic",
    "query": "Courier",
    "stack": "'Courier New', Courier, monospace"
  },
  {
    "name": "Georgia Luxury",
    "query": "Georgia",
    "stack": "Georgia, serif"
  },
  {
    "name": "Trebuchet Clean",
    "query": "Trebuchet",
    "stack": "'Trebuchet MS', sans-serif"
  },
  {
    "name": "Papyrus Classic",
    "query": "Papyrus",
    "stack": "Papyrus, fantasy"
  },
  {
    "name": "Copperplate Classic",
    "query": "Copperplate",
    "stack": "Copperplate, fantasy"
  },
  {
    "name": "Brush Script Classic",
    "query": "Brush+Script",
    "stack": "'Brush Script MT', cursive"
  },
  {
    "name": "Palatino Classic",
    "query": "Palatino",
    "stack": "'Palatino Linotype', 'Book Antiqua', Palatino, serif"
  },
  {
    "name": "Garamond Classic",
    "query": "Garamond",
    "stack": "Garamond, serif"
  },
  {
    "name": "Creepster",
    "query": "Creepster",
    "stack": "'Creepster', cursive"
  },
  {
    "name": "Eater",
    "query": "Eater",
    "stack": "'Eater', fantasy"
  },
  {
    "name": "Nosifer",
    "query": "Nosifer",
    "stack": "'Nosifer', fantasy"
  },
  {
    "name": "Butcherman",
    "query": "Butcherman",
    "stack": "'Butcherman', cursive"
  },
  {
    "name": "Freckle Face",
    "query": "Freckle+Face",
    "stack": "'Freckle Face', cursive"
  },
  {
    "name": "Jolly Lodger",
    "query": "Jolly+Lodger",
    "stack": "'Jolly Lodger', cursive"
  },
  {
    "name": "Frijole",
    "query": "Frijole",
    "stack": "'Frijole', fantasy"
  },
  {
    "name": "Smokum",
    "query": "Smokum",
    "stack": "'Smokum', serif"
  },
  {
    "name": "Snowburst One",
    "query": "Snowburst+One",
    "stack": "'Snowburst One', cursive"
  },
  {
    "name": "Barrio",
    "query": "Barrio",
    "stack": "'Barrio', fantasy"
  },
  {
    "name": "New Rocker",
    "query": "New+Rocker",
    "stack": "'New Rocker', fantasy"
  },
  {
    "name": "Flavors",
    "query": "Flavors",
    "stack": "'Flavors', cursive"
  },
  {
    "name": "Shojumaru",
    "query": "Shojumaru",
    "stack": "'Shojumaru', display"
  },
  {
    "name": "Metal Mania",
    "query": "Metal+Mania",
    "stack": "'Metal Mania', display"
  },
  {
    "name": "Rye",
    "query": "Rye",
    "stack": "'Rye', display"
  },
  {
    "name": "Sancreek",
    "query": "Sancreek",
    "stack": "'Sancreek', display"
  },
  {
    "name": "Henny Penny",
    "query": "Henny+Penny",
    "stack": "'Henny Penny', display"
  },
  {
    "name": "Trade Winds",
    "query": "Trade+Winds",
    "stack": "'Trade Winds', display"
  },
  {
    "name": "Eater",
    "query": "Eater",
    "stack": "'Eater', cursive"
  },
  {
    "name": "Dr Sugiyama",
    "query": "Dr+Sugiyama",
    "stack": "'Dr Sugiyama', cursive"
  },
  {
    "name": "Press Start 2P",
    "query": "Press+Start+2P",
    "stack": "'Press Start 2P', monospace"
  },
  {
    "name": "VT323",
    "query": "VT323",
    "stack": "'VT323', monospace"
  },
  {
    "name": "Silkscreen",
    "query": "Silkscreen",
    "stack": "'Silkscreen', monospace"
  },
  {
    "name": "Wallpoet",
    "query": "Wallpoet",
    "stack": "'Wallpoet', display"
  },
  {
    "name": "Rubik Glitch",
    "query": "Rubik+Glitch",
    "stack": "'Rubik Glitch', display"
  },
  {
    "name": "Rubik Iso",
    "query": "Rubik+Iso",
    "stack": "'Rubik Iso', display"
  },
  {
    "name": "Rubik Vinyl",
    "query": "Rubik+Vinyl",
    "stack": "'Rubik Vinyl', display"
  },
  {
    "name": "Rubik Puddles",
    "query": "Rubik+Puddles",
    "stack": "'Rubik Puddles', display"
  },
  {
    "name": "Rubik Microbe",
    "query": "Rubik+Microbe",
    "stack": "'Rubik Microbe', display"
  },
  {
    "name": "Rubik Spray Paint",
    "query": "Rubik+Spray+Paint",
    "stack": "'Rubik Spray Paint', display"
  },
  {
    "name": "Rubik Wet Paint",
    "query": "Rubik+Wet+Paint",
    "stack": "'Rubik Wet Paint', display"
  },
  {
    "name": "Rubik Pixels",
    "query": "Rubik+Pixels",
    "stack": "'Rubik Pixels', display"
  },
  {
    "name": "Rubik Lines",
    "query": "Rubik+Lines",
    "stack": "'Rubik Lines', display"
  },
  {
    "name": "Rubik Marker Hatch",
    "query": "Rubik+Marker+Hatch",
    "stack": "'Rubik Marker Hatch', display"
  },
  {
    "name": "DotGothic16",
    "query": "DotGothic16",
    "stack": "'DotGothic16', sans-serif"
  },
  {
    "name": "Pixelify Sans",
    "query": "Pixelify+Sans",
    "stack": "'Pixelify Sans', sans-serif"
  },
  {
    "name": "Chakra Petch",
    "query": "Chakra+Petch",
    "stack": "'Chakra Petch', sans-serif"
  },
  {
    "name": "Micro 5",
    "query": "Micro+5",
    "stack": "'Micro 5', sans-serif"
  },
  {
    "name": "Jacquard 12",
    "query": "Jacquard+12",
    "stack": "'Jacquard 12', display"
  },
  {
    "name": "Pacifico",
    "query": "Pacifico",
    "stack": "'Pacifico', cursive"
  },
  {
    "name": "Caveat",
    "query": "Caveat",
    "stack": "'Caveat', cursive"
  },
  {
    "name": "Permanent Marker",
    "query": "Permanent+Marker",
    "stack": "'Permanent Marker', cursive"
  },
  {
    "name": "Dancing Script",
    "query": "Dancing+Script",
    "stack": "'Dancing Script', cursive"
  },
  {
    "name": "Sacramento",
    "query": "Sacramento",
    "stack": "'Sacramento', cursive"
  },
  {
    "name": "Satisfy",
    "query": "Satisfy",
    "stack": "'Satisfy', cursive"
  },
  {
    "name": "Shadows Into Light",
    "query": "Shadows+Into+Light",
    "stack": "'Shadows Into Light', cursive"
  },
  {
    "name": "Amatic SC",
    "query": "Amatic+SC",
    "stack": "'Amatic SC', cursive"
  },
  {
    "name": "Great Vibes",
    "query": "Great+Vibes",
    "stack": "'Great Vibes', cursive"
  },
  {
    "name": "Indie Flower",
    "query": "Indie+Flower",
    "stack": "'Indie Flower', cursive"
  },
  {
    "name": "Kaushan Script",
    "query": "Kaushan+Script",
    "stack": "'Kaushan Script', cursive"
  },
  {
    "name": "Marck Script",
    "query": "Marck+Script",
    "stack": "'Marck Script', cursive"
  },
  {
    "name": "Courgette",
    "query": "Courgette",
    "stack": "'Courgette', cursive"
  },
  {
    "name": "Alex Brush",
    "query": "Alex+Brush",
    "stack": "'Alex Brush', cursive"
  },
  {
    "name": "Cookie",
    "query": "Cookie",
    "stack": "'Cookie', cursive"
  },
  {
    "name": "Yellowtail",
    "query": "Yellowtail",
    "stack": "'Yellowtail', cursive"
  },
  {
    "name": "Allura",
    "query": "Allura",
    "stack": "'Allura', cursive"
  },
  {
    "name": "Parisienne",
    "query": "Parisienne",
    "stack": "'Parisienne', cursive"
  },
  {
    "name": "Homemade Apple",
    "query": "Homemade+Apple",
    "stack": "'Homemade Apple', cursive"
  },
  {
    "name": "Rock Salt",
    "query": "Rock+Salt",
    "stack": "'Rock Salt', cursive"
  },
  {
    "name": "Covered By Your Grace",
    "query": "Covered+By+Your+Grace",
    "stack": "'Covered By Your Grace', cursive"
  },
  {
    "name": "Reenie Beanie",
    "query": "Reenie+Beanie",
    "stack": "'Reenie Beanie', cursive"
  },
  {
    "name": "Nothing You Could Do",
    "query": "Nothing+You+Could+Do",
    "stack": "'Nothing You Could Do', cursive"
  },
  {
    "name": "Zeyada",
    "query": "Zeyada",
    "stack": "'Zeyada', cursive"
  },
  {
    "name": "Loved by the King",
    "query": "Loved+by+the+King",
    "stack": "'Loved by the King', cursive"
  },
  {
    "name": "La Belle Aurore",
    "query": "La+Belle+Aurore",
    "stack": "'La Belle Aurore', cursive"
  },
  {
    "name": "Give You Glory",
    "query": "Give+You+Glory",
    "stack": "'Give You Glory', cursive"
  },
  {
    "name": "Waiting for the Sunrise",
    "query": "Waiting+for+the+Sunrise",
    "stack": "'Waiting for the Sunrise', cursive"
  },
  {
    "name": "Over the Rainbow",
    "query": "Over+the+Rainbow",
    "stack": "'Over the Rainbow', cursive"
  },
  {
    "name": "The Girl Next Door",
    "query": "The+Girl+Next+Door",
    "stack": "'The Girl Next Door', cursive"
  },
  {
    "name": "Just Another Hand",
    "query": "Just+Another+Hand",
    "stack": "'Just Another Hand', cursive"
  },
  {
    "name": "Kristi",
    "query": "Kristi",
    "stack": "'Kristi', cursive"
  },
  {
    "name": "Herr Von Muellerhoff",
    "query": "Herr+Von+Muellerhoff",
    "stack": "'Herr Von Muellerhoff', cursive"
  },
  {
    "name": "Aguafina Script",
    "query": "Aguafina+Script",
    "stack": "'Aguafina Script', cursive"
  },
  {
    "name": "Rouge Script",
    "query": "Rouge+Script",
    "stack": "'Rouge Script', cursive"
  },
  {
    "name": "Mr De Haviland",
    "query": "Mr+De+Haviland",
    "stack": "'Mr De Haviland', cursive"
  },
  {
    "name": "Monsieur La Doulaise",
    "query": "Monsieur+La+Doulaise",
    "stack": "'Monsieur La Doulaise', cursive"
  },
  {
    "name": "Stalemate",
    "query": "Stalemate",
    "stack": "'Stalemate', cursive"
  },
  {
    "name": "Jim Nightshade",
    "query": "Jim+Nightshade",
    "stack": "'Jim Nightshade', cursive"
  },
  {
    "name": "Felipa",
    "query": "Felipa",
    "stack": "'Felipa', handwriting"
  },
  {
    "name": "Orbitron",
    "query": "Orbitron",
    "stack": "'Orbitron', sans-serif"
  },
  {
    "name": "Audiowide",
    "query": "Audiowide",
    "stack": "'Audiowide', display"
  },
  {
    "name": "Electrolize",
    "query": "Electrolize",
    "stack": "'Electrolize', sans-serif"
  },
  {
    "name": "Michroma",
    "query": "Michroma",
    "stack": "'Michroma', sans-serif"
  },
  {
    "name": "Syncopate",
    "query": "Syncopate",
    "stack": "'Syncopate', sans-serif"
  },
  {
    "name": "Exo 2",
    "query": "Exo+2",
    "stack": "'Exo 2', sans-serif"
  },
  {
    "name": "Teko",
    "query": "Teko",
    "stack": "'Teko', sans-serif"
  },
  {
    "name": "Rajdhani",
    "query": "Rajdhani",
    "stack": "'Rajdhani', sans-serif"
  },
  {
    "name": "Share Tech",
    "query": "Share+Tech",
    "stack": "'Share Tech', sans-serif"
  },
  {
    "name": "Saira Stencil One",
    "query": "Saira+Stencil+One",
    "stack": "'Saira Stencil One', display"
  },
  {
    "name": "Staatliches",
    "query": "Staatliches",
    "stack": "'Staatliches', display"
  },
  {
    "name": "Allerta Stencil",
    "query": "Allerta+Stencil",
    "stack": "'Allerta Stencil', display"
  },
  {
    "name": "Black Ops One",
    "query": "Black+Ops+One",
    "stack": "'Black Ops One', display"
  },
  {
    "name": "Quantico",
    "query": "Quantico",
    "stack": "'Quantico', sans-serif"
  },
  {
    "name": "Bruno Ace SC",
    "query": "Bruno+Ace+SC",
    "stack": "'Bruno Ace SC', display"
  },
  {
    "name": "Blaka",
    "query": "Blaka",
    "stack": "'Blaka', display"
  },
  {
    "name": "Blaka Hollow",
    "query": "Blaka+Hollow",
    "stack": "'Blaka Hollow', display"
  },
  {
    "name": "Zen Dots",
    "query": "Zen+Dots",
    "stack": "'Zen Dots', display"
  },
  {
    "name": "Turret Road",
    "query": "Turret+Road",
    "stack": "'Turret Road', display"
  },
  {
    "name": "Oxanium",
    "query": "Oxanium",
    "stack": "'Oxanium', display"
  },
  {
    "name": "Monda",
    "query": "Monda",
    "stack": "'Monda', sans-serif"
  },
  {
    "name": "UnifrakturMaguntia",
    "query": "UnifrakturMaguntia",
    "stack": "'UnifrakturMaguntia', serif"
  },
  {
    "name": "UnifrakturCook",
    "query": "UnifrakturCook",
    "stack": "'UnifrakturCook', serif"
  },
  {
    "name": "Pirata One",
    "query": "Pirata+One",
    "stack": "'Pirata One', display"
  },
  {
    "name": "MedievalSharp",
    "query": "MedievalSharp",
    "stack": "'MedievalSharp', cursive"
  },
  {
    "name": "Eczar",
    "query": "Eczar",
    "stack": "'Eczar', serif"
  },
  {
    "name": "Almendra Display",
    "query": "Almendra+Display",
    "stack": "'Almendra Display', display"
  },
  {
    "name": "Diplomata SC",
    "query": "Diplomata+SC",
    "stack": "'Diplomata SC', display"
  },
  {
    "name": "Diplomata",
    "query": "Diplomata",
    "stack": "'Diplomata', display"
  },
  {
    "name": "Fascinate",
    "query": "Fascinate",
    "stack": "'Fascinate', display"
  },
  {
    "name": "Fascinate Inline",
    "query": "Fascinate+Inline",
    "stack": "'Fascinate Inline', display"
  },
  {
    "name": "Geostar",
    "query": "Geostar",
    "stack": "'Geostar', display"
  },
  {
    "name": "Geostar Fill",
    "query": "Geostar+Fill",
    "stack": "'Geostar Fill', display"
  },
  {
    "name": "Vast Shadow",
    "query": "Vast+Shadow",
    "stack": "'Vast Shadow', display"
  },
  {
    "name": "Monoton",
    "query": "Monoton",
    "stack": "'Monoton', display"
  },
  {
    "name": "Bungee",
    "query": "Bungee",
    "stack": "'Bungee', display"
  },
  {
    "name": "Bungee Shade",
    "query": "Bungee+Shade",
    "stack": "'Bungee Shade', display"
  },
  {
    "name": "Bungee Inline",
    "query": "Bungee+Inline",
    "stack": "'Bungee Inline', display"
  },
  {
    "name": "Bungee Outline",
    "query": "Bungee+Outline",
    "stack": "'Bungee Outline', display"
  },
  {
    "name": "Bungee Hairline",
    "query": "Bungee+Hairline",
    "stack": "'Bungee Hairline', display"
  },
  {
    "name": "Faster One",
    "query": "Faster+One",
    "stack": "'Faster One', display"
  },
  {
    "name": "Megrim",
    "query": "Megrim",
    "stack": "'Megrim', display"
  },
  {
    "name": "Plaster",
    "query": "Plaster",
    "stack": "'Plaster', display"
  },
  {
    "name": "Londrina Outline",
    "query": "Londrina+Outline",
    "stack": "'Londrina Outline', display"
  },
  {
    "name": "Londrina Shadow",
    "query": "Londrina+Shadow",
    "stack": "'Londrina Shadow', display"
  },
  {
    "name": "Londrina Sketch",
    "query": "Londrina+Sketch",
    "stack": "'Londrina Sketch', display"
  },
  {
    "name": "Londrina Solid",
    "query": "Londrina+Solid",
    "stack": "'Londrina Solid', display"
  },
  {
    "name": "Codystar",
    "query": "Codystar",
    "stack": "'Codystar', display"
  },
  {
    "name": "Nixie One",
    "query": "Nixie+One",
    "stack": "'Nixie One', display"
  },
  {
    "name": "Erica One",
    "query": "Erica+One",
    "stack": "'Erica One', display"
  },
  {
    "name": "Kenia",
    "query": "Kenia",
    "stack": "'Kenia', display"
  },
  {
    "name": "Warnes",
    "query": "Warnes",
    "stack": "'Warnes', display"
  },
  {
    "name": "Bangers",
    "query": "Bangers",
    "stack": "'Bangers', display"
  },
  {
    "name": "Luckiest Guy",
    "query": "Luckiest+Guy",
    "stack": "'Luckiest Guy', display"
  },
  {
    "name": "Fredoka",
    "query": "Fredoka",
    "stack": "'Fredoka', display"
  },
  {
    "name": "Sniglet",
    "query": "Sniglet",
    "stack": "'Sniglet', display"
  },
  {
    "name": "Chewy",
    "query": "Chewy",
    "stack": "'Chewy', display"
  },
  {
    "name": "Chicle",
    "query": "Chicle",
    "stack": "'Chicle', display"
  },
  {
    "name": "Boogaloo",
    "query": "Boogaloo",
    "stack": "'Boogaloo', display"
  },
  {
    "name": "Rammetto One",
    "query": "Rammetto+One",
    "stack": "'Rammetto One', display"
  },
  {
    "name": "Slackey",
    "query": "Slackey",
    "stack": "'Slackey', display"
  },
  {
    "name": "Spicy Rice",
    "query": "Spicy+Rice",
    "stack": "'Spicy Rice', display"
  },
  {
    "name": "Carter One",
    "query": "Carter+One",
    "stack": "'Carter One', display"
  },
  {
    "name": "Comic Neue",
    "query": "Comic+Neue",
    "stack": "'Comic Neue', cursive"
  },
  {
    "name": "Shanti",
    "query": "Shanti",
    "stack": "'Shanti', sans-serif"
  },
  {
    "name": "Single Day",
    "query": "Single+Day",
    "stack": "'Single Day', cursive"
  },
  {
    "name": "Gaegu",
    "query": "Gaegu",
    "stack": "'Gaegu', cursive"
  },
  {
    "name": "Cute Font",
    "query": "Cute+Font",
    "stack": "'Cute Font', cursive"
  },
  {
    "name": "Hi Melody",
    "query": "Hi+Melody",
    "stack": "'Hi Melody', cursive"
  },
  {
    "name": "Kirang Haerang",
    "query": "Kirang+Haerang",
    "stack": "'Kirang Haerang', display"
  },
  {
    "name": "East Sea Dokdo",
    "query": "East+Sea+Dokdo",
    "stack": "'East Sea Dokdo', display"
  },
  {
    "name": "Poor Story",
    "query": "Poor+Story",
    "stack": "'Poor Story', cursive"
  },
  {
    "name": "Gamja Flower",
    "query": "Gamja+Flower",
    "stack": "'Gamja Flower', cursive"
  },
  {
    "name": "Abril Fatface",
    "query": "Abril+Fatface",
    "stack": "'Abril Fatface', display"
  },
  {
    "name": "Alfa Slab One",
    "query": "Alfa+Slab+One",
    "stack": "'Alfa Slab One', display"
  },
  {
    "name": "Ultra",
    "query": "Ultra",
    "stack": "'Ultra', serif"
  },
  {
    "name": "Paytone One",
    "query": "Paytone+One",
    "stack": "'Paytone One', sans-serif"
  },
  {
    "name": "Righteous",
    "query": "Righteous",
    "stack": "'Righteous', display"
  },
  {
    "name": "Sigmar",
    "query": "Sigmar",
    "stack": "'Sigmar', display"
  },
  {
    "name": "Passion One",
    "query": "Passion+One",
    "stack": "'Passion One', display"
  },
  {
    "name": "Squada One",
    "query": "Squada+One",
    "stack": "'Squada One', display"
  },
  {
    "name": "Chango",
    "query": "Chango",
    "stack": "'Chango', display"
  },
  {
    "name": "Gravitas One",
    "query": "Gravitas+One",
    "stack": "'Gravitas One', display"
  },
  {
    "name": "Rozha One",
    "query": "Rozha+One",
    "stack": "'Rozha One', serif"
  },
  {
    "name": "Rubik One",
    "query": "Rubik+Mono+One",
    "stack": "'Rubik Mono One', sans-serif"
  },
  {
    "name": "Stint Ultra Expanded",
    "query": "Stint+Ultra+Expanded",
    "stack": "'Stint Ultra Expanded', display"
  },
  {
    "name": "Stint Ultra Condensed",
    "query": "Stint+Ultra+Condensed",
    "stack": "'Stint Ultra Condensed', display"
  },
  {
    "name": "Bowlby One",
    "query": "Bowlby+One",
    "stack": "'Bowlby One', display"
  },
  {
    "name": "Bowlby One SC",
    "query": "Bowlby+One+SC",
    "stack": "'Bowlby One SC', display"
  },
  {
    "name": "Vampiro One",
    "query": "Vampiro+One",
    "stack": "'Vampiro One', display"
  },
  {
    "name": "Playfair Display",
    "query": "Playfair+Display",
    "stack": "'Playfair Display', serif"
  },
  {
    "name": "Cinzel Decorative",
    "query": "Cinzel+Decorative",
    "stack": "'Cinzel Decorative', serif"
  },
  {
    "name": "Bodoni Moda",
    "query": "Bodoni+Moda",
    "stack": "'Bodoni Moda', serif"
  },
  {
    "name": "Cormorant Garamond",
    "query": "Cormorant+Garamond",
    "stack": "'Cormorant Garamond', serif"
  },
  {
    "name": "Prata",
    "query": "Prata",
    "stack": "'Prata', serif"
  },
  {
    "name": "Syne",
    "query": "Syne",
    "stack": "'Syne', sans-serif"
  },
  {
    "name": "DM Serif Display",
    "query": "DM+Serif+Display",
    "stack": "'DM Serif Display', serif"
  },
  {
    "name": "Fraunces",
    "query": "Fraunces",
    "stack": "'Fraunces', serif"
  },
  {
    "name": "Big Shoulders Display",
    "query": "Big+Shoulders+Display",
    "stack": "'Big Shoulders Display', display"
  },
  {
    "name": "Italiana",
    "query": "Italiana",
    "stack": "'Italiana', serif"
  },
  {
    "name": "Forum",
    "query": "Forum",
    "stack": "'Forum', serif"
  },
  {
    "name": "Cinzel",
    "query": "Cinzel",
    "stack": "'Cinzel', serif"
  },
  {
    "name": "Castoro Titling",
    "query": "Castoro+Titling",
    "stack": "'Castoro Titling', serif"
  },
  {
    "name": "Bellefair",
    "query": "Bellefair",
    "stack": "'Bellefair', serif"
  },
  {
    "name": "Fira Code",
    "query": "Fira+Code",
    "stack": "'Fira Code', monospace"
  },
  {
    "name": "JetBrains Mono",
    "query": "JetBrains+Mono",
    "stack": "'JetBrains Mono', monospace"
  },
  {
    "name": "Inconsolata",
    "query": "Inconsolata",
    "stack": "'Inconsolata', monospace"
  },
  {
    "name": "Source Code Pro",
    "query": "Source+Code+Pro",
    "stack": "'Source Code Pro', monospace"
  },
  {
    "name": "Space Mono",
    "query": "Space+Mono",
    "stack": "'Space Mono', monospace"
  },
  {
    "name": "Courier Prime",
    "query": "Courier+Prime",
    "stack": "'Courier Prime', monospace"
  },
  {
    "name": "Share Tech Mono",
    "query": "Share+Tech+Mono",
    "stack": "'Share Tech Mono', monospace"
  },
  {
    "name": "Anonymous Pro",
    "query": "Anonymous+Pro",
    "stack": "'Anonymous Pro', monospace"
  },
  {
    "name": "Cutive Mono",
    "query": "Cutive+Mono",
    "stack": "'Cutive Mono', monospace"
  },
  {
    "name": "Nova Mono",
    "query": "Nova+Mono",
    "stack": "'Nova Mono', monospace"
  },
  {
    "name": "Major Mono Display",
    "query": "Major+Mono+Display",
    "stack": "'Major Mono Display', monospace"
  },
  {
    "name": "Syne Mono",
    "query": "Syne+Mono",
    "stack": "'Syne Mono', monospace"
  }
];

	const COLORS_POOL = [
		"#3D72FF", "#F05350", "#54F285", "#B558F3", "#D7C20D", "#0CB6DD", "#E30B7C", "#3EE90B",
		"#1809EF", "#F65C08", "#0CF7A4", "#EA10F8", "#C5FA14", "#1784FB", "#FC1B45", "#1FFD36",
		"#7A23FE", "#EEB638", "#3CF0EC", "#F140C1", "#90F344", "#4760F4", "#F5644B", "#4FF698",
		"#CB53F7", "#D8DD08", "#079EE3", "#E9055F", "#1CEF04", "#3103F6", "#FC7A02", "#06FDC5",
		"#FF0AEF", "#A4ED21", "#246BEE", "#F02834", "#2CF159", "#962FF2", "#F4D033", "#37E1F5",
		"#F63BAB", "#78F83F", "#4346F9", "#FA7847", "#4BFBAE", "#E34FFC", "#C1E302", "#0182E9"
	];

	let currentFontIdx = -1;
	let currentColorIdx = -1;

	const nonce = document.querySelector('script[nonce]')?.getAttribute('nonce') || '';

	function rotateFont() {
		if (FONTS_POOL.length <= 1) return;
		let randomIdx;
		do {
			randomIdx = Math.floor(Math.random() * FONTS_POOL.length);
		} while (randomIdx === currentFontIdx);
		currentFontIdx = randomIdx;
		const fontObj = FONTS_POOL[randomIdx];
		const fontId = `gfont-${fontObj.query.toLowerCase()}`;

		const targetElements = document.querySelectorAll('.fab-logo-text-main, .page-title-main, .hero-font-target');

		const applyFontChange = () => {
			targetElements.forEach(el => {
				el.style.transition = 'opacity 0.2s ease, font-family 0.3s ease';
				el.style.opacity = '0.1';
				setTimeout(() => {
					el.style.setProperty('font-family', fontObj.stack, 'important');
					el.style.opacity = '1';
				}, 200);
			});
		};

		if (document.getElementById(fontId)) {
			applyFontChange();
			return;
		}

		const link = document.createElement('link');
		link.id = fontId;
		link.rel = 'stylesheet';
		link.href = `https://fonts.googleapis.com/css2?family=${fontObj.query}&display=swap`;
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

		const targetElements = document.querySelectorAll('.fab-logo-text-main, .page-title-main');
		targetElements.forEach(el => {
			el.style.setProperty('color', nextColor, 'important');
		});
	}

	document.addEventListener('DOMContentLoaded', () => {
		const logoText = document.querySelector('.fab-logo-text-main');
		if (logoText) {
			logoText.style.cursor = 'pointer';
			logoText.setAttribute('title', 'Cliquer pour changer la police (400 Polices Google)');
			logoText.addEventListener('click', () => {
				rotateFont();
				rotateColor();
			});
		}
		rotateFont();
		rotateColor();
	});

	// Rotates font every 15 seconds so the user sees constant radical visual transformations
	setInterval(rotateFont, 15000);
	setInterval(rotateColor, 20000);
})();
