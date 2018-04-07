// Marvel Universe Timeline
// By Andrew Brampton (bramp.net)
// 
// TODO:
//   Change the z-index on hover (like https://stackoverflow.com/a/13794019/88646)
//   Highlight the apperances when not dim.
//   Introductions may not have the correct bounding box (text can overlap the small intro box)
//   
'use strict';

const movieWidth = 15; // Horiztonal width of movies
const labelSize = [100, 15];
const textHeight = 15;

let films = [];

function dim_all(value) {
	films.forEach(function(film){
		film._dim = value;
		film.characters.forEach(function(character) {
			character._dim = value;
		});
	});
}

function cssName(name) {
	return name.toLowerCase().replace(/\s+/g, '-');
}

function wrangle(data) {
	let charactersCache = {};

	return data.films.map(function(film){
		film.title = film.name.replace(/\s+\(film\)/g, '').split(': ', 2);
		film.characters = film['characters'].map(function(name){
			return findCharacterByName(name);
		});

		return film;
	});

	function findCharacterByName(name) {
		charactersCache = charactersCache || {};
		charactersCache[name] = charactersCache[name] || data.characters.find(function(character){
			return character.name === name;
		});
		return charactersCache[name];
	}
}

function transition(selection) {
  return selection.transition().duration(1000);
}

function fadein(selection) {
  return selection.transition().duration(1000);//.style("opacity", 1);
}

function fadeout(selection) {
  return selection.transition().duration(1000);//.style("opacity", 0);
}

/**
 * Appends two overlapping text elements to the object. This allows
 * the back text to add a white highlight around the front black text.
 *
 * @param      {<type>}  svg     The svg
 * @return     {<type>}  A new group element containing the text.
 */
function outlineText(svg) {
	let g = svg.append('g');

	// Append two actual 'text' nodes to fake an 'outside' outline.
	g.append('text').attr('class', 'outline');
	g.append('text');

	return g;
}

// Draw links between movies
function drawLinks(svg, narrative) {

	/*
	// Key function
	function(d) {
		if (d.source.scene) {
			 // This character's link from a particular movie
			return d.character.name + '-' + d.source.scene.name;
		}
		return d.character.name; // This characters source
	}
	*/

	let links = svg.selectAll('path').data(narrative.links());
	links.enter().append('path')
		.on("click", function(link) {
			dim_all(true);

			// Highlight the current character, and all movies
			link.character._dim = false;
			link.character.appearances.forEach(function(a){
				a.scene._dim = false;
			});

			draw();
			d3.event.stopPropagation();
		});
	fadeout(links.exit()).remove();

	fadein(links)
		.attr('d', narrative.link())
		.attr('class', function(d) {
			return  d.character._dim ? 'dim' : '';
		})
}

// Draw intro nodes (character names)
function drawIntros(svg, narrative) {
	let intros = svg.selectAll('g.intro').data(narrative.introductions(), function(intro) {
		return intro.character.name;
	});
	intros.exit().remove();

	let g = intros.enter().append('g')
		.attr('class', 'intro')
		.attr('transform', function(intro){
			let x = Math.round(intro.x);
			let y = Math.round(intro.y);
			return 'translate(' + [x, y] + ')';
		})
		.on("click", function(intro) {
			dim_all(true);

			// Highlight the current character, and all movies
			intro.character._dim = false;
			intro.character.appearances.forEach(function(appearance){
				appearance.scene._dim = false;
			});

			draw();
			d3.event.stopPropagation();
		});

	g.append('rect')
		.attr('y', -4)
		.attr('x', -4)
		.attr('width', 4)
		.attr('height', 8);

	outlineText(g).selectAll('text')
		.attr('text-anchor', 'end')
		.attr('y', '4px')
		.attr('x', '-8px');

	// Update
	g = fadein(intros)
		.attr('class', function(intro) {
			return 'intro s-' + cssName(intro.character.mainseries) + (intro.character._dim ? ' dim' : '');
		})
		.attr('transform', function(intro){
			let x = Math.round(intro.x);
			let y = Math.round(intro.y);
			return 'translate(' + [x, y] + ')';
		});

	g.selectAll('text')
		.text(function(intro){
			return intro.character.name;
		});
}

