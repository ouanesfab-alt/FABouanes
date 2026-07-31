// dashboard-fonts.js — Font picker and typography customization (200 Fonts & 200 Colors)
(function () {
	const FONTS_POOL = [
   {
      "name": "Creepster",
      "stack": "'Creepster', 'Comic Sans MS', cursive"
   },
   {
      "name": "Eater",
      "stack": "'Eater', 'Impact', fantasy"
   },
   {
      "name": "Nosifer",
      "stack": "'Nosifer', 'Impact', fantasy"
   },
   {
      "name": "Butcherman",
      "stack": "'Butcherman', 'Comic Sans MS', cursive"
   },
   {
      "name": "Freckle Face",
      "stack": "'Freckle Face', 'Comic Sans MS', cursive"
   },
   {
      "name": "Jolly Lodger",
      "stack": "'Jolly Lodger', 'Comic Sans MS', cursive"
   },
   {
      "name": "Frijole",
      "stack": "'Frijole', 'Impact', fantasy"
   },
   {
      "name": "Eater Caps",
      "stack": "'Eater', fantasy"
   },
   {
      "name": "Nosifer Caps",
      "stack": "'Nosifer', fantasy"
   },
   {
      "name": "Butcherman Caps",
      "stack": "'Butcherman', cursive"
   },
   {
      "name": "Smokum",
      "stack": "'Smokum', 'Impact', serif"
   },
   {
      "name": "Snowburst One",
      "stack": "'Snowburst One', cursive"
   },
   {
      "name": "Barrio",
      "stack": "'Barrio', 'Impact', fantasy"
   },
   {
      "name": "New Rocker",
      "stack": "'New Rocker', 'Impact', fantasy"
   },
   {
      "name": "Germania One",
      "stack": "'Germania One', 'Impact', fantasy"
   },
   {
      "name": "Press Start 2P",
      "stack": "'Press Start 2P', 'Courier New', monospace"
   },
   {
      "name": "VT323",
      "stack": "'VT323', 'Courier New', monospace"
   },
   {
      "name": "Monoton",
      "stack": "'Monoton', 'Impact', display"
   },
   {
      "name": "Faster One",
      "stack": "'Faster One', 'Impact', display"
   },
   {
      "name": "Fascinate Inline",
      "stack": "'Fascinate Inline', 'Impact', display"
   },
   {
      "name": "Audiowide",
      "stack": "'Audiowide', 'Courier New', monospace"
   },
   {
      "name": "Orbitron",
      "stack": "'Orbitron', 'Courier New', monospace"
   },
   {
      "name": "Black Ops One",
      "stack": "'Black Ops One', 'Impact', fantasy"
   },
   {
      "name": "Wallpoet",
      "stack": "'Wallpoet', 'Courier New', monospace"
   },
   {
      "name": "Codystar",
      "stack": "'Codystar', cursive"
   },
   {
      "name": "Geostar",
      "stack": "'Geostar', cursive"
   },
   {
      "name": "Megrim",
      "stack": "'Megrim', monospace"
   },
   {
      "name": "Plaster",
      "stack": "'Plaster', Impact, fantasy"
   },
   {
      "name": "Vampiro One",
      "stack": "'Vampiro One', cursive"
   },
   {
      "name": "Silkscreen",
      "stack": "'Silkscreen', monospace"
   },
   {
      "name": "UnifrakturMaguntia",
      "stack": "'UnifrakturMaguntia', 'Times New Roman', serif"
   },
   {
      "name": "Trade Winds",
      "stack": "'Trade Winds', 'Impact', cursive"
   },
   {
      "name": "Metal Mania",
      "stack": "'Metal Mania', 'Impact', fantasy"
   },
   {
      "name": "Rye",
      "stack": "'Rye', 'Impact', serif"
   },
   {
      "name": "Sancreek",
      "stack": "'Sancreek', 'Georgia', serif"
   },
   {
      "name": "Pirata One",
      "stack": "'Pirata One', 'Georgia', serif"
   },
   {
      "name": "Akronim",
      "stack": "'Akronim', cursive"
   },
   {
      "name": "Shojumaru",
      "stack": "'Shojumaru', 'Impact', fantasy"
   },
   {
      "name": "Arbutus",
      "stack": "'Arbutus', 'Impact', fantasy"
   },
   {
      "name": "Astloch",
      "stack": "'Astloch', cursive"
   },
   {
      "name": "Bigelow Rules",
      "stack": "'Bigelow Rules', cursive"
   },
   {
      "name": "Sirin Stencil",
      "stack": "'Sirin Stencil', monospace"
   },
   {
      "name": "Nova Cut",
      "stack": "'Nova Cut', fantasy"
   },
   {
      "name": "Henny Penny",
      "stack": "'Henny Penny', cursive"
   },
   {
      "name": "Ewert",
      "stack": "'Ewert', fantasy"
   },
   {
      "name": "Diplomata",
      "stack": "'Diplomata', Impact, fantasy"
   },
   {
      "name": "Ranchers",
      "stack": "'Ranchers', Impact, fantasy"
   },
   {
      "name": "Aladin",
      "stack": "'Aladin', cursive"
   },
   {
      "name": "Macondo",
      "stack": "'Macondo', cursive"
   },
   {
      "name": "Papyrus",
      "stack": "Papyrus, fantasy, cursive"
   },
   {
      "name": "Bangers",
      "stack": "'Bangers', 'Impact', fantasy"
   },
   {
      "name": "Luckiest Guy",
      "stack": "'Luckiest Guy', 'Impact', fantasy"
   },
   {
      "name": "Chewy",
      "stack": "'Chewy', 'Comic Sans MS', cursive"
   },
   {
      "name": "Comic Sans MS",
      "stack": "'Comic Sans MS', 'Chalkboard SE', cursive"
   },
   {
      "name": "Sigmar One",
      "stack": "'Sigmar One', 'Impact', fantasy"
   },
   {
      "name": "Bowlby One SC",
      "stack": "'Bowlby One SC', 'Impact', fantasy"
   },
   {
      "name": "Lilita One",
      "stack": "'Lilita One', 'Impact', sans-serif"
   },
   {
      "name": "Titan One",
      "stack": "'Titan One', 'Impact', sans-serif"
   },
   {
      "name": "Changa One",
      "stack": "'Changa One', 'Impact', sans-serif"
   },
   {
      "name": "Carter One",
      "stack": "'Carter One', 'Impact', sans-serif"
   },
   {
      "name": "Fredericka the Great",
      "stack": "'Fredericka the Great', 'Courier New', monospace"
   },
   {
      "name": "Spicy Rice",
      "stack": "'Spicy Rice', cursive"
   },
   {
      "name": "Ultra",
      "stack": "'Ultra', Impact, serif"
   },
   {
      "name": "Paytone One",
      "stack": "'Paytone One', Impact, sans-serif"
   },
   {
      "name": "Concert One",
      "stack": "'Concert One', sans-serif"
   },
   {
      "name": "Sniglet",
      "stack": "'Sniglet', cursive"
   },
   {
      "name": "Life Savers",
      "stack": "'Life Savers', cursive"
   },
   {
      "name": "Love Ya Like A Sister",
      "stack": "'Love Ya Like A Sister', cursive"
   },
   {
      "name": "Kenia",
      "stack": "'Kenia', fantasy"
   },
   {
      "name": "Nova Slim",
      "stack": "'Nova Slim', monospace"
   },
   {
      "name": "Ceviche One",
      "stack": "'Ceviche One', fantasy"
   },
   {
      "name": "Neucha",
      "stack": "'Neucha', cursive"
   },
   {
      "name": "Pangolin",
      "stack": "'Pangolin', cursive"
   },
   {
      "name": "Short Stack",
      "stack": "'Short Stack', cursive"
   },
   {
      "name": "Schoolbell",
      "stack": "'Schoolbell', cursive"
   },
   {
      "name": "Lobster",
      "stack": "'Lobster', 'Comic Sans MS', cursive"
   },
   {
      "name": "Pacifico",
      "stack": "'Pacifico', 'Brush Script MT', cursive"
   },
   {
      "name": "Alfa Slab One",
      "stack": "'Alfa Slab One', Impact, serif"
   },
   {
      "name": "Abril Fatface",
      "stack": "'Abril Fatface', Georgia, serif"
   },
   {
      "name": "Bebas Neue",
      "stack": "'Bebas Neue', Impact, sans-serif"
   },
   {
      "name": "Oswald",
      "stack": "'Oswald', Impact, sans-serif"
   },
   {
      "name": "Russo One",
      "stack": "'Russo One', Impact, sans-serif"
   },
   {
      "name": "Righteous",
      "stack": "'Righteous', sans-serif"
   },
   {
      "name": "Staatliches",
      "stack": "'Staatliches', Impact, sans-serif"
   },
   {
      "name": "Anton",
      "stack": "'Anton', Impact, sans-serif"
   },
   {
      "name": "Acme",
      "stack": "'Acme', sans-serif"
   },
   {
      "name": "Patua One",
      "stack": "'Patua One', serif"
   },
   {
      "name": "Special Elite",
      "stack": "'Special Elite', 'Courier New', monospace"
   },
   {
      "name": "Yellowtail",
      "stack": "'Yellowtail', cursive"
   },
   {
      "name": "Cookie",
      "stack": "'Cookie', cursive"
   },
   {
      "name": "Courgette",
      "stack": "'Courgette', cursive"
   },
   {
      "name": "Amatic SC",
      "stack": "'Amatic SC', cursive"
   },
   {
      "name": "Cinzel Decorative",
      "stack": "'Cinzel Decorative', serif"
   },
   {
      "name": "DM Serif Display",
      "stack": "'DM Serif Display', Georgia, serif"
   },
   {
      "name": "Playfair Display",
      "stack": "'Playfair Display', Georgia, serif"
   },
   {
      "name": "Fraunces",
      "stack": "'Fraunces', Georgia, serif"
   },
   {
      "name": "Cormorant Garamond",
      "stack": "'Cormorant Garamond', Garamond, serif"
   },
   {
      "name": "Modern Antiqua",
      "stack": "'Modern Antiqua', serif"
   },
   {
      "name": "Overlock",
      "stack": "'Overlock', cursive"
   },
   {
      "name": "Sancreek Decorative",
      "stack": "'Sancreek', serif"
   },
   {
      "name": "Permanent Marker",
      "stack": "'Permanent Marker', cursive"
   },
   {
      "name": "Kaushan Script",
      "stack": "'Kaushan Script', cursive"
   },
   {
      "name": "Shadows Into Light",
      "stack": "'Shadows Into Light', cursive"
   },
   {
      "name": "Indie Flower",
      "stack": "'Indie Flower', cursive"
   },
   {
      "name": "Architects Daughter",
      "stack": "'Architects Daughter', cursive"
   },
   {
      "name": "Caveat",
      "stack": "'Caveat', cursive"
   },
   {
      "name": "Satisfy",
      "stack": "'Satisfy', cursive"
   },
   {
      "name": "Gloria Hallelujah",
      "stack": "'Gloria Hallelujah', cursive"
   },
   {
      "name": "Covered By Your Grace",
      "stack": "'Covered By Your Grace', cursive"
   },
   {
      "name": "Rock Salt",
      "stack": "'Rock Salt', cursive"
   },
   {
      "name": "Walter Turncoat",
      "stack": "'Walter Turncoat', cursive"
   },
   {
      "name": "Reenie Beanie",
      "stack": "'Reenie Beanie', cursive"
   },
   {
      "name": "Loved by the King",
      "stack": "'Loved by the King', cursive"
   },
   {
      "name": "Coming Soon",
      "stack": "'Coming Soon', cursive"
   },
   {
      "name": "Give You Glory",
      "stack": "'Give You Glory', cursive"
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
      "name": "Gochi Hand",
      "stack": "'Gochi Hand', cursive"
   },
   {
      "name": "Patrick Hand",
      "stack": "'Patrick Hand', cursive"
   },
   {
      "name": "Bad Script",
      "stack": "'Bad Script', cursive"
   },
   {
      "name": "Cedarville Cursive",
      "stack": "'Cedarville Cursive', cursive"
   },
   {
      "name": "Homemade Apple",
      "stack": "'Homemade Apple', cursive"
   },
   {
      "name": "La Belle Aurore",
      "stack": "'La Belle Aurore', cursive"
   },
   {
      "name": "Sue Ellen Francisco",
      "stack": "'Sue Ellen Francisco', cursive"
   },
   {
      "name": "Nothing You Could Do",
      "stack": "'Nothing You Could Do', cursive"
   },
   {
      "name": "Waiting for the Sunrise",
      "stack": "'Waiting for the Sunrise', cursive"
   },
   {
      "name": "Zeyada",
      "stack": "'Zeyada', cursive"
   },
   {
      "name": "Beth Ellen",
      "stack": "'Beth Ellen', cursive"
   },
   {
      "name": "Kalam",
      "stack": "'Kalam', cursive"
   },
   {
      "name": "Handlee",
      "stack": "'Handlee', cursive"
   },
   {
      "name": "Dancing Script",
      "stack": "'Dancing Script', cursive"
   },
   {
      "name": "Great Vibes",
      "stack": "'Great Vibes', cursive"
   },
   {
      "name": "Sacramento",
      "stack": "'Sacramento', cursive"
   },
   {
      "name": "Leckerli One",
      "stack": "'Leckerli One', cursive"
   },
   {
      "name": "Grand Hotel",
      "stack": "'Grand Hotel', cursive"
   },
   {
      "name": "Niconne",
      "stack": "'Niconne', cursive"
   },
   {
      "name": "Montez",
      "stack": "'Montez', cursive"
   },
   {
      "name": "Pinyon Script",
      "stack": "'Pinyon Script', cursive"
   },
   {
      "name": "Rochester",
      "stack": "'Rochester', cursive"
   },
   {
      "name": "Alex Brush",
      "stack": "'Alex Brush', cursive"
   },
   {
      "name": "Allura",
      "stack": "'Allura', cursive"
   },
   {
      "name": "Italianno",
      "stack": "'Italianno', cursive"
   },
   {
      "name": "Mr De Haviland",
      "stack": "'Mr De Haviland', cursive"
   },
   {
      "name": "Mrs Saint Delafield",
      "stack": "'Mrs Saint Delafield', cursive"
   },
   {
      "name": "Parisienne",
      "stack": "'Parisienne', cursive"
   },
   {
      "name": "Tangerine",
      "stack": "'Tangerine', cursive"
   },
   {
      "name": "Marck Script",
      "stack": "'Marck Script', cursive"
   },
   {
      "name": "Calligraffitti",
      "stack": "'Calligraffitti', cursive"
   },
   {
      "name": "Arizonia",
      "stack": "'Arizonia', cursive"
   },
   {
      "name": "Brush Script",
      "stack": "'Brush Script MT', 'Segoe Script', cursive"
   },
   {
      "name": "Impact",
      "stack": "Impact, 'Arial Black', sans-serif"
   },
   {
      "name": "Georgia",
      "stack": "Georgia, 'Times New Roman', serif"
   },
   {
      "name": "Courier New",
      "stack": "'Courier New', Courier, monospace"
   },
   {
      "name": "Trebuchet MS",
      "stack": "'Trebuchet MS', 'Lucida Sans', sans-serif"
   },
   {
      "name": "Palatino",
      "stack": "'Palatino Linotype', 'Book Antiqua', serif"
   },
   {
      "name": "Verdana",
      "stack": "Verdana, Geneva, sans-serif"
   },
   {
      "name": "Lucida Console",
      "stack": "'Lucida Console', Monaco, monospace"
   },
   {
      "name": "Century Gothic",
      "stack": "'Century Gothic', AppleGothic, sans-serif"
   },
   {
      "name": "Arial Black",
      "stack": "'Arial Black', Gadget, sans-serif"
   },
   {
      "name": "Garamond",
      "stack": "Garamond, 'Baskerville', serif"
   },
   {
      "name": "Times New Roman",
      "stack": "'Times New Roman', Times, serif"
   },
   {
      "name": "Tahoma",
      "stack": "Tahoma, Geneva, sans-serif"
   },
   {
      "name": "Geneva",
      "stack": "Geneva, Verdana, sans-serif"
   },
   {
      "name": "Helvetica",
      "stack": "Helvetica, Arial, sans-serif"
   },
   {
      "name": "Monaco",
      "stack": "Monaco, 'Courier New', monospace"
   },
   {
      "name": "Segoe UI",
      "stack": "'Segoe UI', Tahoma, sans-serif"
   },
   {
      "name": "Optima",
      "stack": "Optima, Segoe, sans-serif"
   },
   {
      "name": "Copperplate",
      "stack": "Copperplate, fantasy"
   },
   {
      "name": "Bookman",
      "stack": "'Bookman Old Style', Bookman, serif"
   },
   {
      "name": "Futura",
      "stack": "Futura, 'Trebuchet MS', sans-serif"
   },
   {
      "name": "Didot",
      "stack": "Didot, serif"
   },
   {
      "name": "Bodoni MT",
      "stack": "'Bodoni MT', Didot, serif"
   },
   {
      "name": "Franklin Gothic",
      "stack": "'Franklin Gothic Medium', Arial, sans-serif"
   },
   {
      "name": "Gill Sans",
      "stack": "'Gill Sans', sans-serif"
   },
   {
      "name": "Baskerville",
      "stack": "Baskerville, Garamond, serif"
   },
   {
      "name": "Big Caslon",
      "stack": "'Big Caslon', serif"
   },
   {
      "name": "American Typewriter",
      "stack": "'American Typewriter', monospace"
   },
   {
      "name": "Consolas",
      "stack": "Consolas, monospace"
   },
   {
      "name": "Outfit",
      "stack": "'Outfit', sans-serif"
   },
   {
      "name": "Roboto",
      "stack": "'Roboto', sans-serif"
   },
   {
      "name": "Open Sans",
      "stack": "'Open Sans', sans-serif"
   },
   {
      "name": "Montserrat",
      "stack": "'Montserrat', sans-serif"
   },
   {
      "name": "Lato",
      "stack": "'Lato', sans-serif"
   },
   {
      "name": "Poppins",
      "stack": "'Poppins', sans-serif"
   },
   {
      "name": "Inter",
      "stack": "'Inter', sans-serif"
   },
   {
      "name": "Raleway",
      "stack": "'Raleway', sans-serif"
   },
   {
      "name": "Nunito",
      "stack": "'Nunito', sans-serif"
   },
   {
      "name": "Cinzel",
      "stack": "'Cinzel', serif"
   },
   {
      "name": "Cardo",
      "stack": "'Cardo', serif"
   },
   {
      "name": "Dosis",
      "stack": "'Dosis', sans-serif"
   },
   {
      "name": "EB Garamond",
      "stack": "'EB Garamond', serif"
   },
   {
      "name": "Exo 2",
      "stack": "'Exo 2', sans-serif"
   },
   {
      "name": "Fira Sans",
      "stack": "'Fira Sans', sans-serif"
   },
   {
      "name": "Fredoka",
      "stack": "'Fredoka', sans-serif"
   },
   {
      "name": "Jost",
      "stack": "'Jost', sans-serif"
   },
   {
      "name": "Kanit",
      "stack": "'Kanit', sans-serif"
   },
   {
      "name": "Lexend",
      "stack": "'Lexend', sans-serif"
   },
   {
      "name": "Lora",
      "stack": "'Lora', serif"
   },
   {
      "name": "Manrope",
      "stack": "'Manrope', sans-serif"
   },
   {
      "name": "Plus Jakarta Sans",
      "stack": "'Plus Jakarta Sans', sans-serif"
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
