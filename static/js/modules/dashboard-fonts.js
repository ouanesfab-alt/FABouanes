// dashboard-fonts.js — Dynamic Font Rotator & Typography Switcher (400 Verified Distinct Fonts with Full Persistence)
(function () {
	const FONTS_POOL = [
  {
    "id": 1,
    "name": "Creepster",
    "query": "Creepster",
    "stack": "'Creepster', 'Jokerman', 'Chiller', 'Impact', fantasy",
    "weight": "300",
    "style": "normal",
    "spacing": "-1.5px",
    "transform": "none"
  },
  {
    "id": 2,
    "name": "Eater",
    "query": "Eater",
    "stack": "'Eater', 'Brush Script MT', 'Segoe Script', 'Monotype Corsiva', cursive",
    "weight": "400",
    "style": "italic",
    "spacing": "-0.8px",
    "transform": "uppercase"
  },
  {
    "id": 3,
    "name": "Nosifer",
    "query": "Nosifer",
    "stack": "'Nosifer', 'Consolas', 'Cascadia Code', 'Courier New', monospace",
    "weight": "500",
    "style": "normal",
    "spacing": "0px",
    "transform": "lowercase"
  },
  {
    "id": 4,
    "name": "Butcherman",
    "query": "Butcherman",
    "stack": "'Butcherman', 'Georgia', 'Palatino Linotype', 'Book Antiqua', serif",
    "weight": "600",
    "style": "italic",
    "spacing": "0.5px",
    "transform": "capitalize"
  },
  {
    "id": 5,
    "name": "Freckle Face",
    "query": "Freckle+Face",
    "stack": "'Freckle Face', 'Trebuchet MS', 'Arial Black', 'Franklin Gothic Medium', sans-serif",
    "weight": "700",
    "style": "normal",
    "spacing": "1.2px",
    "transform": "none"
  },
  {
    "id": 6,
    "name": "Jolly Lodger",
    "query": "Jolly+Lodger",
    "stack": "'Jolly Lodger', 'Copperplate', 'Papyrus', 'Impact', fantasy",
    "weight": "800",
    "style": "italic",
    "spacing": "2px",
    "transform": "uppercase"
  },
  {
    "id": 7,
    "name": "Frijole",
    "query": "Frijole",
    "stack": "'Frijole', 'Lucida Console', 'Lucida Sans Unicode', monospace",
    "weight": "900",
    "style": "normal",
    "spacing": "3px",
    "transform": "lowercase"
  },
  {
    "id": 8,
    "name": "Smokum",
    "query": "Smokum",
    "stack": "'Smokum', 'Gabriola', 'Segoe Print', cursive",
    "weight": "300",
    "style": "italic",
    "spacing": "4px",
    "transform": "capitalize"
  },
  {
    "id": 9,
    "name": "Snowburst One",
    "query": "Snowburst+One",
    "stack": "'Snowburst One', 'Bahnschrift', 'Franklin Gothic Heavy', sans-serif",
    "weight": "400",
    "style": "normal",
    "spacing": "-1.5px",
    "transform": "none"
  },
  {
    "id": 10,
    "name": "Barrio",
    "query": "Barrio",
    "stack": "'Barrio', 'Ebrima', 'Segoe UI Semibold', sans-serif",
    "weight": "500",
    "style": "italic",
    "spacing": "-0.8px",
    "transform": "uppercase"
  },
  {
    "id": 11,
    "name": "New Rocker",
    "query": "New+Rocker",
    "stack": "'New Rocker', 'Sitka Text', 'Cambria', serif",
    "weight": "600",
    "style": "normal",
    "spacing": "0px",
    "transform": "lowercase"
  },
  {
    "id": 12,
    "name": "Flavors",
    "query": "Flavors",
    "stack": "'Flavors', 'Ink Free', 'Comic Sans MS', cursive",
    "weight": "700",
    "style": "italic",
    "spacing": "0.5px",
    "transform": "capitalize"
  },
  {
    "id": 13,
    "name": "Shojumaru",
    "query": "Shojumaru",
    "stack": "'Shojumaru', 'Corbel', 'Candara', sans-serif",
    "weight": "800",
    "style": "normal",
    "spacing": "1.2px",
    "transform": "none"
  },
  {
    "id": 14,
    "name": "Metal Mania",
    "query": "Metal+Mania",
    "stack": "'Metal Mania', 'Constantia', 'Baskerville', serif",
    "weight": "900",
    "style": "italic",
    "spacing": "2px",
    "transform": "uppercase"
  },
  {
    "id": 15,
    "name": "Rye",
    "query": "Rye",
    "stack": "'Rye', 'Verdana', 'Tahoma', sans-serif",
    "weight": "300",
    "style": "normal",
    "spacing": "3px",
    "transform": "lowercase"
  },
  {
    "id": 16,
    "name": "Sancreek",
    "query": "Sancreek",
    "stack": "'Sancreek', 'Rockwell', 'Courier New', serif",
    "weight": "400",
    "style": "italic",
    "spacing": "4px",
    "transform": "capitalize"
  },
  {
    "id": 17,
    "name": "Henny Penny",
    "query": "Henny+Penny",
    "stack": "'Henny Penny', 'Marlett', 'Impact', fantasy",
    "weight": "500",
    "style": "normal",
    "spacing": "-1.5px",
    "transform": "none"
  },
  {
    "id": 18,
    "name": "Trade Winds",
    "query": "Trade+Winds",
    "stack": "'Trade Winds', 'MS Gothic', 'MingLiU-ExtB', monospace",
    "weight": "600",
    "style": "italic",
    "spacing": "-0.8px",
    "transform": "uppercase"
  },
  {
    "id": 19,
    "name": "Eater",
    "query": "Eater",
    "stack": "'Eater', 'MV Boli', 'Comic Sans MS', cursive",
    "weight": "700",
    "style": "normal",
    "spacing": "0px",
    "transform": "lowercase"
  },
  {
    "id": 20,
    "name": "Dr Sugiyama",
    "query": "Dr+Sugiyama",
    "stack": "'Dr Sugiyama', 'Sylfaen', 'Times New Roman', serif",
    "weight": "800",
    "style": "italic",
    "spacing": "0.5px",
    "transform": "capitalize"
  },
  {
    "id": 21,
    "name": "Press Start 2P",
    "query": "Press+Start+2P",
    "stack": "'Press Start 2P', 'Jokerman', 'Chiller', 'Impact', fantasy",
    "weight": "900",
    "style": "normal",
    "spacing": "1.2px",
    "transform": "none"
  },
  {
    "id": 22,
    "name": "VT323",
    "query": "VT323",
    "stack": "'VT323', 'Brush Script MT', 'Segoe Script', 'Monotype Corsiva', cursive",
    "weight": "300",
    "style": "italic",
    "spacing": "2px",
    "transform": "uppercase"
  },
  {
    "id": 23,
    "name": "Silkscreen",
    "query": "Silkscreen",
    "stack": "'Silkscreen', 'Consolas', 'Cascadia Code', 'Courier New', monospace",
    "weight": "400",
    "style": "normal",
    "spacing": "3px",
    "transform": "lowercase"
  },
  {
    "id": 24,
    "name": "Wallpoet",
    "query": "Wallpoet",
    "stack": "'Wallpoet', 'Georgia', 'Palatino Linotype', 'Book Antiqua', serif",
    "weight": "500",
    "style": "italic",
    "spacing": "4px",
    "transform": "capitalize"
  },
  {
    "id": 25,
    "name": "Rubik Glitch",
    "query": "Rubik+Glitch",
    "stack": "'Rubik Glitch', 'Trebuchet MS', 'Arial Black', 'Franklin Gothic Medium', sans-serif",
    "weight": "600",
    "style": "normal",
    "spacing": "-1.5px",
    "transform": "none"
  },
  {
    "id": 26,
    "name": "Rubik Iso",
    "query": "Rubik+Iso",
    "stack": "'Rubik Iso', 'Copperplate', 'Papyrus', 'Impact', fantasy",
    "weight": "700",
    "style": "italic",
    "spacing": "-0.8px",
    "transform": "uppercase"
  },
  {
    "id": 27,
    "name": "Rubik Vinyl",
    "query": "Rubik+Vinyl",
    "stack": "'Rubik Vinyl', 'Lucida Console', 'Lucida Sans Unicode', monospace",
    "weight": "800",
    "style": "normal",
    "spacing": "0px",
    "transform": "lowercase"
  },
  {
    "id": 28,
    "name": "Rubik Puddles",
    "query": "Rubik+Puddles",
    "stack": "'Rubik Puddles', 'Gabriola', 'Segoe Print', cursive",
    "weight": "900",
    "style": "italic",
    "spacing": "0.5px",
    "transform": "capitalize"
  },
  {
    "id": 29,
    "name": "Rubik Microbe",
    "query": "Rubik+Microbe",
    "stack": "'Rubik Microbe', 'Bahnschrift', 'Franklin Gothic Heavy', sans-serif",
    "weight": "300",
    "style": "normal",
    "spacing": "1.2px",
    "transform": "none"
  },
  {
    "id": 30,
    "name": "Rubik Spray Paint",
    "query": "Rubik+Spray+Paint",
    "stack": "'Rubik Spray Paint', 'Ebrima', 'Segoe UI Semibold', sans-serif",
    "weight": "400",
    "style": "italic",
    "spacing": "2px",
    "transform": "uppercase"
  },
  {
    "id": 31,
    "name": "Rubik Wet Paint",
    "query": "Rubik+Wet+Paint",
    "stack": "'Rubik Wet Paint', 'Sitka Text', 'Cambria', serif",
    "weight": "500",
    "style": "normal",
    "spacing": "3px",
    "transform": "lowercase"
  },
  {
    "id": 32,
    "name": "Rubik Pixels",
    "query": "Rubik+Pixels",
    "stack": "'Rubik Pixels', 'Ink Free', 'Comic Sans MS', cursive",
    "weight": "600",
    "style": "italic",
    "spacing": "4px",
    "transform": "capitalize"
  },
  {
    "id": 33,
    "name": "Rubik Lines",
    "query": "Rubik+Lines",
    "stack": "'Rubik Lines', 'Corbel', 'Candara', sans-serif",
    "weight": "700",
    "style": "normal",
    "spacing": "-1.5px",
    "transform": "none"
  },
  {
    "id": 34,
    "name": "Rubik Marker Hatch",
    "query": "Rubik+Marker+Hatch",
    "stack": "'Rubik Marker Hatch', 'Constantia', 'Baskerville', serif",
    "weight": "800",
    "style": "italic",
    "spacing": "-0.8px",
    "transform": "uppercase"
  },
  {
    "id": 35,
    "name": "DotGothic16",
    "query": "DotGothic16",
    "stack": "'DotGothic16', 'Verdana', 'Tahoma', sans-serif",
    "weight": "900",
    "style": "normal",
    "spacing": "0px",
    "transform": "lowercase"
  },
  {
    "id": 36,
    "name": "Pixelify Sans",
    "query": "Pixelify+Sans",
    "stack": "'Pixelify Sans', 'Rockwell', 'Courier New', serif",
    "weight": "300",
    "style": "italic",
    "spacing": "0.5px",
    "transform": "capitalize"
  },
  {
    "id": 37,
    "name": "Chakra Petch",
    "query": "Chakra+Petch",
    "stack": "'Chakra Petch', 'Marlett', 'Impact', fantasy",
    "weight": "400",
    "style": "normal",
    "spacing": "1.2px",
    "transform": "none"
  },
  {
    "id": 38,
    "name": "Micro 5",
    "query": "Micro+5",
    "stack": "'Micro 5', 'MS Gothic', 'MingLiU-ExtB', monospace",
    "weight": "500",
    "style": "italic",
    "spacing": "2px",
    "transform": "uppercase"
  },
  {
    "id": 39,
    "name": "Jacquard 12",
    "query": "Jacquard+12",
    "stack": "'Jacquard 12', 'MV Boli', 'Comic Sans MS', cursive",
    "weight": "600",
    "style": "normal",
    "spacing": "3px",
    "transform": "lowercase"
  },
  {
    "id": 40,
    "name": "Pacifico",
    "query": "Pacifico",
    "stack": "'Pacifico', 'Sylfaen', 'Times New Roman', serif",
    "weight": "700",
    "style": "italic",
    "spacing": "4px",
    "transform": "capitalize"
  },
  {
    "id": 41,
    "name": "Caveat",
    "query": "Caveat",
    "stack": "'Caveat', 'Jokerman', 'Chiller', 'Impact', fantasy",
    "weight": "800",
    "style": "normal",
    "spacing": "-1.5px",
    "transform": "none"
  },
  {
    "id": 42,
    "name": "Permanent Marker",
    "query": "Permanent+Marker",
    "stack": "'Permanent Marker', 'Brush Script MT', 'Segoe Script', 'Monotype Corsiva', cursive",
    "weight": "900",
    "style": "italic",
    "spacing": "-0.8px",
    "transform": "uppercase"
  },
  {
    "id": 43,
    "name": "Dancing Script",
    "query": "Dancing+Script",
    "stack": "'Dancing Script', 'Consolas', 'Cascadia Code', 'Courier New', monospace",
    "weight": "300",
    "style": "normal",
    "spacing": "0px",
    "transform": "lowercase"
  },
  {
    "id": 44,
    "name": "Sacramento",
    "query": "Sacramento",
    "stack": "'Sacramento', 'Georgia', 'Palatino Linotype', 'Book Antiqua', serif",
    "weight": "400",
    "style": "italic",
    "spacing": "0.5px",
    "transform": "capitalize"
  },
  {
    "id": 45,
    "name": "Satisfy",
    "query": "Satisfy",
    "stack": "'Satisfy', 'Trebuchet MS', 'Arial Black', 'Franklin Gothic Medium', sans-serif",
    "weight": "500",
    "style": "normal",
    "spacing": "1.2px",
    "transform": "none"
  },
  {
    "id": 46,
    "name": "Shadows Into Light",
    "query": "Shadows+Into+Light",
    "stack": "'Shadows Into Light', 'Copperplate', 'Papyrus', 'Impact', fantasy",
    "weight": "600",
    "style": "italic",
    "spacing": "2px",
    "transform": "uppercase"
  },
  {
    "id": 47,
    "name": "Amatic SC",
    "query": "Amatic+SC",
    "stack": "'Amatic SC', 'Lucida Console', 'Lucida Sans Unicode', monospace",
    "weight": "700",
    "style": "normal",
    "spacing": "3px",
    "transform": "lowercase"
  },
  {
    "id": 48,
    "name": "Great Vibes",
    "query": "Great+Vibes",
    "stack": "'Great Vibes', 'Gabriola', 'Segoe Print', cursive",
    "weight": "800",
    "style": "italic",
    "spacing": "4px",
    "transform": "capitalize"
  },
  {
    "id": 49,
    "name": "Indie Flower",
    "query": "Indie+Flower",
    "stack": "'Indie Flower', 'Bahnschrift', 'Franklin Gothic Heavy', sans-serif",
    "weight": "900",
    "style": "normal",
    "spacing": "-1.5px",
    "transform": "none"
  },
  {
    "id": 50,
    "name": "Kaushan Script",
    "query": "Kaushan+Script",
    "stack": "'Kaushan Script', 'Ebrima', 'Segoe UI Semibold', sans-serif",
    "weight": "300",
    "style": "italic",
    "spacing": "-0.8px",
    "transform": "uppercase"
  },
  {
    "id": 51,
    "name": "Marck Script",
    "query": "Marck+Script",
    "stack": "'Marck Script', 'Sitka Text', 'Cambria', serif",
    "weight": "400",
    "style": "normal",
    "spacing": "0px",
    "transform": "lowercase"
  },
  {
    "id": 52,
    "name": "Courgette",
    "query": "Courgette",
    "stack": "'Courgette', 'Ink Free', 'Comic Sans MS', cursive",
    "weight": "500",
    "style": "italic",
    "spacing": "0.5px",
    "transform": "capitalize"
  },
  {
    "id": 53,
    "name": "Alex Brush",
    "query": "Alex+Brush",
    "stack": "'Alex Brush', 'Corbel', 'Candara', sans-serif",
    "weight": "600",
    "style": "normal",
    "spacing": "1.2px",
    "transform": "none"
  },
  {
    "id": 54,
    "name": "Cookie",
    "query": "Cookie",
    "stack": "'Cookie', 'Constantia', 'Baskerville', serif",
    "weight": "700",
    "style": "italic",
    "spacing": "2px",
    "transform": "uppercase"
  },
  {
    "id": 55,
    "name": "Yellowtail",
    "query": "Yellowtail",
    "stack": "'Yellowtail', 'Verdana', 'Tahoma', sans-serif",
    "weight": "800",
    "style": "normal",
    "spacing": "3px",
    "transform": "lowercase"
  },
  {
    "id": 56,
    "name": "Allura",
    "query": "Allura",
    "stack": "'Allura', 'Rockwell', 'Courier New', serif",
    "weight": "900",
    "style": "italic",
    "spacing": "4px",
    "transform": "capitalize"
  },
  {
    "id": 57,
    "name": "Parisienne",
    "query": "Parisienne",
    "stack": "'Parisienne', 'Marlett', 'Impact', fantasy",
    "weight": "300",
    "style": "normal",
    "spacing": "-1.5px",
    "transform": "none"
  },
  {
    "id": 58,
    "name": "Homemade Apple",
    "query": "Homemade+Apple",
    "stack": "'Homemade Apple', 'MS Gothic', 'MingLiU-ExtB', monospace",
    "weight": "400",
    "style": "italic",
    "spacing": "-0.8px",
    "transform": "uppercase"
  },
  {
    "id": 59,
    "name": "Rock Salt",
    "query": "Rock+Salt",
    "stack": "'Rock Salt', 'MV Boli', 'Comic Sans MS', cursive",
    "weight": "500",
    "style": "normal",
    "spacing": "0px",
    "transform": "lowercase"
  },
  {
    "id": 60,
    "name": "Covered By Your Grace",
    "query": "Covered+By+Your+Grace",
    "stack": "'Covered By Your Grace', 'Sylfaen', 'Times New Roman', serif",
    "weight": "600",
    "style": "italic",
    "spacing": "0.5px",
    "transform": "capitalize"
  },
  {
    "id": 61,
    "name": "Reenie Beanie",
    "query": "Reenie+Beanie",
    "stack": "'Reenie Beanie', 'Jokerman', 'Chiller', 'Impact', fantasy",
    "weight": "700",
    "style": "normal",
    "spacing": "1.2px",
    "transform": "none"
  },
  {
    "id": 62,
    "name": "Nothing You Could Do",
    "query": "Nothing+You+Could+Do",
    "stack": "'Nothing You Could Do', 'Brush Script MT', 'Segoe Script', 'Monotype Corsiva', cursive",
    "weight": "800",
    "style": "italic",
    "spacing": "2px",
    "transform": "uppercase"
  },
  {
    "id": 63,
    "name": "Zeyada",
    "query": "Zeyada",
    "stack": "'Zeyada', 'Consolas', 'Cascadia Code', 'Courier New', monospace",
    "weight": "900",
    "style": "normal",
    "spacing": "3px",
    "transform": "lowercase"
  },
  {
    "id": 64,
    "name": "Loved by the King",
    "query": "Loved+by+the+King",
    "stack": "'Loved by the King', 'Georgia', 'Palatino Linotype', 'Book Antiqua', serif",
    "weight": "300",
    "style": "italic",
    "spacing": "4px",
    "transform": "capitalize"
  },
  {
    "id": 65,
    "name": "La Belle Aurore",
    "query": "La+Belle+Aurore",
    "stack": "'La Belle Aurore', 'Trebuchet MS', 'Arial Black', 'Franklin Gothic Medium', sans-serif",
    "weight": "400",
    "style": "normal",
    "spacing": "-1.5px",
    "transform": "none"
  },
  {
    "id": 66,
    "name": "Give You Glory",
    "query": "Give+You+Glory",
    "stack": "'Give You Glory', 'Copperplate', 'Papyrus', 'Impact', fantasy",
    "weight": "500",
    "style": "italic",
    "spacing": "-0.8px",
    "transform": "uppercase"
  },
  {
    "id": 67,
    "name": "Waiting for the Sunrise",
    "query": "Waiting+for+the+Sunrise",
    "stack": "'Waiting for the Sunrise', 'Lucida Console', 'Lucida Sans Unicode', monospace",
    "weight": "600",
    "style": "normal",
    "spacing": "0px",
    "transform": "lowercase"
  },
  {
    "id": 68,
    "name": "Over the Rainbow",
    "query": "Over+the+Rainbow",
    "stack": "'Over the Rainbow', 'Gabriola', 'Segoe Print', cursive",
    "weight": "700",
    "style": "italic",
    "spacing": "0.5px",
    "transform": "capitalize"
  },
  {
    "id": 69,
    "name": "The Girl Next Door",
    "query": "The+Girl+Next+Door",
    "stack": "'The Girl Next Door', 'Bahnschrift', 'Franklin Gothic Heavy', sans-serif",
    "weight": "800",
    "style": "normal",
    "spacing": "1.2px",
    "transform": "none"
  },
  {
    "id": 70,
    "name": "Just Another Hand",
    "query": "Just+Another+Hand",
    "stack": "'Just Another Hand', 'Ebrima', 'Segoe UI Semibold', sans-serif",
    "weight": "900",
    "style": "italic",
    "spacing": "2px",
    "transform": "uppercase"
  },
  {
    "id": 71,
    "name": "Kristi",
    "query": "Kristi",
    "stack": "'Kristi', 'Sitka Text', 'Cambria', serif",
    "weight": "300",
    "style": "normal",
    "spacing": "3px",
    "transform": "lowercase"
  },
  {
    "id": 72,
    "name": "Herr Von Muellerhoff",
    "query": "Herr+Von+Muellerhoff",
    "stack": "'Herr Von Muellerhoff', 'Ink Free', 'Comic Sans MS', cursive",
    "weight": "400",
    "style": "italic",
    "spacing": "4px",
    "transform": "capitalize"
  },
  {
    "id": 73,
    "name": "Aguafina Script",
    "query": "Aguafina+Script",
    "stack": "'Aguafina Script', 'Corbel', 'Candara', sans-serif",
    "weight": "500",
    "style": "normal",
    "spacing": "-1.5px",
    "transform": "none"
  },
  {
    "id": 74,
    "name": "Rouge Script",
    "query": "Rouge+Script",
    "stack": "'Rouge Script', 'Constantia', 'Baskerville', serif",
    "weight": "600",
    "style": "italic",
    "spacing": "-0.8px",
    "transform": "uppercase"
  },
  {
    "id": 75,
    "name": "Mr De Haviland",
    "query": "Mr+De+Haviland",
    "stack": "'Mr De Haviland', 'Verdana', 'Tahoma', sans-serif",
    "weight": "700",
    "style": "normal",
    "spacing": "0px",
    "transform": "lowercase"
  },
  {
    "id": 76,
    "name": "Monsieur La Doulaise",
    "query": "Monsieur+La+Doulaise",
    "stack": "'Monsieur La Doulaise', 'Rockwell', 'Courier New', serif",
    "weight": "800",
    "style": "italic",
    "spacing": "0.5px",
    "transform": "capitalize"
  },
  {
    "id": 77,
    "name": "Stalemate",
    "query": "Stalemate",
    "stack": "'Stalemate', 'Marlett', 'Impact', fantasy",
    "weight": "900",
    "style": "normal",
    "spacing": "1.2px",
    "transform": "none"
  },
  {
    "id": 78,
    "name": "Jim Nightshade",
    "query": "Jim+Nightshade",
    "stack": "'Jim Nightshade', 'MS Gothic', 'MingLiU-ExtB', monospace",
    "weight": "300",
    "style": "italic",
    "spacing": "2px",
    "transform": "uppercase"
  },
  {
    "id": 79,
    "name": "Felipa",
    "query": "Felipa",
    "stack": "'Felipa', 'MV Boli', 'Comic Sans MS', cursive",
    "weight": "400",
    "style": "normal",
    "spacing": "3px",
    "transform": "lowercase"
  },
  {
    "id": 80,
    "name": "Orbitron",
    "query": "Orbitron",
    "stack": "'Orbitron', 'Sylfaen', 'Times New Roman', serif",
    "weight": "500",
    "style": "italic",
    "spacing": "4px",
    "transform": "capitalize"
  },
  {
    "id": 81,
    "name": "Audiowide",
    "query": "Audiowide",
    "stack": "'Audiowide', 'Jokerman', 'Chiller', 'Impact', fantasy",
    "weight": "600",
    "style": "normal",
    "spacing": "-1.5px",
    "transform": "none"
  },
  {
    "id": 82,
    "name": "Electrolize",
    "query": "Electrolize",
    "stack": "'Electrolize', 'Brush Script MT', 'Segoe Script', 'Monotype Corsiva', cursive",
    "weight": "700",
    "style": "italic",
    "spacing": "-0.8px",
    "transform": "uppercase"
  },
  {
    "id": 83,
    "name": "Michroma",
    "query": "Michroma",
    "stack": "'Michroma', 'Consolas', 'Cascadia Code', 'Courier New', monospace",
    "weight": "800",
    "style": "normal",
    "spacing": "0px",
    "transform": "lowercase"
  },
  {
    "id": 84,
    "name": "Syncopate",
    "query": "Syncopate",
    "stack": "'Syncopate', 'Georgia', 'Palatino Linotype', 'Book Antiqua', serif",
    "weight": "900",
    "style": "italic",
    "spacing": "0.5px",
    "transform": "capitalize"
  },
  {
    "id": 85,
    "name": "Exo 2",
    "query": "Exo+2",
    "stack": "'Exo 2', 'Trebuchet MS', 'Arial Black', 'Franklin Gothic Medium', sans-serif",
    "weight": "300",
    "style": "normal",
    "spacing": "1.2px",
    "transform": "none"
  },
  {
    "id": 86,
    "name": "Teko",
    "query": "Teko",
    "stack": "'Teko', 'Copperplate', 'Papyrus', 'Impact', fantasy",
    "weight": "400",
    "style": "italic",
    "spacing": "2px",
    "transform": "uppercase"
  },
  {
    "id": 87,
    "name": "Rajdhani",
    "query": "Rajdhani",
    "stack": "'Rajdhani', 'Lucida Console', 'Lucida Sans Unicode', monospace",
    "weight": "500",
    "style": "normal",
    "spacing": "3px",
    "transform": "lowercase"
  },
  {
    "id": 88,
    "name": "Share Tech",
    "query": "Share+Tech",
    "stack": "'Share Tech', 'Gabriola', 'Segoe Print', cursive",
    "weight": "600",
    "style": "italic",
    "spacing": "4px",
    "transform": "capitalize"
  },
  {
    "id": 89,
    "name": "Saira Stencil One",
    "query": "Saira+Stencil+One",
    "stack": "'Saira Stencil One', 'Bahnschrift', 'Franklin Gothic Heavy', sans-serif",
    "weight": "700",
    "style": "normal",
    "spacing": "-1.5px",
    "transform": "none"
  },
  {
    "id": 90,
    "name": "Staatliches",
    "query": "Staatliches",
    "stack": "'Staatliches', 'Ebrima', 'Segoe UI Semibold', sans-serif",
    "weight": "800",
    "style": "italic",
    "spacing": "-0.8px",
    "transform": "uppercase"
  },
  {
    "id": 91,
    "name": "Allerta Stencil",
    "query": "Allerta+Stencil",
    "stack": "'Allerta Stencil', 'Sitka Text', 'Cambria', serif",
    "weight": "900",
    "style": "normal",
    "spacing": "0px",
    "transform": "lowercase"
  },
  {
    "id": 92,
    "name": "Black Ops One",
    "query": "Black+Ops+One",
    "stack": "'Black Ops One', 'Ink Free', 'Comic Sans MS', cursive",
    "weight": "300",
    "style": "italic",
    "spacing": "0.5px",
    "transform": "capitalize"
  },
  {
    "id": 93,
    "name": "Quantico",
    "query": "Quantico",
    "stack": "'Quantico', 'Corbel', 'Candara', sans-serif",
    "weight": "400",
    "style": "normal",
    "spacing": "1.2px",
    "transform": "none"
  },
  {
    "id": 94,
    "name": "Bruno Ace SC",
    "query": "Bruno+Ace+SC",
    "stack": "'Bruno Ace SC', 'Constantia', 'Baskerville', serif",
    "weight": "500",
    "style": "italic",
    "spacing": "2px",
    "transform": "uppercase"
  },
  {
    "id": 95,
    "name": "Blaka",
    "query": "Blaka",
    "stack": "'Blaka', 'Verdana', 'Tahoma', sans-serif",
    "weight": "600",
    "style": "normal",
    "spacing": "3px",
    "transform": "lowercase"
  },
  {
    "id": 96,
    "name": "Blaka Hollow",
    "query": "Blaka+Hollow",
    "stack": "'Blaka Hollow', 'Rockwell', 'Courier New', serif",
    "weight": "700",
    "style": "italic",
    "spacing": "4px",
    "transform": "capitalize"
  },
  {
    "id": 97,
    "name": "Zen Dots",
    "query": "Zen+Dots",
    "stack": "'Zen Dots', 'Marlett', 'Impact', fantasy",
    "weight": "800",
    "style": "normal",
    "spacing": "-1.5px",
    "transform": "none"
  },
  {
    "id": 98,
    "name": "Turret Road",
    "query": "Turret+Road",
    "stack": "'Turret Road', 'MS Gothic', 'MingLiU-ExtB', monospace",
    "weight": "900",
    "style": "italic",
    "spacing": "-0.8px",
    "transform": "uppercase"
  },
  {
    "id": 99,
    "name": "Oxanium",
    "query": "Oxanium",
    "stack": "'Oxanium', 'MV Boli', 'Comic Sans MS', cursive",
    "weight": "300",
    "style": "normal",
    "spacing": "0px",
    "transform": "lowercase"
  },
  {
    "id": 100,
    "name": "Monda",
    "query": "Monda",
    "stack": "'Monda', 'Sylfaen', 'Times New Roman', serif",
    "weight": "400",
    "style": "italic",
    "spacing": "0.5px",
    "transform": "capitalize"
  },
  {
    "id": 101,
    "name": "UnifrakturMaguntia",
    "query": "UnifrakturMaguntia",
    "stack": "'UnifrakturMaguntia', 'Jokerman', 'Chiller', 'Impact', fantasy",
    "weight": "500",
    "style": "normal",
    "spacing": "1.2px",
    "transform": "none"
  },
  {
    "id": 102,
    "name": "UnifrakturCook",
    "query": "UnifrakturCook",
    "stack": "'UnifrakturCook', 'Brush Script MT', 'Segoe Script', 'Monotype Corsiva', cursive",
    "weight": "600",
    "style": "italic",
    "spacing": "2px",
    "transform": "uppercase"
  },
  {
    "id": 103,
    "name": "Pirata One",
    "query": "Pirata+One",
    "stack": "'Pirata One', 'Consolas', 'Cascadia Code', 'Courier New', monospace",
    "weight": "700",
    "style": "normal",
    "spacing": "3px",
    "transform": "lowercase"
  },
  {
    "id": 104,
    "name": "MedievalSharp",
    "query": "MedievalSharp",
    "stack": "'MedievalSharp', 'Georgia', 'Palatino Linotype', 'Book Antiqua', serif",
    "weight": "800",
    "style": "italic",
    "spacing": "4px",
    "transform": "capitalize"
  },
  {
    "id": 105,
    "name": "Eczar",
    "query": "Eczar",
    "stack": "'Eczar', 'Trebuchet MS', 'Arial Black', 'Franklin Gothic Medium', sans-serif",
    "weight": "900",
    "style": "normal",
    "spacing": "-1.5px",
    "transform": "none"
  },
  {
    "id": 106,
    "name": "Almendra Display",
    "query": "Almendra+Display",
    "stack": "'Almendra Display', 'Copperplate', 'Papyrus', 'Impact', fantasy",
    "weight": "300",
    "style": "italic",
    "spacing": "-0.8px",
    "transform": "uppercase"
  },
  {
    "id": 107,
    "name": "Diplomata SC",
    "query": "Diplomata+SC",
    "stack": "'Diplomata SC', 'Lucida Console', 'Lucida Sans Unicode', monospace",
    "weight": "400",
    "style": "normal",
    "spacing": "0px",
    "transform": "lowercase"
  },
  {
    "id": 108,
    "name": "Diplomata",
    "query": "Diplomata",
    "stack": "'Diplomata', 'Gabriola', 'Segoe Print', cursive",
    "weight": "500",
    "style": "italic",
    "spacing": "0.5px",
    "transform": "capitalize"
  },
  {
    "id": 109,
    "name": "Fascinate",
    "query": "Fascinate",
    "stack": "'Fascinate', 'Bahnschrift', 'Franklin Gothic Heavy', sans-serif",
    "weight": "600",
    "style": "normal",
    "spacing": "1.2px",
    "transform": "none"
  },
  {
    "id": 110,
    "name": "Fascinate Inline",
    "query": "Fascinate+Inline",
    "stack": "'Fascinate Inline', 'Ebrima', 'Segoe UI Semibold', sans-serif",
    "weight": "700",
    "style": "italic",
    "spacing": "2px",
    "transform": "uppercase"
  },
  {
    "id": 111,
    "name": "Geostar",
    "query": "Geostar",
    "stack": "'Geostar', 'Sitka Text', 'Cambria', serif",
    "weight": "800",
    "style": "normal",
    "spacing": "3px",
    "transform": "lowercase"
  },
  {
    "id": 112,
    "name": "Geostar Fill",
    "query": "Geostar+Fill",
    "stack": "'Geostar Fill', 'Ink Free', 'Comic Sans MS', cursive",
    "weight": "900",
    "style": "italic",
    "spacing": "4px",
    "transform": "capitalize"
  },
  {
    "id": 113,
    "name": "Vast Shadow",
    "query": "Vast+Shadow",
    "stack": "'Vast Shadow', 'Corbel', 'Candara', sans-serif",
    "weight": "300",
    "style": "normal",
    "spacing": "-1.5px",
    "transform": "none"
  },
  {
    "id": 114,
    "name": "Monoton",
    "query": "Monoton",
    "stack": "'Monoton', 'Constantia', 'Baskerville', serif",
    "weight": "400",
    "style": "italic",
    "spacing": "-0.8px",
    "transform": "uppercase"
  },
  {
    "id": 115,
    "name": "Bungee",
    "query": "Bungee",
    "stack": "'Bungee', 'Verdana', 'Tahoma', sans-serif",
    "weight": "500",
    "style": "normal",
    "spacing": "0px",
    "transform": "lowercase"
  },
  {
    "id": 116,
    "name": "Bungee Shade",
    "query": "Bungee+Shade",
    "stack": "'Bungee Shade', 'Rockwell', 'Courier New', serif",
    "weight": "600",
    "style": "italic",
    "spacing": "0.5px",
    "transform": "capitalize"
  },
  {
    "id": 117,
    "name": "Bungee Inline",
    "query": "Bungee+Inline",
    "stack": "'Bungee Inline', 'Marlett', 'Impact', fantasy",
    "weight": "700",
    "style": "normal",
    "spacing": "1.2px",
    "transform": "none"
  },
  {
    "id": 118,
    "name": "Bungee Outline",
    "query": "Bungee+Outline",
    "stack": "'Bungee Outline', 'MS Gothic', 'MingLiU-ExtB', monospace",
    "weight": "800",
    "style": "italic",
    "spacing": "2px",
    "transform": "uppercase"
  },
  {
    "id": 119,
    "name": "Bungee Hairline",
    "query": "Bungee+Hairline",
    "stack": "'Bungee Hairline', 'MV Boli', 'Comic Sans MS', cursive",
    "weight": "900",
    "style": "normal",
    "spacing": "3px",
    "transform": "lowercase"
  },
  {
    "id": 120,
    "name": "Faster One",
    "query": "Faster+One",
    "stack": "'Faster One', 'Sylfaen', 'Times New Roman', serif",
    "weight": "300",
    "style": "italic",
    "spacing": "4px",
    "transform": "capitalize"
  },
  {
    "id": 121,
    "name": "Megrim",
    "query": "Megrim",
    "stack": "'Megrim', 'Jokerman', 'Chiller', 'Impact', fantasy",
    "weight": "400",
    "style": "normal",
    "spacing": "-1.5px",
    "transform": "none"
  },
  {
    "id": 122,
    "name": "Plaster",
    "query": "Plaster",
    "stack": "'Plaster', 'Brush Script MT', 'Segoe Script', 'Monotype Corsiva', cursive",
    "weight": "500",
    "style": "italic",
    "spacing": "-0.8px",
    "transform": "uppercase"
  },
  {
    "id": 123,
    "name": "Londrina Outline",
    "query": "Londrina+Outline",
    "stack": "'Londrina Outline', 'Consolas', 'Cascadia Code', 'Courier New', monospace",
    "weight": "600",
    "style": "normal",
    "spacing": "0px",
    "transform": "lowercase"
  },
  {
    "id": 124,
    "name": "Londrina Shadow",
    "query": "Londrina+Shadow",
    "stack": "'Londrina Shadow', 'Georgia', 'Palatino Linotype', 'Book Antiqua', serif",
    "weight": "700",
    "style": "italic",
    "spacing": "0.5px",
    "transform": "capitalize"
  },
  {
    "id": 125,
    "name": "Londrina Sketch",
    "query": "Londrina+Sketch",
    "stack": "'Londrina Sketch', 'Trebuchet MS', 'Arial Black', 'Franklin Gothic Medium', sans-serif",
    "weight": "800",
    "style": "normal",
    "spacing": "1.2px",
    "transform": "none"
  },
  {
    "id": 126,
    "name": "Londrina Solid",
    "query": "Londrina+Solid",
    "stack": "'Londrina Solid', 'Copperplate', 'Papyrus', 'Impact', fantasy",
    "weight": "900",
    "style": "italic",
    "spacing": "2px",
    "transform": "uppercase"
  },
  {
    "id": 127,
    "name": "Codystar",
    "query": "Codystar",
    "stack": "'Codystar', 'Lucida Console', 'Lucida Sans Unicode', monospace",
    "weight": "300",
    "style": "normal",
    "spacing": "3px",
    "transform": "lowercase"
  },
  {
    "id": 128,
    "name": "Nixie One",
    "query": "Nixie+One",
    "stack": "'Nixie One', 'Gabriola', 'Segoe Print', cursive",
    "weight": "400",
    "style": "italic",
    "spacing": "4px",
    "transform": "capitalize"
  },
  {
    "id": 129,
    "name": "Erica One",
    "query": "Erica+One",
    "stack": "'Erica One', 'Bahnschrift', 'Franklin Gothic Heavy', sans-serif",
    "weight": "500",
    "style": "normal",
    "spacing": "-1.5px",
    "transform": "none"
  },
  {
    "id": 130,
    "name": "Kenia",
    "query": "Kenia",
    "stack": "'Kenia', 'Ebrima', 'Segoe UI Semibold', sans-serif",
    "weight": "600",
    "style": "italic",
    "spacing": "-0.8px",
    "transform": "uppercase"
  },
  {
    "id": 131,
    "name": "Warnes",
    "query": "Warnes",
    "stack": "'Warnes', 'Sitka Text', 'Cambria', serif",
    "weight": "700",
    "style": "normal",
    "spacing": "0px",
    "transform": "lowercase"
  },
  {
    "id": 132,
    "name": "Bangers",
    "query": "Bangers",
    "stack": "'Bangers', 'Ink Free', 'Comic Sans MS', cursive",
    "weight": "800",
    "style": "italic",
    "spacing": "0.5px",
    "transform": "capitalize"
  },
  {
    "id": 133,
    "name": "Luckiest Guy",
    "query": "Luckiest+Guy",
    "stack": "'Luckiest Guy', 'Corbel', 'Candara', sans-serif",
    "weight": "900",
    "style": "normal",
    "spacing": "1.2px",
    "transform": "none"
  },
  {
    "id": 134,
    "name": "Fredoka",
    "query": "Fredoka",
    "stack": "'Fredoka', 'Constantia', 'Baskerville', serif",
    "weight": "300",
    "style": "italic",
    "spacing": "2px",
    "transform": "uppercase"
  },
  {
    "id": 135,
    "name": "Sniglet",
    "query": "Sniglet",
    "stack": "'Sniglet', 'Verdana', 'Tahoma', sans-serif",
    "weight": "400",
    "style": "normal",
    "spacing": "3px",
    "transform": "lowercase"
  },
  {
    "id": 136,
    "name": "Chewy",
    "query": "Chewy",
    "stack": "'Chewy', 'Rockwell', 'Courier New', serif",
    "weight": "500",
    "style": "italic",
    "spacing": "4px",
    "transform": "capitalize"
  },
  {
    "id": 137,
    "name": "Chicle",
    "query": "Chicle",
    "stack": "'Chicle', 'Marlett', 'Impact', fantasy",
    "weight": "600",
    "style": "normal",
    "spacing": "-1.5px",
    "transform": "none"
  },
  {
    "id": 138,
    "name": "Boogaloo",
    "query": "Boogaloo",
    "stack": "'Boogaloo', 'MS Gothic', 'MingLiU-ExtB', monospace",
    "weight": "700",
    "style": "italic",
    "spacing": "-0.8px",
    "transform": "uppercase"
  },
  {
    "id": 139,
    "name": "Rammetto One",
    "query": "Rammetto+One",
    "stack": "'Rammetto One', 'MV Boli', 'Comic Sans MS', cursive",
    "weight": "800",
    "style": "normal",
    "spacing": "0px",
    "transform": "lowercase"
  },
  {
    "id": 140,
    "name": "Slackey",
    "query": "Slackey",
    "stack": "'Slackey', 'Sylfaen', 'Times New Roman', serif",
    "weight": "900",
    "style": "italic",
    "spacing": "0.5px",
    "transform": "capitalize"
  },
  {
    "id": 141,
    "name": "Spicy Rice",
    "query": "Spicy+Rice",
    "stack": "'Spicy Rice', 'Jokerman', 'Chiller', 'Impact', fantasy",
    "weight": "300",
    "style": "normal",
    "spacing": "1.2px",
    "transform": "none"
  },
  {
    "id": 142,
    "name": "Carter One",
    "query": "Carter+One",
    "stack": "'Carter One', 'Brush Script MT', 'Segoe Script', 'Monotype Corsiva', cursive",
    "weight": "400",
    "style": "italic",
    "spacing": "2px",
    "transform": "uppercase"
  },
  {
    "id": 143,
    "name": "Comic Neue",
    "query": "Comic+Neue",
    "stack": "'Comic Neue', 'Consolas', 'Cascadia Code', 'Courier New', monospace",
    "weight": "500",
    "style": "normal",
    "spacing": "3px",
    "transform": "lowercase"
  },
  {
    "id": 144,
    "name": "Shanti",
    "query": "Shanti",
    "stack": "'Shanti', 'Georgia', 'Palatino Linotype', 'Book Antiqua', serif",
    "weight": "600",
    "style": "italic",
    "spacing": "4px",
    "transform": "capitalize"
  },
  {
    "id": 145,
    "name": "Single Day",
    "query": "Single+Day",
    "stack": "'Single Day', 'Trebuchet MS', 'Arial Black', 'Franklin Gothic Medium', sans-serif",
    "weight": "700",
    "style": "normal",
    "spacing": "-1.5px",
    "transform": "none"
  },
  {
    "id": 146,
    "name": "Gaegu",
    "query": "Gaegu",
    "stack": "'Gaegu', 'Copperplate', 'Papyrus', 'Impact', fantasy",
    "weight": "800",
    "style": "italic",
    "spacing": "-0.8px",
    "transform": "uppercase"
  },
  {
    "id": 147,
    "name": "Cute Font",
    "query": "Cute+Font",
    "stack": "'Cute Font', 'Lucida Console', 'Lucida Sans Unicode', monospace",
    "weight": "900",
    "style": "normal",
    "spacing": "0px",
    "transform": "lowercase"
  },
  {
    "id": 148,
    "name": "Hi Melody",
    "query": "Hi+Melody",
    "stack": "'Hi Melody', 'Gabriola', 'Segoe Print', cursive",
    "weight": "300",
    "style": "italic",
    "spacing": "0.5px",
    "transform": "capitalize"
  },
  {
    "id": 149,
    "name": "Kirang Haerang",
    "query": "Kirang+Haerang",
    "stack": "'Kirang Haerang', 'Bahnschrift', 'Franklin Gothic Heavy', sans-serif",
    "weight": "400",
    "style": "normal",
    "spacing": "1.2px",
    "transform": "none"
  },
  {
    "id": 150,
    "name": "East Sea Dokdo",
    "query": "East+Sea+Dokdo",
    "stack": "'East Sea Dokdo', 'Ebrima', 'Segoe UI Semibold', sans-serif",
    "weight": "500",
    "style": "italic",
    "spacing": "2px",
    "transform": "uppercase"
  },
  {
    "id": 151,
    "name": "Poor Story",
    "query": "Poor+Story",
    "stack": "'Poor Story', 'Sitka Text', 'Cambria', serif",
    "weight": "600",
    "style": "normal",
    "spacing": "3px",
    "transform": "lowercase"
  },
  {
    "id": 152,
    "name": "Gamja Flower",
    "query": "Gamja+Flower",
    "stack": "'Gamja Flower', 'Ink Free', 'Comic Sans MS', cursive",
    "weight": "700",
    "style": "italic",
    "spacing": "4px",
    "transform": "capitalize"
  },
  {
    "id": 153,
    "name": "Abril Fatface",
    "query": "Abril+Fatface",
    "stack": "'Abril Fatface', 'Corbel', 'Candara', sans-serif",
    "weight": "800",
    "style": "normal",
    "spacing": "-1.5px",
    "transform": "none"
  },
  {
    "id": 154,
    "name": "Alfa Slab One",
    "query": "Alfa+Slab+One",
    "stack": "'Alfa Slab One', 'Constantia', 'Baskerville', serif",
    "weight": "900",
    "style": "italic",
    "spacing": "-0.8px",
    "transform": "uppercase"
  },
  {
    "id": 155,
    "name": "Ultra",
    "query": "Ultra",
    "stack": "'Ultra', 'Verdana', 'Tahoma', sans-serif",
    "weight": "300",
    "style": "normal",
    "spacing": "0px",
    "transform": "lowercase"
  },
  {
    "id": 156,
    "name": "Paytone One",
    "query": "Paytone+One",
    "stack": "'Paytone One', 'Rockwell', 'Courier New', serif",
    "weight": "400",
    "style": "italic",
    "spacing": "0.5px",
    "transform": "capitalize"
  },
  {
    "id": 157,
    "name": "Righteous",
    "query": "Righteous",
    "stack": "'Righteous', 'Marlett', 'Impact', fantasy",
    "weight": "500",
    "style": "normal",
    "spacing": "1.2px",
    "transform": "none"
  },
  {
    "id": 158,
    "name": "Sigmar",
    "query": "Sigmar",
    "stack": "'Sigmar', 'MS Gothic', 'MingLiU-ExtB', monospace",
    "weight": "600",
    "style": "italic",
    "spacing": "2px",
    "transform": "uppercase"
  },
  {
    "id": 159,
    "name": "Passion One",
    "query": "Passion+One",
    "stack": "'Passion One', 'MV Boli', 'Comic Sans MS', cursive",
    "weight": "700",
    "style": "normal",
    "spacing": "3px",
    "transform": "lowercase"
  },
  {
    "id": 160,
    "name": "Squada One",
    "query": "Squada+One",
    "stack": "'Squada One', 'Sylfaen', 'Times New Roman', serif",
    "weight": "800",
    "style": "italic",
    "spacing": "4px",
    "transform": "capitalize"
  },
  {
    "id": 161,
    "name": "Chango",
    "query": "Chango",
    "stack": "'Chango', 'Jokerman', 'Chiller', 'Impact', fantasy",
    "weight": "900",
    "style": "normal",
    "spacing": "-1.5px",
    "transform": "none"
  },
  {
    "id": 162,
    "name": "Gravitas One",
    "query": "Gravitas+One",
    "stack": "'Gravitas One', 'Brush Script MT', 'Segoe Script', 'Monotype Corsiva', cursive",
    "weight": "300",
    "style": "italic",
    "spacing": "-0.8px",
    "transform": "uppercase"
  },
  {
    "id": 163,
    "name": "Rozha One",
    "query": "Rozha+One",
    "stack": "'Rozha One', 'Consolas', 'Cascadia Code', 'Courier New', monospace",
    "weight": "400",
    "style": "normal",
    "spacing": "0px",
    "transform": "lowercase"
  },
  {
    "id": 164,
    "name": "Rubik One",
    "query": "Rubik+Mono+One",
    "stack": "'Rubik One', 'Georgia', 'Palatino Linotype', 'Book Antiqua', serif",
    "weight": "500",
    "style": "italic",
    "spacing": "0.5px",
    "transform": "capitalize"
  },
  {
    "id": 165,
    "name": "Stint Ultra Expanded",
    "query": "Stint+Ultra+Expanded",
    "stack": "'Stint Ultra Expanded', 'Trebuchet MS', 'Arial Black', 'Franklin Gothic Medium', sans-serif",
    "weight": "600",
    "style": "normal",
    "spacing": "1.2px",
    "transform": "none"
  },
  {
    "id": 166,
    "name": "Stint Ultra Condensed",
    "query": "Stint+Ultra+Condensed",
    "stack": "'Stint Ultra Condensed', 'Copperplate', 'Papyrus', 'Impact', fantasy",
    "weight": "700",
    "style": "italic",
    "spacing": "2px",
    "transform": "uppercase"
  },
  {
    "id": 167,
    "name": "Bowlby One",
    "query": "Bowlby+One",
    "stack": "'Bowlby One', 'Lucida Console', 'Lucida Sans Unicode', monospace",
    "weight": "800",
    "style": "normal",
    "spacing": "3px",
    "transform": "lowercase"
  },
  {
    "id": 168,
    "name": "Bowlby One SC",
    "query": "Bowlby+One+SC",
    "stack": "'Bowlby One SC', 'Gabriola', 'Segoe Print', cursive",
    "weight": "900",
    "style": "italic",
    "spacing": "4px",
    "transform": "capitalize"
  },
  {
    "id": 169,
    "name": "Vampiro One",
    "query": "Vampiro+One",
    "stack": "'Vampiro One', 'Bahnschrift', 'Franklin Gothic Heavy', sans-serif",
    "weight": "300",
    "style": "normal",
    "spacing": "-1.5px",
    "transform": "none"
  },
  {
    "id": 170,
    "name": "Playfair Display",
    "query": "Playfair+Display",
    "stack": "'Playfair Display', 'Ebrima', 'Segoe UI Semibold', sans-serif",
    "weight": "400",
    "style": "italic",
    "spacing": "-0.8px",
    "transform": "uppercase"
  },
  {
    "id": 171,
    "name": "Cinzel Decorative",
    "query": "Cinzel+Decorative",
    "stack": "'Cinzel Decorative', 'Sitka Text', 'Cambria', serif",
    "weight": "500",
    "style": "normal",
    "spacing": "0px",
    "transform": "lowercase"
  },
  {
    "id": 172,
    "name": "Bodoni Moda",
    "query": "Bodoni+Moda",
    "stack": "'Bodoni Moda', 'Ink Free', 'Comic Sans MS', cursive",
    "weight": "600",
    "style": "italic",
    "spacing": "0.5px",
    "transform": "capitalize"
  },
  {
    "id": 173,
    "name": "Cormorant Garamond",
    "query": "Cormorant+Garamond",
    "stack": "'Cormorant Garamond', 'Corbel', 'Candara', sans-serif",
    "weight": "700",
    "style": "normal",
    "spacing": "1.2px",
    "transform": "none"
  },
  {
    "id": 174,
    "name": "Prata",
    "query": "Prata",
    "stack": "'Prata', 'Constantia', 'Baskerville', serif",
    "weight": "800",
    "style": "italic",
    "spacing": "2px",
    "transform": "uppercase"
  },
  {
    "id": 175,
    "name": "Syne",
    "query": "Syne",
    "stack": "'Syne', 'Verdana', 'Tahoma', sans-serif",
    "weight": "900",
    "style": "normal",
    "spacing": "3px",
    "transform": "lowercase"
  },
  {
    "id": 176,
    "name": "DM Serif Display",
    "query": "DM+Serif+Display",
    "stack": "'DM Serif Display', 'Rockwell', 'Courier New', serif",
    "weight": "300",
    "style": "italic",
    "spacing": "4px",
    "transform": "capitalize"
  },
  {
    "id": 177,
    "name": "Fraunces",
    "query": "Fraunces",
    "stack": "'Fraunces', 'Marlett', 'Impact', fantasy",
    "weight": "400",
    "style": "normal",
    "spacing": "-1.5px",
    "transform": "none"
  },
  {
    "id": 178,
    "name": "Big Shoulders Display",
    "query": "Big+Shoulders+Display",
    "stack": "'Big Shoulders Display', 'MS Gothic', 'MingLiU-ExtB', monospace",
    "weight": "500",
    "style": "italic",
    "spacing": "-0.8px",
    "transform": "uppercase"
  },
  {
    "id": 179,
    "name": "Italiana",
    "query": "Italiana",
    "stack": "'Italiana', 'MV Boli', 'Comic Sans MS', cursive",
    "weight": "600",
    "style": "normal",
    "spacing": "0px",
    "transform": "lowercase"
  },
  {
    "id": 180,
    "name": "Forum",
    "query": "Forum",
    "stack": "'Forum', 'Sylfaen', 'Times New Roman', serif",
    "weight": "700",
    "style": "italic",
    "spacing": "0.5px",
    "transform": "capitalize"
  },
  {
    "id": 181,
    "name": "Cinzel",
    "query": "Cinzel",
    "stack": "'Cinzel', 'Jokerman', 'Chiller', 'Impact', fantasy",
    "weight": "800",
    "style": "normal",
    "spacing": "1.2px",
    "transform": "none"
  },
  {
    "id": 182,
    "name": "Castoro Titling",
    "query": "Castoro+Titling",
    "stack": "'Castoro Titling', 'Brush Script MT', 'Segoe Script', 'Monotype Corsiva', cursive",
    "weight": "900",
    "style": "italic",
    "spacing": "2px",
    "transform": "uppercase"
  },
  {
    "id": 183,
    "name": "Bellefair",
    "query": "Bellefair",
    "stack": "'Bellefair', 'Consolas', 'Cascadia Code', 'Courier New', monospace",
    "weight": "300",
    "style": "normal",
    "spacing": "3px",
    "transform": "lowercase"
  },
  {
    "id": 184,
    "name": "Fira Code",
    "query": "Fira+Code",
    "stack": "'Fira Code', 'Georgia', 'Palatino Linotype', 'Book Antiqua', serif",
    "weight": "400",
    "style": "italic",
    "spacing": "4px",
    "transform": "capitalize"
  },
  {
    "id": 185,
    "name": "JetBrains Mono",
    "query": "JetBrains+Mono",
    "stack": "'JetBrains Mono', 'Trebuchet MS', 'Arial Black', 'Franklin Gothic Medium', sans-serif",
    "weight": "500",
    "style": "normal",
    "spacing": "-1.5px",
    "transform": "none"
  },
  {
    "id": 186,
    "name": "Inconsolata",
    "query": "Inconsolata",
    "stack": "'Inconsolata', 'Copperplate', 'Papyrus', 'Impact', fantasy",
    "weight": "600",
    "style": "italic",
    "spacing": "-0.8px",
    "transform": "uppercase"
  },
  {
    "id": 187,
    "name": "Source Code Pro",
    "query": "Source+Code+Pro",
    "stack": "'Source Code Pro', 'Lucida Console', 'Lucida Sans Unicode', monospace",
    "weight": "700",
    "style": "normal",
    "spacing": "0px",
    "transform": "lowercase"
  },
  {
    "id": 188,
    "name": "Space Mono",
    "query": "Space+Mono",
    "stack": "'Space Mono', 'Gabriola', 'Segoe Print', cursive",
    "weight": "800",
    "style": "italic",
    "spacing": "0.5px",
    "transform": "capitalize"
  },
  {
    "id": 189,
    "name": "Courier Prime",
    "query": "Courier+Prime",
    "stack": "'Courier Prime', 'Bahnschrift', 'Franklin Gothic Heavy', sans-serif",
    "weight": "900",
    "style": "normal",
    "spacing": "1.2px",
    "transform": "none"
  },
  {
    "id": 190,
    "name": "Share Tech Mono",
    "query": "Share+Tech+Mono",
    "stack": "'Share Tech Mono', 'Ebrima', 'Segoe UI Semibold', sans-serif",
    "weight": "300",
    "style": "italic",
    "spacing": "2px",
    "transform": "uppercase"
  },
  {
    "id": 191,
    "name": "Anonymous Pro",
    "query": "Anonymous+Pro",
    "stack": "'Anonymous Pro', 'Sitka Text', 'Cambria', serif",
    "weight": "400",
    "style": "normal",
    "spacing": "3px",
    "transform": "lowercase"
  },
  {
    "id": 192,
    "name": "Cutive Mono",
    "query": "Cutive+Mono",
    "stack": "'Cutive Mono', 'Ink Free', 'Comic Sans MS', cursive",
    "weight": "500",
    "style": "italic",
    "spacing": "4px",
    "transform": "capitalize"
  },
  {
    "id": 193,
    "name": "Nova Mono",
    "query": "Nova+Mono",
    "stack": "'Nova Mono', 'Corbel', 'Candara', sans-serif",
    "weight": "600",
    "style": "normal",
    "spacing": "-1.5px",
    "transform": "none"
  },
  {
    "id": 194,
    "name": "Major Mono Display",
    "query": "Major+Mono+Display",
    "stack": "'Major Mono Display', 'Constantia', 'Baskerville', serif",
    "weight": "700",
    "style": "italic",
    "spacing": "-0.8px",
    "transform": "uppercase"
  },
  {
    "id": 195,
    "name": "Syne Mono",
    "query": "Syne+Mono",
    "stack": "'Syne Mono', 'Verdana', 'Tahoma', sans-serif",
    "weight": "800",
    "style": "normal",
    "spacing": "0px",
    "transform": "lowercase"
  },
  {
    "id": 196,
    "name": "Impact Vintage",
    "query": "Impact",
    "stack": "'Impact Vintage', 'Rockwell', 'Courier New', serif",
    "weight": "900",
    "style": "italic",
    "spacing": "0.5px",
    "transform": "capitalize"
  },
  {
    "id": 197,
    "name": "Comic Sans Original",
    "query": "Comic+Sans",
    "stack": "'Comic Sans Original', 'Marlett', 'Impact', fantasy",
    "weight": "300",
    "style": "normal",
    "spacing": "1.2px",
    "transform": "none"
  },
  {
    "id": 198,
    "name": "Courier Classic",
    "query": "Courier",
    "stack": "'Courier Classic', 'MS Gothic', 'MingLiU-ExtB', monospace",
    "weight": "400",
    "style": "italic",
    "spacing": "2px",
    "transform": "uppercase"
  },
  {
    "id": 199,
    "name": "Georgia Luxury",
    "query": "Georgia",
    "stack": "'Georgia Luxury', 'MV Boli', 'Comic Sans MS', cursive",
    "weight": "500",
    "style": "normal",
    "spacing": "3px",
    "transform": "lowercase"
  },
  {
    "id": 200,
    "name": "Trebuchet Clean",
    "query": "Trebuchet",
    "stack": "'Trebuchet Clean', 'Sylfaen', 'Times New Roman', serif",
    "weight": "600",
    "style": "italic",
    "spacing": "4px",
    "transform": "capitalize"
  },
  {
    "id": 201,
    "name": "Papyrus Classic",
    "query": "Papyrus",
    "stack": "'Papyrus Classic', 'Jokerman', 'Chiller', 'Impact', fantasy",
    "weight": "700",
    "style": "normal",
    "spacing": "-1.5px",
    "transform": "none"
  },
  {
    "id": 202,
    "name": "Copperplate Classic",
    "query": "Copperplate",
    "stack": "'Copperplate Classic', 'Brush Script MT', 'Segoe Script', 'Monotype Corsiva', cursive",
    "weight": "800",
    "style": "italic",
    "spacing": "-0.8px",
    "transform": "uppercase"
  },
  {
    "id": 203,
    "name": "Brush Script Classic",
    "query": "Brush+Script",
    "stack": "'Brush Script Classic', 'Consolas', 'Cascadia Code', 'Courier New', monospace",
    "weight": "900",
    "style": "normal",
    "spacing": "0px",
    "transform": "lowercase"
  },
  {
    "id": 204,
    "name": "Palatino Classic",
    "query": "Palatino",
    "stack": "'Palatino Classic', 'Georgia', 'Palatino Linotype', 'Book Antiqua', serif",
    "weight": "300",
    "style": "italic",
    "spacing": "0.5px",
    "transform": "capitalize"
  },
  {
    "id": 205,
    "name": "Garamond Classic",
    "query": "Garamond",
    "stack": "'Garamond Classic', 'Trebuchet MS', 'Arial Black', 'Franklin Gothic Medium', sans-serif",
    "weight": "400",
    "style": "normal",
    "spacing": "1.2px",
    "transform": "none"
  },
  {
    "id": 206,
    "name": "Creepster",
    "query": "Creepster",
    "stack": "'Creepster', 'Copperplate', 'Papyrus', 'Impact', fantasy",
    "weight": "500",
    "style": "italic",
    "spacing": "2px",
    "transform": "uppercase"
  },
  {
    "id": 207,
    "name": "Eater",
    "query": "Eater",
    "stack": "'Eater', 'Lucida Console', 'Lucida Sans Unicode', monospace",
    "weight": "600",
    "style": "normal",
    "spacing": "3px",
    "transform": "lowercase"
  },
  {
    "id": 208,
    "name": "Nosifer",
    "query": "Nosifer",
    "stack": "'Nosifer', 'Gabriola', 'Segoe Print', cursive",
    "weight": "700",
    "style": "italic",
    "spacing": "4px",
    "transform": "capitalize"
  },
  {
    "id": 209,
    "name": "Butcherman",
    "query": "Butcherman",
    "stack": "'Butcherman', 'Bahnschrift', 'Franklin Gothic Heavy', sans-serif",
    "weight": "800",
    "style": "normal",
    "spacing": "-1.5px",
    "transform": "none"
  },
  {
    "id": 210,
    "name": "Freckle Face",
    "query": "Freckle+Face",
    "stack": "'Freckle Face', 'Ebrima', 'Segoe UI Semibold', sans-serif",
    "weight": "900",
    "style": "italic",
    "spacing": "-0.8px",
    "transform": "uppercase"
  },
  {
    "id": 211,
    "name": "Jolly Lodger",
    "query": "Jolly+Lodger",
    "stack": "'Jolly Lodger', 'Sitka Text', 'Cambria', serif",
    "weight": "300",
    "style": "normal",
    "spacing": "0px",
    "transform": "lowercase"
  },
  {
    "id": 212,
    "name": "Frijole",
    "query": "Frijole",
    "stack": "'Frijole', 'Ink Free', 'Comic Sans MS', cursive",
    "weight": "400",
    "style": "italic",
    "spacing": "0.5px",
    "transform": "capitalize"
  },
  {
    "id": 213,
    "name": "Smokum",
    "query": "Smokum",
    "stack": "'Smokum', 'Corbel', 'Candara', sans-serif",
    "weight": "500",
    "style": "normal",
    "spacing": "1.2px",
    "transform": "none"
  },
  {
    "id": 214,
    "name": "Snowburst One",
    "query": "Snowburst+One",
    "stack": "'Snowburst One', 'Constantia', 'Baskerville', serif",
    "weight": "600",
    "style": "italic",
    "spacing": "2px",
    "transform": "uppercase"
  },
  {
    "id": 215,
    "name": "Barrio",
    "query": "Barrio",
    "stack": "'Barrio', 'Verdana', 'Tahoma', sans-serif",
    "weight": "700",
    "style": "normal",
    "spacing": "3px",
    "transform": "lowercase"
  },
  {
    "id": 216,
    "name": "New Rocker",
    "query": "New+Rocker",
    "stack": "'New Rocker', 'Rockwell', 'Courier New', serif",
    "weight": "800",
    "style": "italic",
    "spacing": "4px",
    "transform": "capitalize"
  },
  {
    "id": 217,
    "name": "Flavors",
    "query": "Flavors",
    "stack": "'Flavors', 'Marlett', 'Impact', fantasy",
    "weight": "900",
    "style": "normal",
    "spacing": "-1.5px",
    "transform": "none"
  },
  {
    "id": 218,
    "name": "Shojumaru",
    "query": "Shojumaru",
    "stack": "'Shojumaru', 'MS Gothic', 'MingLiU-ExtB', monospace",
    "weight": "300",
    "style": "italic",
    "spacing": "-0.8px",
    "transform": "uppercase"
  },
  {
    "id": 219,
    "name": "Metal Mania",
    "query": "Metal+Mania",
    "stack": "'Metal Mania', 'MV Boli', 'Comic Sans MS', cursive",
    "weight": "400",
    "style": "normal",
    "spacing": "0px",
    "transform": "lowercase"
  },
  {
    "id": 220,
    "name": "Rye",
    "query": "Rye",
    "stack": "'Rye', 'Sylfaen', 'Times New Roman', serif",
    "weight": "500",
    "style": "italic",
    "spacing": "0.5px",
    "transform": "capitalize"
  },
  {
    "id": 221,
    "name": "Sancreek",
    "query": "Sancreek",
    "stack": "'Sancreek', 'Jokerman', 'Chiller', 'Impact', fantasy",
    "weight": "600",
    "style": "normal",
    "spacing": "1.2px",
    "transform": "none"
  },
  {
    "id": 222,
    "name": "Henny Penny",
    "query": "Henny+Penny",
    "stack": "'Henny Penny', 'Brush Script MT', 'Segoe Script', 'Monotype Corsiva', cursive",
    "weight": "700",
    "style": "italic",
    "spacing": "2px",
    "transform": "uppercase"
  },
  {
    "id": 223,
    "name": "Trade Winds",
    "query": "Trade+Winds",
    "stack": "'Trade Winds', 'Consolas', 'Cascadia Code', 'Courier New', monospace",
    "weight": "800",
    "style": "normal",
    "spacing": "3px",
    "transform": "lowercase"
  },
  {
    "id": 224,
    "name": "Eater",
    "query": "Eater",
    "stack": "'Eater', 'Georgia', 'Palatino Linotype', 'Book Antiqua', serif",
    "weight": "900",
    "style": "italic",
    "spacing": "4px",
    "transform": "capitalize"
  },
  {
    "id": 225,
    "name": "Dr Sugiyama",
    "query": "Dr+Sugiyama",
    "stack": "'Dr Sugiyama', 'Trebuchet MS', 'Arial Black', 'Franklin Gothic Medium', sans-serif",
    "weight": "300",
    "style": "normal",
    "spacing": "-1.5px",
    "transform": "none"
  },
  {
    "id": 226,
    "name": "Press Start 2P",
    "query": "Press+Start+2P",
    "stack": "'Press Start 2P', 'Copperplate', 'Papyrus', 'Impact', fantasy",
    "weight": "400",
    "style": "italic",
    "spacing": "-0.8px",
    "transform": "uppercase"
  },
  {
    "id": 227,
    "name": "VT323",
    "query": "VT323",
    "stack": "'VT323', 'Lucida Console', 'Lucida Sans Unicode', monospace",
    "weight": "500",
    "style": "normal",
    "spacing": "0px",
    "transform": "lowercase"
  },
  {
    "id": 228,
    "name": "Silkscreen",
    "query": "Silkscreen",
    "stack": "'Silkscreen', 'Gabriola', 'Segoe Print', cursive",
    "weight": "600",
    "style": "italic",
    "spacing": "0.5px",
    "transform": "capitalize"
  },
  {
    "id": 229,
    "name": "Wallpoet",
    "query": "Wallpoet",
    "stack": "'Wallpoet', 'Bahnschrift', 'Franklin Gothic Heavy', sans-serif",
    "weight": "700",
    "style": "normal",
    "spacing": "1.2px",
    "transform": "none"
  },
  {
    "id": 230,
    "name": "Rubik Glitch",
    "query": "Rubik+Glitch",
    "stack": "'Rubik Glitch', 'Ebrima', 'Segoe UI Semibold', sans-serif",
    "weight": "800",
    "style": "italic",
    "spacing": "2px",
    "transform": "uppercase"
  },
  {
    "id": 231,
    "name": "Rubik Iso",
    "query": "Rubik+Iso",
    "stack": "'Rubik Iso', 'Sitka Text', 'Cambria', serif",
    "weight": "900",
    "style": "normal",
    "spacing": "3px",
    "transform": "lowercase"
  },
  {
    "id": 232,
    "name": "Rubik Vinyl",
    "query": "Rubik+Vinyl",
    "stack": "'Rubik Vinyl', 'Ink Free', 'Comic Sans MS', cursive",
    "weight": "300",
    "style": "italic",
    "spacing": "4px",
    "transform": "capitalize"
  },
  {
    "id": 233,
    "name": "Rubik Puddles",
    "query": "Rubik+Puddles",
    "stack": "'Rubik Puddles', 'Corbel', 'Candara', sans-serif",
    "weight": "400",
    "style": "normal",
    "spacing": "-1.5px",
    "transform": "none"
  },
  {
    "id": 234,
    "name": "Rubik Microbe",
    "query": "Rubik+Microbe",
    "stack": "'Rubik Microbe', 'Constantia', 'Baskerville', serif",
    "weight": "500",
    "style": "italic",
    "spacing": "-0.8px",
    "transform": "uppercase"
  },
  {
    "id": 235,
    "name": "Rubik Spray Paint",
    "query": "Rubik+Spray+Paint",
    "stack": "'Rubik Spray Paint', 'Verdana', 'Tahoma', sans-serif",
    "weight": "600",
    "style": "normal",
    "spacing": "0px",
    "transform": "lowercase"
  },
  {
    "id": 236,
    "name": "Rubik Wet Paint",
    "query": "Rubik+Wet+Paint",
    "stack": "'Rubik Wet Paint', 'Rockwell', 'Courier New', serif",
    "weight": "700",
    "style": "italic",
    "spacing": "0.5px",
    "transform": "capitalize"
  },
  {
    "id": 237,
    "name": "Rubik Pixels",
    "query": "Rubik+Pixels",
    "stack": "'Rubik Pixels', 'Marlett', 'Impact', fantasy",
    "weight": "800",
    "style": "normal",
    "spacing": "1.2px",
    "transform": "none"
  },
  {
    "id": 238,
    "name": "Rubik Lines",
    "query": "Rubik+Lines",
    "stack": "'Rubik Lines', 'MS Gothic', 'MingLiU-ExtB', monospace",
    "weight": "900",
    "style": "italic",
    "spacing": "2px",
    "transform": "uppercase"
  },
  {
    "id": 239,
    "name": "Rubik Marker Hatch",
    "query": "Rubik+Marker+Hatch",
    "stack": "'Rubik Marker Hatch', 'MV Boli', 'Comic Sans MS', cursive",
    "weight": "300",
    "style": "normal",
    "spacing": "3px",
    "transform": "lowercase"
  },
  {
    "id": 240,
    "name": "DotGothic16",
    "query": "DotGothic16",
    "stack": "'DotGothic16', 'Sylfaen', 'Times New Roman', serif",
    "weight": "400",
    "style": "italic",
    "spacing": "4px",
    "transform": "capitalize"
  },
  {
    "id": 241,
    "name": "Pixelify Sans",
    "query": "Pixelify+Sans",
    "stack": "'Pixelify Sans', 'Jokerman', 'Chiller', 'Impact', fantasy",
    "weight": "500",
    "style": "normal",
    "spacing": "-1.5px",
    "transform": "none"
  },
  {
    "id": 242,
    "name": "Chakra Petch",
    "query": "Chakra+Petch",
    "stack": "'Chakra Petch', 'Brush Script MT', 'Segoe Script', 'Monotype Corsiva', cursive",
    "weight": "600",
    "style": "italic",
    "spacing": "-0.8px",
    "transform": "uppercase"
  },
  {
    "id": 243,
    "name": "Micro 5",
    "query": "Micro+5",
    "stack": "'Micro 5', 'Consolas', 'Cascadia Code', 'Courier New', monospace",
    "weight": "700",
    "style": "normal",
    "spacing": "0px",
    "transform": "lowercase"
  },
  {
    "id": 244,
    "name": "Jacquard 12",
    "query": "Jacquard+12",
    "stack": "'Jacquard 12', 'Georgia', 'Palatino Linotype', 'Book Antiqua', serif",
    "weight": "800",
    "style": "italic",
    "spacing": "0.5px",
    "transform": "capitalize"
  },
  {
    "id": 245,
    "name": "Pacifico",
    "query": "Pacifico",
    "stack": "'Pacifico', 'Trebuchet MS', 'Arial Black', 'Franklin Gothic Medium', sans-serif",
    "weight": "900",
    "style": "normal",
    "spacing": "1.2px",
    "transform": "none"
  },
  {
    "id": 246,
    "name": "Caveat",
    "query": "Caveat",
    "stack": "'Caveat', 'Copperplate', 'Papyrus', 'Impact', fantasy",
    "weight": "300",
    "style": "italic",
    "spacing": "2px",
    "transform": "uppercase"
  },
  {
    "id": 247,
    "name": "Permanent Marker",
    "query": "Permanent+Marker",
    "stack": "'Permanent Marker', 'Lucida Console', 'Lucida Sans Unicode', monospace",
    "weight": "400",
    "style": "normal",
    "spacing": "3px",
    "transform": "lowercase"
  },
  {
    "id": 248,
    "name": "Dancing Script",
    "query": "Dancing+Script",
    "stack": "'Dancing Script', 'Gabriola', 'Segoe Print', cursive",
    "weight": "500",
    "style": "italic",
    "spacing": "4px",
    "transform": "capitalize"
  },
  {
    "id": 249,
    "name": "Sacramento",
    "query": "Sacramento",
    "stack": "'Sacramento', 'Bahnschrift', 'Franklin Gothic Heavy', sans-serif",
    "weight": "600",
    "style": "normal",
    "spacing": "-1.5px",
    "transform": "none"
  },
  {
    "id": 250,
    "name": "Satisfy",
    "query": "Satisfy",
    "stack": "'Satisfy', 'Ebrima', 'Segoe UI Semibold', sans-serif",
    "weight": "700",
    "style": "italic",
    "spacing": "-0.8px",
    "transform": "uppercase"
  },
  {
    "id": 251,
    "name": "Shadows Into Light",
    "query": "Shadows+Into+Light",
    "stack": "'Shadows Into Light', 'Sitka Text', 'Cambria', serif",
    "weight": "800",
    "style": "normal",
    "spacing": "0px",
    "transform": "lowercase"
  },
  {
    "id": 252,
    "name": "Amatic SC",
    "query": "Amatic+SC",
    "stack": "'Amatic SC', 'Ink Free', 'Comic Sans MS', cursive",
    "weight": "900",
    "style": "italic",
    "spacing": "0.5px",
    "transform": "capitalize"
  },
  {
    "id": 253,
    "name": "Great Vibes",
    "query": "Great+Vibes",
    "stack": "'Great Vibes', 'Corbel', 'Candara', sans-serif",
    "weight": "300",
    "style": "normal",
    "spacing": "1.2px",
    "transform": "none"
  },
  {
    "id": 254,
    "name": "Indie Flower",
    "query": "Indie+Flower",
    "stack": "'Indie Flower', 'Constantia', 'Baskerville', serif",
    "weight": "400",
    "style": "italic",
    "spacing": "2px",
    "transform": "uppercase"
  },
  {
    "id": 255,
    "name": "Kaushan Script",
    "query": "Kaushan+Script",
    "stack": "'Kaushan Script', 'Verdana', 'Tahoma', sans-serif",
    "weight": "500",
    "style": "normal",
    "spacing": "3px",
    "transform": "lowercase"
  },
  {
    "id": 256,
    "name": "Marck Script",
    "query": "Marck+Script",
    "stack": "'Marck Script', 'Rockwell', 'Courier New', serif",
    "weight": "600",
    "style": "italic",
    "spacing": "4px",
    "transform": "capitalize"
  },
  {
    "id": 257,
    "name": "Courgette",
    "query": "Courgette",
    "stack": "'Courgette', 'Marlett', 'Impact', fantasy",
    "weight": "700",
    "style": "normal",
    "spacing": "-1.5px",
    "transform": "none"
  },
  {
    "id": 258,
    "name": "Alex Brush",
    "query": "Alex+Brush",
    "stack": "'Alex Brush', 'MS Gothic', 'MingLiU-ExtB', monospace",
    "weight": "800",
    "style": "italic",
    "spacing": "-0.8px",
    "transform": "uppercase"
  },
  {
    "id": 259,
    "name": "Cookie",
    "query": "Cookie",
    "stack": "'Cookie', 'MV Boli', 'Comic Sans MS', cursive",
    "weight": "900",
    "style": "normal",
    "spacing": "0px",
    "transform": "lowercase"
  },
  {
    "id": 260,
    "name": "Yellowtail",
    "query": "Yellowtail",
    "stack": "'Yellowtail', 'Sylfaen', 'Times New Roman', serif",
    "weight": "300",
    "style": "italic",
    "spacing": "0.5px",
    "transform": "capitalize"
  },
  {
    "id": 261,
    "name": "Allura",
    "query": "Allura",
    "stack": "'Allura', 'Jokerman', 'Chiller', 'Impact', fantasy",
    "weight": "400",
    "style": "normal",
    "spacing": "1.2px",
    "transform": "none"
  },
  {
    "id": 262,
    "name": "Parisienne",
    "query": "Parisienne",
    "stack": "'Parisienne', 'Brush Script MT', 'Segoe Script', 'Monotype Corsiva', cursive",
    "weight": "500",
    "style": "italic",
    "spacing": "2px",
    "transform": "uppercase"
  },
  {
    "id": 263,
    "name": "Homemade Apple",
    "query": "Homemade+Apple",
    "stack": "'Homemade Apple', 'Consolas', 'Cascadia Code', 'Courier New', monospace",
    "weight": "600",
    "style": "normal",
    "spacing": "3px",
    "transform": "lowercase"
  },
  {
    "id": 264,
    "name": "Rock Salt",
    "query": "Rock+Salt",
    "stack": "'Rock Salt', 'Georgia', 'Palatino Linotype', 'Book Antiqua', serif",
    "weight": "700",
    "style": "italic",
    "spacing": "4px",
    "transform": "capitalize"
  },
  {
    "id": 265,
    "name": "Covered By Your Grace",
    "query": "Covered+By+Your+Grace",
    "stack": "'Covered By Your Grace', 'Trebuchet MS', 'Arial Black', 'Franklin Gothic Medium', sans-serif",
    "weight": "800",
    "style": "normal",
    "spacing": "-1.5px",
    "transform": "none"
  },
  {
    "id": 266,
    "name": "Reenie Beanie",
    "query": "Reenie+Beanie",
    "stack": "'Reenie Beanie', 'Copperplate', 'Papyrus', 'Impact', fantasy",
    "weight": "900",
    "style": "italic",
    "spacing": "-0.8px",
    "transform": "uppercase"
  },
  {
    "id": 267,
    "name": "Nothing You Could Do",
    "query": "Nothing+You+Could+Do",
    "stack": "'Nothing You Could Do', 'Lucida Console', 'Lucida Sans Unicode', monospace",
    "weight": "300",
    "style": "normal",
    "spacing": "0px",
    "transform": "lowercase"
  },
  {
    "id": 268,
    "name": "Zeyada",
    "query": "Zeyada",
    "stack": "'Zeyada', 'Gabriola', 'Segoe Print', cursive",
    "weight": "400",
    "style": "italic",
    "spacing": "0.5px",
    "transform": "capitalize"
  },
  {
    "id": 269,
    "name": "Loved by the King",
    "query": "Loved+by+the+King",
    "stack": "'Loved by the King', 'Bahnschrift', 'Franklin Gothic Heavy', sans-serif",
    "weight": "500",
    "style": "normal",
    "spacing": "1.2px",
    "transform": "none"
  },
  {
    "id": 270,
    "name": "La Belle Aurore",
    "query": "La+Belle+Aurore",
    "stack": "'La Belle Aurore', 'Ebrima', 'Segoe UI Semibold', sans-serif",
    "weight": "600",
    "style": "italic",
    "spacing": "2px",
    "transform": "uppercase"
  },
  {
    "id": 271,
    "name": "Give You Glory",
    "query": "Give+You+Glory",
    "stack": "'Give You Glory', 'Sitka Text', 'Cambria', serif",
    "weight": "700",
    "style": "normal",
    "spacing": "3px",
    "transform": "lowercase"
  },
  {
    "id": 272,
    "name": "Waiting for the Sunrise",
    "query": "Waiting+for+the+Sunrise",
    "stack": "'Waiting for the Sunrise', 'Ink Free', 'Comic Sans MS', cursive",
    "weight": "800",
    "style": "italic",
    "spacing": "4px",
    "transform": "capitalize"
  },
  {
    "id": 273,
    "name": "Over the Rainbow",
    "query": "Over+the+Rainbow",
    "stack": "'Over the Rainbow', 'Corbel', 'Candara', sans-serif",
    "weight": "900",
    "style": "normal",
    "spacing": "-1.5px",
    "transform": "none"
  },
  {
    "id": 274,
    "name": "The Girl Next Door",
    "query": "The+Girl+Next+Door",
    "stack": "'The Girl Next Door', 'Constantia', 'Baskerville', serif",
    "weight": "300",
    "style": "italic",
    "spacing": "-0.8px",
    "transform": "uppercase"
  },
  {
    "id": 275,
    "name": "Just Another Hand",
    "query": "Just+Another+Hand",
    "stack": "'Just Another Hand', 'Verdana', 'Tahoma', sans-serif",
    "weight": "400",
    "style": "normal",
    "spacing": "0px",
    "transform": "lowercase"
  },
  {
    "id": 276,
    "name": "Kristi",
    "query": "Kristi",
    "stack": "'Kristi', 'Rockwell', 'Courier New', serif",
    "weight": "500",
    "style": "italic",
    "spacing": "0.5px",
    "transform": "capitalize"
  },
  {
    "id": 277,
    "name": "Herr Von Muellerhoff",
    "query": "Herr+Von+Muellerhoff",
    "stack": "'Herr Von Muellerhoff', 'Marlett', 'Impact', fantasy",
    "weight": "600",
    "style": "normal",
    "spacing": "1.2px",
    "transform": "none"
  },
  {
    "id": 278,
    "name": "Aguafina Script",
    "query": "Aguafina+Script",
    "stack": "'Aguafina Script', 'MS Gothic', 'MingLiU-ExtB', monospace",
    "weight": "700",
    "style": "italic",
    "spacing": "2px",
    "transform": "uppercase"
  },
  {
    "id": 279,
    "name": "Rouge Script",
    "query": "Rouge+Script",
    "stack": "'Rouge Script', 'MV Boli', 'Comic Sans MS', cursive",
    "weight": "800",
    "style": "normal",
    "spacing": "3px",
    "transform": "lowercase"
  },
  {
    "id": 280,
    "name": "Mr De Haviland",
    "query": "Mr+De+Haviland",
    "stack": "'Mr De Haviland', 'Sylfaen', 'Times New Roman', serif",
    "weight": "900",
    "style": "italic",
    "spacing": "4px",
    "transform": "capitalize"
  },
  {
    "id": 281,
    "name": "Monsieur La Doulaise",
    "query": "Monsieur+La+Doulaise",
    "stack": "'Monsieur La Doulaise', 'Jokerman', 'Chiller', 'Impact', fantasy",
    "weight": "300",
    "style": "normal",
    "spacing": "-1.5px",
    "transform": "none"
  },
  {
    "id": 282,
    "name": "Stalemate",
    "query": "Stalemate",
    "stack": "'Stalemate', 'Brush Script MT', 'Segoe Script', 'Monotype Corsiva', cursive",
    "weight": "400",
    "style": "italic",
    "spacing": "-0.8px",
    "transform": "uppercase"
  },
  {
    "id": 283,
    "name": "Jim Nightshade",
    "query": "Jim+Nightshade",
    "stack": "'Jim Nightshade', 'Consolas', 'Cascadia Code', 'Courier New', monospace",
    "weight": "500",
    "style": "normal",
    "spacing": "0px",
    "transform": "lowercase"
  },
  {
    "id": 284,
    "name": "Felipa",
    "query": "Felipa",
    "stack": "'Felipa', 'Georgia', 'Palatino Linotype', 'Book Antiqua', serif",
    "weight": "600",
    "style": "italic",
    "spacing": "0.5px",
    "transform": "capitalize"
  },
  {
    "id": 285,
    "name": "Orbitron",
    "query": "Orbitron",
    "stack": "'Orbitron', 'Trebuchet MS', 'Arial Black', 'Franklin Gothic Medium', sans-serif",
    "weight": "700",
    "style": "normal",
    "spacing": "1.2px",
    "transform": "none"
  },
  {
    "id": 286,
    "name": "Audiowide",
    "query": "Audiowide",
    "stack": "'Audiowide', 'Copperplate', 'Papyrus', 'Impact', fantasy",
    "weight": "800",
    "style": "italic",
    "spacing": "2px",
    "transform": "uppercase"
  },
  {
    "id": 287,
    "name": "Electrolize",
    "query": "Electrolize",
    "stack": "'Electrolize', 'Lucida Console', 'Lucida Sans Unicode', monospace",
    "weight": "900",
    "style": "normal",
    "spacing": "3px",
    "transform": "lowercase"
  },
  {
    "id": 288,
    "name": "Michroma",
    "query": "Michroma",
    "stack": "'Michroma', 'Gabriola', 'Segoe Print', cursive",
    "weight": "300",
    "style": "italic",
    "spacing": "4px",
    "transform": "capitalize"
  },
  {
    "id": 289,
    "name": "Syncopate",
    "query": "Syncopate",
    "stack": "'Syncopate', 'Bahnschrift', 'Franklin Gothic Heavy', sans-serif",
    "weight": "400",
    "style": "normal",
    "spacing": "-1.5px",
    "transform": "none"
  },
  {
    "id": 290,
    "name": "Exo 2",
    "query": "Exo+2",
    "stack": "'Exo 2', 'Ebrima', 'Segoe UI Semibold', sans-serif",
    "weight": "500",
    "style": "italic",
    "spacing": "-0.8px",
    "transform": "uppercase"
  },
  {
    "id": 291,
    "name": "Teko",
    "query": "Teko",
    "stack": "'Teko', 'Sitka Text', 'Cambria', serif",
    "weight": "600",
    "style": "normal",
    "spacing": "0px",
    "transform": "lowercase"
  },
  {
    "id": 292,
    "name": "Rajdhani",
    "query": "Rajdhani",
    "stack": "'Rajdhani', 'Ink Free', 'Comic Sans MS', cursive",
    "weight": "700",
    "style": "italic",
    "spacing": "0.5px",
    "transform": "capitalize"
  },
  {
    "id": 293,
    "name": "Share Tech",
    "query": "Share+Tech",
    "stack": "'Share Tech', 'Corbel', 'Candara', sans-serif",
    "weight": "800",
    "style": "normal",
    "spacing": "1.2px",
    "transform": "none"
  },
  {
    "id": 294,
    "name": "Saira Stencil One",
    "query": "Saira+Stencil+One",
    "stack": "'Saira Stencil One', 'Constantia', 'Baskerville', serif",
    "weight": "900",
    "style": "italic",
    "spacing": "2px",
    "transform": "uppercase"
  },
  {
    "id": 295,
    "name": "Staatliches",
    "query": "Staatliches",
    "stack": "'Staatliches', 'Verdana', 'Tahoma', sans-serif",
    "weight": "300",
    "style": "normal",
    "spacing": "3px",
    "transform": "lowercase"
  },
  {
    "id": 296,
    "name": "Allerta Stencil",
    "query": "Allerta+Stencil",
    "stack": "'Allerta Stencil', 'Rockwell', 'Courier New', serif",
    "weight": "400",
    "style": "italic",
    "spacing": "4px",
    "transform": "capitalize"
  },
  {
    "id": 297,
    "name": "Black Ops One",
    "query": "Black+Ops+One",
    "stack": "'Black Ops One', 'Marlett', 'Impact', fantasy",
    "weight": "500",
    "style": "normal",
    "spacing": "-1.5px",
    "transform": "none"
  },
  {
    "id": 298,
    "name": "Quantico",
    "query": "Quantico",
    "stack": "'Quantico', 'MS Gothic', 'MingLiU-ExtB', monospace",
    "weight": "600",
    "style": "italic",
    "spacing": "-0.8px",
    "transform": "uppercase"
  },
  {
    "id": 299,
    "name": "Bruno Ace SC",
    "query": "Bruno+Ace+SC",
    "stack": "'Bruno Ace SC', 'MV Boli', 'Comic Sans MS', cursive",
    "weight": "700",
    "style": "normal",
    "spacing": "0px",
    "transform": "lowercase"
  },
  {
    "id": 300,
    "name": "Blaka",
    "query": "Blaka",
    "stack": "'Blaka', 'Sylfaen', 'Times New Roman', serif",
    "weight": "800",
    "style": "italic",
    "spacing": "0.5px",
    "transform": "capitalize"
  },
  {
    "id": 301,
    "name": "Blaka Hollow",
    "query": "Blaka+Hollow",
    "stack": "'Blaka Hollow', 'Jokerman', 'Chiller', 'Impact', fantasy",
    "weight": "900",
    "style": "normal",
    "spacing": "1.2px",
    "transform": "none"
  },
  {
    "id": 302,
    "name": "Zen Dots",
    "query": "Zen+Dots",
    "stack": "'Zen Dots', 'Brush Script MT', 'Segoe Script', 'Monotype Corsiva', cursive",
    "weight": "300",
    "style": "italic",
    "spacing": "2px",
    "transform": "uppercase"
  },
  {
    "id": 303,
    "name": "Turret Road",
    "query": "Turret+Road",
    "stack": "'Turret Road', 'Consolas', 'Cascadia Code', 'Courier New', monospace",
    "weight": "400",
    "style": "normal",
    "spacing": "3px",
    "transform": "lowercase"
  },
  {
    "id": 304,
    "name": "Oxanium",
    "query": "Oxanium",
    "stack": "'Oxanium', 'Georgia', 'Palatino Linotype', 'Book Antiqua', serif",
    "weight": "500",
    "style": "italic",
    "spacing": "4px",
    "transform": "capitalize"
  },
  {
    "id": 305,
    "name": "Monda",
    "query": "Monda",
    "stack": "'Monda', 'Trebuchet MS', 'Arial Black', 'Franklin Gothic Medium', sans-serif",
    "weight": "600",
    "style": "normal",
    "spacing": "-1.5px",
    "transform": "none"
  },
  {
    "id": 306,
    "name": "UnifrakturMaguntia",
    "query": "UnifrakturMaguntia",
    "stack": "'UnifrakturMaguntia', 'Copperplate', 'Papyrus', 'Impact', fantasy",
    "weight": "700",
    "style": "italic",
    "spacing": "-0.8px",
    "transform": "uppercase"
  },
  {
    "id": 307,
    "name": "UnifrakturCook",
    "query": "UnifrakturCook",
    "stack": "'UnifrakturCook', 'Lucida Console', 'Lucida Sans Unicode', monospace",
    "weight": "800",
    "style": "normal",
    "spacing": "0px",
    "transform": "lowercase"
  },
  {
    "id": 308,
    "name": "Pirata One",
    "query": "Pirata+One",
    "stack": "'Pirata One', 'Gabriola', 'Segoe Print', cursive",
    "weight": "900",
    "style": "italic",
    "spacing": "0.5px",
    "transform": "capitalize"
  },
  {
    "id": 309,
    "name": "MedievalSharp",
    "query": "MedievalSharp",
    "stack": "'MedievalSharp', 'Bahnschrift', 'Franklin Gothic Heavy', sans-serif",
    "weight": "300",
    "style": "normal",
    "spacing": "1.2px",
    "transform": "none"
  },
  {
    "id": 310,
    "name": "Eczar",
    "query": "Eczar",
    "stack": "'Eczar', 'Ebrima', 'Segoe UI Semibold', sans-serif",
    "weight": "400",
    "style": "italic",
    "spacing": "2px",
    "transform": "uppercase"
  },
  {
    "id": 311,
    "name": "Almendra Display",
    "query": "Almendra+Display",
    "stack": "'Almendra Display', 'Sitka Text', 'Cambria', serif",
    "weight": "500",
    "style": "normal",
    "spacing": "3px",
    "transform": "lowercase"
  },
  {
    "id": 312,
    "name": "Diplomata SC",
    "query": "Diplomata+SC",
    "stack": "'Diplomata SC', 'Ink Free', 'Comic Sans MS', cursive",
    "weight": "600",
    "style": "italic",
    "spacing": "4px",
    "transform": "capitalize"
  },
  {
    "id": 313,
    "name": "Diplomata",
    "query": "Diplomata",
    "stack": "'Diplomata', 'Corbel', 'Candara', sans-serif",
    "weight": "700",
    "style": "normal",
    "spacing": "-1.5px",
    "transform": "none"
  },
  {
    "id": 314,
    "name": "Fascinate",
    "query": "Fascinate",
    "stack": "'Fascinate', 'Constantia', 'Baskerville', serif",
    "weight": "800",
    "style": "italic",
    "spacing": "-0.8px",
    "transform": "uppercase"
  },
  {
    "id": 315,
    "name": "Fascinate Inline",
    "query": "Fascinate+Inline",
    "stack": "'Fascinate Inline', 'Verdana', 'Tahoma', sans-serif",
    "weight": "900",
    "style": "normal",
    "spacing": "0px",
    "transform": "lowercase"
  },
  {
    "id": 316,
    "name": "Geostar",
    "query": "Geostar",
    "stack": "'Geostar', 'Rockwell', 'Courier New', serif",
    "weight": "300",
    "style": "italic",
    "spacing": "0.5px",
    "transform": "capitalize"
  },
  {
    "id": 317,
    "name": "Geostar Fill",
    "query": "Geostar+Fill",
    "stack": "'Geostar Fill', 'Marlett', 'Impact', fantasy",
    "weight": "400",
    "style": "normal",
    "spacing": "1.2px",
    "transform": "none"
  },
  {
    "id": 318,
    "name": "Vast Shadow",
    "query": "Vast+Shadow",
    "stack": "'Vast Shadow', 'MS Gothic', 'MingLiU-ExtB', monospace",
    "weight": "500",
    "style": "italic",
    "spacing": "2px",
    "transform": "uppercase"
  },
  {
    "id": 319,
    "name": "Monoton",
    "query": "Monoton",
    "stack": "'Monoton', 'MV Boli', 'Comic Sans MS', cursive",
    "weight": "600",
    "style": "normal",
    "spacing": "3px",
    "transform": "lowercase"
  },
  {
    "id": 320,
    "name": "Bungee",
    "query": "Bungee",
    "stack": "'Bungee', 'Sylfaen', 'Times New Roman', serif",
    "weight": "700",
    "style": "italic",
    "spacing": "4px",
    "transform": "capitalize"
  },
  {
    "id": 321,
    "name": "Bungee Shade",
    "query": "Bungee+Shade",
    "stack": "'Bungee Shade', 'Jokerman', 'Chiller', 'Impact', fantasy",
    "weight": "800",
    "style": "normal",
    "spacing": "-1.5px",
    "transform": "none"
  },
  {
    "id": 322,
    "name": "Bungee Inline",
    "query": "Bungee+Inline",
    "stack": "'Bungee Inline', 'Brush Script MT', 'Segoe Script', 'Monotype Corsiva', cursive",
    "weight": "900",
    "style": "italic",
    "spacing": "-0.8px",
    "transform": "uppercase"
  },
  {
    "id": 323,
    "name": "Bungee Outline",
    "query": "Bungee+Outline",
    "stack": "'Bungee Outline', 'Consolas', 'Cascadia Code', 'Courier New', monospace",
    "weight": "300",
    "style": "normal",
    "spacing": "0px",
    "transform": "lowercase"
  },
  {
    "id": 324,
    "name": "Bungee Hairline",
    "query": "Bungee+Hairline",
    "stack": "'Bungee Hairline', 'Georgia', 'Palatino Linotype', 'Book Antiqua', serif",
    "weight": "400",
    "style": "italic",
    "spacing": "0.5px",
    "transform": "capitalize"
  },
  {
    "id": 325,
    "name": "Faster One",
    "query": "Faster+One",
    "stack": "'Faster One', 'Trebuchet MS', 'Arial Black', 'Franklin Gothic Medium', sans-serif",
    "weight": "500",
    "style": "normal",
    "spacing": "1.2px",
    "transform": "none"
  },
  {
    "id": 326,
    "name": "Megrim",
    "query": "Megrim",
    "stack": "'Megrim', 'Copperplate', 'Papyrus', 'Impact', fantasy",
    "weight": "600",
    "style": "italic",
    "spacing": "2px",
    "transform": "uppercase"
  },
  {
    "id": 327,
    "name": "Plaster",
    "query": "Plaster",
    "stack": "'Plaster', 'Lucida Console', 'Lucida Sans Unicode', monospace",
    "weight": "700",
    "style": "normal",
    "spacing": "3px",
    "transform": "lowercase"
  },
  {
    "id": 328,
    "name": "Londrina Outline",
    "query": "Londrina+Outline",
    "stack": "'Londrina Outline', 'Gabriola', 'Segoe Print', cursive",
    "weight": "800",
    "style": "italic",
    "spacing": "4px",
    "transform": "capitalize"
  },
  {
    "id": 329,
    "name": "Londrina Shadow",
    "query": "Londrina+Shadow",
    "stack": "'Londrina Shadow', 'Bahnschrift', 'Franklin Gothic Heavy', sans-serif",
    "weight": "900",
    "style": "normal",
    "spacing": "-1.5px",
    "transform": "none"
  },
  {
    "id": 330,
    "name": "Londrina Sketch",
    "query": "Londrina+Sketch",
    "stack": "'Londrina Sketch', 'Ebrima', 'Segoe UI Semibold', sans-serif",
    "weight": "300",
    "style": "italic",
    "spacing": "-0.8px",
    "transform": "uppercase"
  },
  {
    "id": 331,
    "name": "Londrina Solid",
    "query": "Londrina+Solid",
    "stack": "'Londrina Solid', 'Sitka Text', 'Cambria', serif",
    "weight": "400",
    "style": "normal",
    "spacing": "0px",
    "transform": "lowercase"
  },
  {
    "id": 332,
    "name": "Codystar",
    "query": "Codystar",
    "stack": "'Codystar', 'Ink Free', 'Comic Sans MS', cursive",
    "weight": "500",
    "style": "italic",
    "spacing": "0.5px",
    "transform": "capitalize"
  },
  {
    "id": 333,
    "name": "Nixie One",
    "query": "Nixie+One",
    "stack": "'Nixie One', 'Corbel', 'Candara', sans-serif",
    "weight": "600",
    "style": "normal",
    "spacing": "1.2px",
    "transform": "none"
  },
  {
    "id": 334,
    "name": "Erica One",
    "query": "Erica+One",
    "stack": "'Erica One', 'Constantia', 'Baskerville', serif",
    "weight": "700",
    "style": "italic",
    "spacing": "2px",
    "transform": "uppercase"
  },
  {
    "id": 335,
    "name": "Kenia",
    "query": "Kenia",
    "stack": "'Kenia', 'Verdana', 'Tahoma', sans-serif",
    "weight": "800",
    "style": "normal",
    "spacing": "3px",
    "transform": "lowercase"
  },
  {
    "id": 336,
    "name": "Warnes",
    "query": "Warnes",
    "stack": "'Warnes', 'Rockwell', 'Courier New', serif",
    "weight": "900",
    "style": "italic",
    "spacing": "4px",
    "transform": "capitalize"
  },
  {
    "id": 337,
    "name": "Bangers",
    "query": "Bangers",
    "stack": "'Bangers', 'Marlett', 'Impact', fantasy",
    "weight": "300",
    "style": "normal",
    "spacing": "-1.5px",
    "transform": "none"
  },
  {
    "id": 338,
    "name": "Luckiest Guy",
    "query": "Luckiest+Guy",
    "stack": "'Luckiest Guy', 'MS Gothic', 'MingLiU-ExtB', monospace",
    "weight": "400",
    "style": "italic",
    "spacing": "-0.8px",
    "transform": "uppercase"
  },
  {
    "id": 339,
    "name": "Fredoka",
    "query": "Fredoka",
    "stack": "'Fredoka', 'MV Boli', 'Comic Sans MS', cursive",
    "weight": "500",
    "style": "normal",
    "spacing": "0px",
    "transform": "lowercase"
  },
  {
    "id": 340,
    "name": "Sniglet",
    "query": "Sniglet",
    "stack": "'Sniglet', 'Sylfaen', 'Times New Roman', serif",
    "weight": "600",
    "style": "italic",
    "spacing": "0.5px",
    "transform": "capitalize"
  },
  {
    "id": 341,
    "name": "Chewy",
    "query": "Chewy",
    "stack": "'Chewy', 'Jokerman', 'Chiller', 'Impact', fantasy",
    "weight": "700",
    "style": "normal",
    "spacing": "1.2px",
    "transform": "none"
  },
  {
    "id": 342,
    "name": "Chicle",
    "query": "Chicle",
    "stack": "'Chicle', 'Brush Script MT', 'Segoe Script', 'Monotype Corsiva', cursive",
    "weight": "800",
    "style": "italic",
    "spacing": "2px",
    "transform": "uppercase"
  },
  {
    "id": 343,
    "name": "Boogaloo",
    "query": "Boogaloo",
    "stack": "'Boogaloo', 'Consolas', 'Cascadia Code', 'Courier New', monospace",
    "weight": "900",
    "style": "normal",
    "spacing": "3px",
    "transform": "lowercase"
  },
  {
    "id": 344,
    "name": "Rammetto One",
    "query": "Rammetto+One",
    "stack": "'Rammetto One', 'Georgia', 'Palatino Linotype', 'Book Antiqua', serif",
    "weight": "300",
    "style": "italic",
    "spacing": "4px",
    "transform": "capitalize"
  },
  {
    "id": 345,
    "name": "Slackey",
    "query": "Slackey",
    "stack": "'Slackey', 'Trebuchet MS', 'Arial Black', 'Franklin Gothic Medium', sans-serif",
    "weight": "400",
    "style": "normal",
    "spacing": "-1.5px",
    "transform": "none"
  },
  {
    "id": 346,
    "name": "Spicy Rice",
    "query": "Spicy+Rice",
    "stack": "'Spicy Rice', 'Copperplate', 'Papyrus', 'Impact', fantasy",
    "weight": "500",
    "style": "italic",
    "spacing": "-0.8px",
    "transform": "uppercase"
  },
  {
    "id": 347,
    "name": "Carter One",
    "query": "Carter+One",
    "stack": "'Carter One', 'Lucida Console', 'Lucida Sans Unicode', monospace",
    "weight": "600",
    "style": "normal",
    "spacing": "0px",
    "transform": "lowercase"
  },
  {
    "id": 348,
    "name": "Comic Neue",
    "query": "Comic+Neue",
    "stack": "'Comic Neue', 'Gabriola', 'Segoe Print', cursive",
    "weight": "700",
    "style": "italic",
    "spacing": "0.5px",
    "transform": "capitalize"
  },
  {
    "id": 349,
    "name": "Shanti",
    "query": "Shanti",
    "stack": "'Shanti', 'Bahnschrift', 'Franklin Gothic Heavy', sans-serif",
    "weight": "800",
    "style": "normal",
    "spacing": "1.2px",
    "transform": "none"
  },
  {
    "id": 350,
    "name": "Single Day",
    "query": "Single+Day",
    "stack": "'Single Day', 'Ebrima', 'Segoe UI Semibold', sans-serif",
    "weight": "900",
    "style": "italic",
    "spacing": "2px",
    "transform": "uppercase"
  },
  {
    "id": 351,
    "name": "Gaegu",
    "query": "Gaegu",
    "stack": "'Gaegu', 'Sitka Text', 'Cambria', serif",
    "weight": "300",
    "style": "normal",
    "spacing": "3px",
    "transform": "lowercase"
  },
  {
    "id": 352,
    "name": "Cute Font",
    "query": "Cute+Font",
    "stack": "'Cute Font', 'Ink Free', 'Comic Sans MS', cursive",
    "weight": "400",
    "style": "italic",
    "spacing": "4px",
    "transform": "capitalize"
  },
  {
    "id": 353,
    "name": "Hi Melody",
    "query": "Hi+Melody",
    "stack": "'Hi Melody', 'Corbel', 'Candara', sans-serif",
    "weight": "500",
    "style": "normal",
    "spacing": "-1.5px",
    "transform": "none"
  },
  {
    "id": 354,
    "name": "Kirang Haerang",
    "query": "Kirang+Haerang",
    "stack": "'Kirang Haerang', 'Constantia', 'Baskerville', serif",
    "weight": "600",
    "style": "italic",
    "spacing": "-0.8px",
    "transform": "uppercase"
  },
  {
    "id": 355,
    "name": "East Sea Dokdo",
    "query": "East+Sea+Dokdo",
    "stack": "'East Sea Dokdo', 'Verdana', 'Tahoma', sans-serif",
    "weight": "700",
    "style": "normal",
    "spacing": "0px",
    "transform": "lowercase"
  },
  {
    "id": 356,
    "name": "Poor Story",
    "query": "Poor+Story",
    "stack": "'Poor Story', 'Rockwell', 'Courier New', serif",
    "weight": "800",
    "style": "italic",
    "spacing": "0.5px",
    "transform": "capitalize"
  },
  {
    "id": 357,
    "name": "Gamja Flower",
    "query": "Gamja+Flower",
    "stack": "'Gamja Flower', 'Marlett', 'Impact', fantasy",
    "weight": "900",
    "style": "normal",
    "spacing": "1.2px",
    "transform": "none"
  },
  {
    "id": 358,
    "name": "Abril Fatface",
    "query": "Abril+Fatface",
    "stack": "'Abril Fatface', 'MS Gothic', 'MingLiU-ExtB', monospace",
    "weight": "300",
    "style": "italic",
    "spacing": "2px",
    "transform": "uppercase"
  },
  {
    "id": 359,
    "name": "Alfa Slab One",
    "query": "Alfa+Slab+One",
    "stack": "'Alfa Slab One', 'MV Boli', 'Comic Sans MS', cursive",
    "weight": "400",
    "style": "normal",
    "spacing": "3px",
    "transform": "lowercase"
  },
  {
    "id": 360,
    "name": "Ultra",
    "query": "Ultra",
    "stack": "'Ultra', 'Sylfaen', 'Times New Roman', serif",
    "weight": "500",
    "style": "italic",
    "spacing": "4px",
    "transform": "capitalize"
  },
  {
    "id": 361,
    "name": "Paytone One",
    "query": "Paytone+One",
    "stack": "'Paytone One', 'Jokerman', 'Chiller', 'Impact', fantasy",
    "weight": "600",
    "style": "normal",
    "spacing": "-1.5px",
    "transform": "none"
  },
  {
    "id": 362,
    "name": "Righteous",
    "query": "Righteous",
    "stack": "'Righteous', 'Brush Script MT', 'Segoe Script', 'Monotype Corsiva', cursive",
    "weight": "700",
    "style": "italic",
    "spacing": "-0.8px",
    "transform": "uppercase"
  },
  {
    "id": 363,
    "name": "Sigmar",
    "query": "Sigmar",
    "stack": "'Sigmar', 'Consolas', 'Cascadia Code', 'Courier New', monospace",
    "weight": "800",
    "style": "normal",
    "spacing": "0px",
    "transform": "lowercase"
  },
  {
    "id": 364,
    "name": "Passion One",
    "query": "Passion+One",
    "stack": "'Passion One', 'Georgia', 'Palatino Linotype', 'Book Antiqua', serif",
    "weight": "900",
    "style": "italic",
    "spacing": "0.5px",
    "transform": "capitalize"
  },
  {
    "id": 365,
    "name": "Squada One",
    "query": "Squada+One",
    "stack": "'Squada One', 'Trebuchet MS', 'Arial Black', 'Franklin Gothic Medium', sans-serif",
    "weight": "300",
    "style": "normal",
    "spacing": "1.2px",
    "transform": "none"
  },
  {
    "id": 366,
    "name": "Chango",
    "query": "Chango",
    "stack": "'Chango', 'Copperplate', 'Papyrus', 'Impact', fantasy",
    "weight": "400",
    "style": "italic",
    "spacing": "2px",
    "transform": "uppercase"
  },
  {
    "id": 367,
    "name": "Gravitas One",
    "query": "Gravitas+One",
    "stack": "'Gravitas One', 'Lucida Console', 'Lucida Sans Unicode', monospace",
    "weight": "500",
    "style": "normal",
    "spacing": "3px",
    "transform": "lowercase"
  },
  {
    "id": 368,
    "name": "Rozha One",
    "query": "Rozha+One",
    "stack": "'Rozha One', 'Gabriola', 'Segoe Print', cursive",
    "weight": "600",
    "style": "italic",
    "spacing": "4px",
    "transform": "capitalize"
  },
  {
    "id": 369,
    "name": "Rubik One",
    "query": "Rubik+Mono+One",
    "stack": "'Rubik One', 'Bahnschrift', 'Franklin Gothic Heavy', sans-serif",
    "weight": "700",
    "style": "normal",
    "spacing": "-1.5px",
    "transform": "none"
  },
  {
    "id": 370,
    "name": "Stint Ultra Expanded",
    "query": "Stint+Ultra+Expanded",
    "stack": "'Stint Ultra Expanded', 'Ebrima', 'Segoe UI Semibold', sans-serif",
    "weight": "800",
    "style": "italic",
    "spacing": "-0.8px",
    "transform": "uppercase"
  },
  {
    "id": 371,
    "name": "Stint Ultra Condensed",
    "query": "Stint+Ultra+Condensed",
    "stack": "'Stint Ultra Condensed', 'Sitka Text', 'Cambria', serif",
    "weight": "900",
    "style": "normal",
    "spacing": "0px",
    "transform": "lowercase"
  },
  {
    "id": 372,
    "name": "Bowlby One",
    "query": "Bowlby+One",
    "stack": "'Bowlby One', 'Ink Free', 'Comic Sans MS', cursive",
    "weight": "300",
    "style": "italic",
    "spacing": "0.5px",
    "transform": "capitalize"
  },
  {
    "id": 373,
    "name": "Bowlby One SC",
    "query": "Bowlby+One+SC",
    "stack": "'Bowlby One SC', 'Corbel', 'Candara', sans-serif",
    "weight": "400",
    "style": "normal",
    "spacing": "1.2px",
    "transform": "none"
  },
  {
    "id": 374,
    "name": "Vampiro One",
    "query": "Vampiro+One",
    "stack": "'Vampiro One', 'Constantia', 'Baskerville', serif",
    "weight": "500",
    "style": "italic",
    "spacing": "2px",
    "transform": "uppercase"
  },
  {
    "id": 375,
    "name": "Playfair Display",
    "query": "Playfair+Display",
    "stack": "'Playfair Display', 'Verdana', 'Tahoma', sans-serif",
    "weight": "600",
    "style": "normal",
    "spacing": "3px",
    "transform": "lowercase"
  },
  {
    "id": 376,
    "name": "Cinzel Decorative",
    "query": "Cinzel+Decorative",
    "stack": "'Cinzel Decorative', 'Rockwell', 'Courier New', serif",
    "weight": "700",
    "style": "italic",
    "spacing": "4px",
    "transform": "capitalize"
  },
  {
    "id": 377,
    "name": "Bodoni Moda",
    "query": "Bodoni+Moda",
    "stack": "'Bodoni Moda', 'Marlett', 'Impact', fantasy",
    "weight": "800",
    "style": "normal",
    "spacing": "-1.5px",
    "transform": "none"
  },
  {
    "id": 378,
    "name": "Cormorant Garamond",
    "query": "Cormorant+Garamond",
    "stack": "'Cormorant Garamond', 'MS Gothic', 'MingLiU-ExtB', monospace",
    "weight": "900",
    "style": "italic",
    "spacing": "-0.8px",
    "transform": "uppercase"
  },
  {
    "id": 379,
    "name": "Prata",
    "query": "Prata",
    "stack": "'Prata', 'MV Boli', 'Comic Sans MS', cursive",
    "weight": "300",
    "style": "normal",
    "spacing": "0px",
    "transform": "lowercase"
  },
  {
    "id": 380,
    "name": "Syne",
    "query": "Syne",
    "stack": "'Syne', 'Sylfaen', 'Times New Roman', serif",
    "weight": "400",
    "style": "italic",
    "spacing": "0.5px",
    "transform": "capitalize"
  },
  {
    "id": 381,
    "name": "DM Serif Display",
    "query": "DM+Serif+Display",
    "stack": "'DM Serif Display', 'Jokerman', 'Chiller', 'Impact', fantasy",
    "weight": "500",
    "style": "normal",
    "spacing": "1.2px",
    "transform": "none"
  },
  {
    "id": 382,
    "name": "Fraunces",
    "query": "Fraunces",
    "stack": "'Fraunces', 'Brush Script MT', 'Segoe Script', 'Monotype Corsiva', cursive",
    "weight": "600",
    "style": "italic",
    "spacing": "2px",
    "transform": "uppercase"
  },
  {
    "id": 383,
    "name": "Big Shoulders Display",
    "query": "Big+Shoulders+Display",
    "stack": "'Big Shoulders Display', 'Consolas', 'Cascadia Code', 'Courier New', monospace",
    "weight": "700",
    "style": "normal",
    "spacing": "3px",
    "transform": "lowercase"
  },
  {
    "id": 384,
    "name": "Italiana",
    "query": "Italiana",
    "stack": "'Italiana', 'Georgia', 'Palatino Linotype', 'Book Antiqua', serif",
    "weight": "800",
    "style": "italic",
    "spacing": "4px",
    "transform": "capitalize"
  },
  {
    "id": 385,
    "name": "Forum",
    "query": "Forum",
    "stack": "'Forum', 'Trebuchet MS', 'Arial Black', 'Franklin Gothic Medium', sans-serif",
    "weight": "900",
    "style": "normal",
    "spacing": "-1.5px",
    "transform": "none"
  },
  {
    "id": 386,
    "name": "Cinzel",
    "query": "Cinzel",
    "stack": "'Cinzel', 'Copperplate', 'Papyrus', 'Impact', fantasy",
    "weight": "300",
    "style": "italic",
    "spacing": "-0.8px",
    "transform": "uppercase"
  },
  {
    "id": 387,
    "name": "Castoro Titling",
    "query": "Castoro+Titling",
    "stack": "'Castoro Titling', 'Lucida Console', 'Lucida Sans Unicode', monospace",
    "weight": "400",
    "style": "normal",
    "spacing": "0px",
    "transform": "lowercase"
  },
  {
    "id": 388,
    "name": "Bellefair",
    "query": "Bellefair",
    "stack": "'Bellefair', 'Gabriola', 'Segoe Print', cursive",
    "weight": "500",
    "style": "italic",
    "spacing": "0.5px",
    "transform": "capitalize"
  },
  {
    "id": 389,
    "name": "Fira Code",
    "query": "Fira+Code",
    "stack": "'Fira Code', 'Bahnschrift', 'Franklin Gothic Heavy', sans-serif",
    "weight": "600",
    "style": "normal",
    "spacing": "1.2px",
    "transform": "none"
  },
  {
    "id": 390,
    "name": "JetBrains Mono",
    "query": "JetBrains+Mono",
    "stack": "'JetBrains Mono', 'Ebrima', 'Segoe UI Semibold', sans-serif",
    "weight": "700",
    "style": "italic",
    "spacing": "2px",
    "transform": "uppercase"
  },
  {
    "id": 391,
    "name": "Inconsolata",
    "query": "Inconsolata",
    "stack": "'Inconsolata', 'Sitka Text', 'Cambria', serif",
    "weight": "800",
    "style": "normal",
    "spacing": "3px",
    "transform": "lowercase"
  },
  {
    "id": 392,
    "name": "Source Code Pro",
    "query": "Source+Code+Pro",
    "stack": "'Source Code Pro', 'Ink Free', 'Comic Sans MS', cursive",
    "weight": "900",
    "style": "italic",
    "spacing": "4px",
    "transform": "capitalize"
  },
  {
    "id": 393,
    "name": "Space Mono",
    "query": "Space+Mono",
    "stack": "'Space Mono', 'Corbel', 'Candara', sans-serif",
    "weight": "300",
    "style": "normal",
    "spacing": "-1.5px",
    "transform": "none"
  },
  {
    "id": 394,
    "name": "Courier Prime",
    "query": "Courier+Prime",
    "stack": "'Courier Prime', 'Constantia', 'Baskerville', serif",
    "weight": "400",
    "style": "italic",
    "spacing": "-0.8px",
    "transform": "uppercase"
  },
  {
    "id": 395,
    "name": "Share Tech Mono",
    "query": "Share+Tech+Mono",
    "stack": "'Share Tech Mono', 'Verdana', 'Tahoma', sans-serif",
    "weight": "500",
    "style": "normal",
    "spacing": "0px",
    "transform": "lowercase"
  },
  {
    "id": 396,
    "name": "Anonymous Pro",
    "query": "Anonymous+Pro",
    "stack": "'Anonymous Pro', 'Rockwell', 'Courier New', serif",
    "weight": "600",
    "style": "italic",
    "spacing": "0.5px",
    "transform": "capitalize"
  },
  {
    "id": 397,
    "name": "Cutive Mono",
    "query": "Cutive+Mono",
    "stack": "'Cutive Mono', 'Marlett', 'Impact', fantasy",
    "weight": "700",
    "style": "normal",
    "spacing": "1.2px",
    "transform": "none"
  },
  {
    "id": 398,
    "name": "Nova Mono",
    "query": "Nova+Mono",
    "stack": "'Nova Mono', 'MS Gothic', 'MingLiU-ExtB', monospace",
    "weight": "800",
    "style": "italic",
    "spacing": "2px",
    "transform": "uppercase"
  },
  {
    "id": 399,
    "name": "Major Mono Display",
    "query": "Major+Mono+Display",
    "stack": "'Major Mono Display', 'MV Boli', 'Comic Sans MS', cursive",
    "weight": "900",
    "style": "normal",
    "spacing": "3px",
    "transform": "lowercase"
  },
  {
    "id": 400,
    "name": "Syne Mono",
    "query": "Syne+Mono",
    "stack": "'Syne Mono', 'Sylfaen', 'Times New Roman', serif",
    "weight": "300",
    "style": "italic",
    "spacing": "4px",
    "transform": "capitalize"
  }
];

	const COLORS_POOL = [
		"#3D72FF", "#F05350", "#10B981", "#B558F3", "#F59E0B", "#0CB6DD", "#EC4899", "#10B981",
		"#6366F1", "#F97316", "#14B8A6", "#D946EF", "#8B5CF6", "#3B82F6", "#EF4444", "#22C55E",
		"#8B5CF6", "#EAB308", "#06B6D4", "#F43F5E", "#84CC16", "#4F46E5", "#FB923C", "#34D399",
		"#A855F7", "#FACC15", "#0284C7", "#E11D48", "#16A34A", "#4338CA", "#EA580C", "#0D9488"
	];

	let currentFontIdx = -1;
	let currentColorIdx = -1;
	const fetchedFonts = new Set();

	function ensureFontLink(fontObj) {
		if (!fontObj || !fontObj.query) return;
		const safeId = 'fab-gfont-' + fontObj.query.replace(/[^a-zA-Z0-9_-]/g, '');

		// 1. Inject <link rel="stylesheet" crossorigin="anonymous">
		if (!document.getElementById(safeId)) {
			const link = document.createElement('link');
			link.id = safeId;
			link.rel = 'stylesheet';
			link.crossOrigin = 'anonymous';
			link.href = `https://fonts.googleapis.com/css2?family=${fontObj.query}&display=swap`;
			document.head.appendChild(link);
		}

		// 2. Direct CSS fetch & @font-face rule injection for Chromium / WebView2 reliability
		if (!fetchedFonts.has(fontObj.query)) {
			fetchedFonts.add(fontObj.query);
			fetch(`https://fonts.googleapis.com/css2?family=${fontObj.query}&display=swap`)
				.then(res => res.text())
				.then(css => {
					if (css && css.includes('@font-face')) {
						const styleEl = document.createElement('style');
						styleEl.id = safeId + '-css';
						styleEl.textContent = css;
						document.head.appendChild(styleEl);
					}
				})
				.catch(() => {});
		}
	}

	function showFontToast(fontObj, index) {
		let toast = document.getElementById('fab-font-toast-badge');
		if (!toast) {
			toast = document.createElement('div');
			toast.id = 'fab-font-toast-badge';
			toast.style.position = 'fixed';
			toast.style.bottom = '20px';
			toast.style.right = '20px';
			toast.style.background = 'rgba(15, 23, 42, 0.94)';
			toast.style.color = '#38BDF8';
			toast.style.padding = '8px 16px';
			toast.style.borderRadius = '9999px';
			toast.style.fontSize = '12px';
			toast.style.fontWeight = '600';
			toast.style.fontFamily = 'sans-serif';
			toast.style.boxShadow = '0 10px 25px -5px rgba(0, 0, 0, 0.5), 0 0 15px rgba(56, 189, 248, 0.3)';
			toast.style.border = '1px solid rgba(56, 189, 248, 0.4)';
			toast.style.zIndex = '99999';
			toast.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
			toast.style.pointerEvents = 'none';
			toast.style.opacity = '0';
			toast.style.transform = 'translateY(10px)';
			document.body.appendChild(toast);
		}

		toast.innerHTML = `<span style="color:#94A3B8;">Police ${index + 1}/400:</span> <strong style="color:#F43F5E;">${fontObj.name}</strong>`;
		toast.style.opacity = '1';
		toast.style.transform = 'translateY(0)';

		if (window._fabToastTimeout) clearTimeout(window._fabToastTimeout);
		window._fabToastTimeout = setTimeout(() => {
			toast.style.opacity = '0';
			toast.style.transform = 'translateY(10px)';
		}, 2500);
	}

	function applyFontObj(fontObj, index, isInitialRestoration = false) {
		if (!fontObj) return;

		ensureFontLink(fontObj);

		document.documentElement.style.setProperty('--font-custom-active', fontObj.stack);

		const targetElements = document.querySelectorAll('.fab-logo-text-main, .fab-logo-text-sub, .page-title-main, .hero-font-target, .nav-brand-title');

		const applyStyles = (el) => {
			el.style.setProperty('font-family', fontObj.stack, 'important');
			el.style.setProperty('font-weight', fontObj.weight, 'important');
			el.style.setProperty('font-style', fontObj.style, 'important');
			el.style.setProperty('letter-spacing', fontObj.spacing, 'important');
			el.style.setProperty('text-transform', fontObj.transform, 'important');
		};

		if (isInitialRestoration) {
			targetElements.forEach(el => applyStyles(el));
		} else {
			targetElements.forEach(el => {
				el.style.transition = 'opacity 0.15s ease, font-family 0.25s ease, transform 0.25s ease';
				el.style.opacity = '0.3';
				setTimeout(() => {
					applyStyles(el);
					el.style.opacity = '1';
				}, 100);
			});
		}

		if (document.fonts && document.fonts.load) {
			try {
				document.fonts.load(`16px "${fontObj.name}"`).then(() => {
					targetElements.forEach(el => applyStyles(el));
				}).catch(() => {});
			} catch(e) {}
		}

		if (!isInitialRestoration) {
			showFontToast(fontObj, index !== undefined ? index : currentFontIdx);
		}

		try {
			localStorage.setItem('fab_active_font_query', fontObj.query);
			localStorage.setItem('fab_active_font_stack', fontObj.stack);
			localStorage.setItem('fab_active_font_name', fontObj.name);
		} catch(e) {}
	}

	function applyColor(colorStr) {
		if (!colorStr) return;
		const targetElements = document.querySelectorAll('.fab-logo-text-main, .page-title-main');
		targetElements.forEach(el => {
			el.style.setProperty('color', colorStr, 'important');
		});
		try {
			localStorage.setItem('fab_active_color', colorStr);
		} catch(e) {}
	}

	function rotateFont() {
		if (FONTS_POOL.length <= 1) return;
		let randomIdx;
		do {
			randomIdx = Math.floor(Math.random() * FONTS_POOL.length);
		} while (randomIdx === currentFontIdx);
		currentFontIdx = randomIdx;
		const fontObj = FONTS_POOL[randomIdx];
		applyFontObj(fontObj, randomIdx, false);
	}

	function rotateColor() {
		if (COLORS_POOL.length <= 1) return;
		let randomIdx;
		do {
			randomIdx = Math.floor(Math.random() * COLORS_POOL.length);
		} while (randomIdx === currentColorIdx);
		currentColorIdx = randomIdx;
		applyColor(COLORS_POOL[randomIdx]);
	}

	function restoreSavedFontAndColor() {
		let savedQuery = null;
		let savedColor = null;
		try {
			savedQuery = localStorage.getItem('fab_active_font_query');
			savedColor = localStorage.getItem('fab_active_color');
		} catch(e) {}

		// Restore Font only if saved explicitly by user click
		if (savedQuery) {
			const foundIdx = FONTS_POOL.findIndex(f => f.query === savedQuery || f.name === savedQuery);
			if (foundIdx !== -1) {
				currentFontIdx = foundIdx;
				applyFontObj(FONTS_POOL[foundIdx], foundIdx, true);
			}
		}

		// Restore Color only if saved explicitly
		if (savedColor) {
			const foundColorIdx = COLORS_POOL.indexOf(savedColor);
			if (foundColorIdx !== -1) {
				currentColorIdx = foundColorIdx;
				applyColor(savedColor);
			}
		}
	}

	document.addEventListener('DOMContentLoaded', () => {
		// Preconnect Google Fonts
		if (!document.getElementById('fab-gfonts-preconnect-1')) {
			const p1 = document.createElement('link');
			p1.id = 'fab-gfonts-preconnect-1';
			p1.rel = 'preconnect';
			p1.href = 'https://fonts.googleapis.com';
			document.head.appendChild(p1);
		}
		if (!document.getElementById('fab-gfonts-preconnect-2')) {
			const p2 = document.createElement('link');
			p2.id = 'fab-gfonts-preconnect-2';
			p2.rel = 'preconnect';
			p2.href = 'https://fonts.gstatic.com';
			p2.crossOrigin = 'anonymous';
			document.head.appendChild(p2);
		}

		const logoTargets = document.querySelectorAll('.fab-logo-text-main, .fab-logo-text-sub, .nav-brand, .nav-brand-title');
		logoTargets.forEach(target => {
			target.style.cursor = 'pointer';
			target.setAttribute('title', 'Cliquer pour changer la police (400 polices distinctes)');
			target.addEventListener('click', (e) => {
				e.preventDefault();
				rotateFont();
				rotateColor();
			});
		});

		// Restore persistent choice on page load / refresh
		restoreSavedFontAndColor();
	});
})();