// Draw the movies
function drawMovies(svg, narrative) {
	let movies = svg.selectAll('g.movie').data(narrative.scenes(), function (scene) {
		return scene.name;
	});
	movies.exit().remove();

	let g = movies.enter().append('g')
		.attr('class', 'movie')
		.attr('transform', function(film){
			const x = Math.round(film.x)+0.5;
			const y = Math.round(film.y)+0.5 + textHeight;
			return 'translate('+[x, y]+')';
		})
		.on("click", function(film) {
			dim_all(true);

			// Highlight the movies and all characters
			film._dim = false;
			film.characters.forEach(function(character){
				character._dim = false;
			});

			draw();
			d3.event.stopPropagation();
		});

	g.append('rect')
		.attr('y', 0)
		.attr('x', 0)
		.attr('rx', 3)
		.attr('ry', 3);

	g.append('title');
	let text = outlineText(g).selectAll('text')
		.attr('text-anchor', 'middle')
		.attr('x', (movieWidth / 2) + 'px')
		.attr('y', '-1.8em');

	text.append('tspan')
		.attr('text-anchor', 'middle')
		.attr('x', (movieWidth / 2) + 'px');
	text.append('tspan')
		.attr('text-anchor', 'middle')
		.attr('x', (movieWidth / 2) + 'px')
		.attr('dy', '1.4em');

	// Update
	movies = transition(movies)
		.attr('class', function(scene) {
			return 'movie p' + scene.phase + ' s-' + cssName(scene.series);
		})
		.attr('transform', function(scene){
			const x = Math.round(scene.x)+0.5;
			const y = Math.round(scene.y)+0.5 + textHeight;
			return 'translate('+[x, y]+')';
		});

	movies.selectAll('rect')
		.attr('width', movieWidth)
		.attr('height', function(scene) {
			return scene.height - 2 * textHeight;
		})
		.attr('class', function(scene) {
			return scene._dim ? 'dim' : '';
		});

	text = movies.selectAll('text').attr('class', function(scene) {
		if (d3.select(this).classed('outline')) {
			return 'outline' + (scene._dim ? ' dim' : '');
		}
		return scene._dim ? 'dim' : '';
	});

	text.select('tspan:nth-child(1)').text(function(scene){
		if (scene.title.length > 1) {
			return scene.title[0];
		}
		return '';
	});
	text.select('tspan:nth-child(2)').text(function(scene){
		if (scene.title.length > 1) {
			return scene.title[1];
		}
		return scene.title[0];
	});
}

// Draw appearances (dots on the movies)
function drawAppearances(svg) {
	let appearances = svg.selectAll('.movie').selectAll('circle').data(function(scene){
		return scene.appearances;
	});
	appearances.enter().append('circle').attr('r', 3);
	appearances.exit().remove();

	svg.selectAll('.movie').selectAll('circle')
		.attr('class', function(appearance) {
			return appearance.character._dim ? 'dim' : '';
		})
		.attr('cx', function(appearance){
			return appearance.x;
		})
		.attr('cy', function(appearance){
			return appearance.y - textHeight;
		})
}

// Copyright (in bottom left)
function drawCopyright(svg, narrative) {
	let copyright = svg.selectAll('g.copyright').data([narrative]);
	copyright.exit().remove();

	let g = copyright.enter()
		.append('a').attr('xlink:href', 'https://bramp.net/');

	let text = outlineText(g)
		.attr('class', 'copyright')
		.attr('transform', function(n){
			const extent = n.extent();
			const x = 20;
			const y = (extent[1] - 2 * textHeight - 10);
			return 'translate('+[x, y]+')';
		})
		.selectAll('text');

	text.append('tspan')
		.text('Marvel Cinematic Universe - Character Timeline')
	text.append('tspan')
		.attr('x', '0').attr('dy', '1.4em')
		.text('By Andrew Brampton (bramp.net) - March 2018');

	// Update
	transition(svg.selectAll('g.copyright'))
		.attr('transform', function(n){
			const extent = n.extent();
			const x = 20;
			const y = (extent[1] - 2 * textHeight - 10);
			return 'translate('+[x, y]+')';
		});
}

function draw() {
	// Some defaults
	let suggestedWidth = films.length * movieWidth * 6;
	let suggestedHeight = 800;

	// Calculate the actual width of every character label.
	films.forEach(function(film){
		// Delete cached values (to ensure narrative recalculates them)
		delete film.x;
		delete film.y;
		delete film.start;
		delete film.duration;

		film.characters.forEach(function(character) {
			delete character.x;
			delete character.y;

			character.width = character.width || svg.append('text')
				.attr('opacity',0)
				.attr('class', 'temp')
				.text(character.name)
					.node().getComputedTextLength()+10;
		});
	});

	// Remove all the temporary labels.
	svg.selectAll('text.temp').remove();

	// Do the layout (https://abcnews.github.io/d3-layout-narrative/)
	let narrative = d3.layout.narrative()
		.scenes(films)
		.size([suggestedWidth, suggestedHeight])
		.pathSpace(labelSize[1])   // Vertical space available to each character’s path
		.groupMargin(0)            // Not sure
		.labelSize(labelSize)      // Intro label (character names) size
		.scenePadding([5 + textHeight, movieWidth/2, 5 + textHeight, movieWidth/2]) // Padding inside the scene
		.labelPosition('left')
		.layout();

	// Get the extent so we can re-size the SVG appropriately.
	transition(svg.data([narrative]))
		.attr('width', function(n) {
			return narrative.extent()[0] + 40; // 40px pad to fit the long "Avergers" title, which is last.
		})
		.attr('height', function(n) {
			return narrative.extent()[1];
		});

	drawLinks(svg, narrative);
	drawIntros(svg, narrative);
	drawMovies(svg, narrative);
	drawAppearances(svg);
	drawCopyright(svg, narrative);
}


// The container element (this is the HTML fragment);
let svg = d3.select('body').append('svg')
	.attr('xmlns', 'http://www.w3.org/2000/svg')
	.attr('xmlns:xlink', 'http://www.w3.org/1999/xlink')
	.attr('id', 'narrative-chart');

svg.on("click", function() {
	dim_all(false);
	draw();
});

// Request the data
d3.json('film.json', function(err, response){
	// Get the data in the format we need to feed to d3.layout.narrative().scenes
	films = wrangle(response);
	draw();
/*
	// Party time (to test moves)
	d3.interval(function() {
		films = d3.shuffle(films);
		draw();
	}, 1500);
*/
});
