#!/usr/bin/env python3
#
# TODO
# * Fix the parsing of characters with multiple names. e.g War Machine is listed as "James Rhodes" in Iron Man 1, but "James Rhodes / War Machine" in Iron Man 2
# 
import urllib.parse
import urllib.request, json 
import csv
import sys
import time
import re
import os
from collections import defaultdict
from sortedcontainers import SortedSet
import operator

WIKI = 'http://marvel-movies.wikia.com/api.php?'

# Fields in the CSV
NAME_FIELD = 'Name'

# Extra info to add to the films
extra = {
	# Netflex
	'Daredevil (Season 1)' : {'released': '2015-04-10'},
	'Jessica Jones (Season 1)' : {'released': '2015-11-20'},

	'Daredevil (Season 2)' : {'released': '2016-03-18'},
	'Luke Cage (Season 1)' : {'released': '2016-09-30'},

	'Iron Fist (Season 1)' : {'released': '2017-03-17'},
	'The Defenders (Season 1)' : {'released': '2017-08-18'},
	'The Punisher (Season 1)' : {'released': '2017-11-17'},

	'Jessica Jones (Season 2)' : {'released': '2018-03-08'},
	'Luke Cage (Season 2)' : {'released': '2018-06-22'},

	'Daredevil (Season 3)' : {'released': '2018-99-01'},    # unknown released date
	'Iron Fist (Season 2)' : {'released': '2018-99-02'},    # unknown released date
	'The Punisher (Season 2)' : {'released': '2018-99-03'}, # unknown released date

	# ABC
	'Agents of S.H.I.E.L.D. (Season 1)' : {'released': '2013-09-24'},
	'Agents of S.H.I.E.L.D. (Season 2)' : {'released': '2014-09-23'},
	'Agent Carter (Season 1)' : {'released': '2015-01-06'},
	'Agents of S.H.I.E.L.D. (Season 3)' : {'released': '2015-09-29'},
	'Agent Carter (Season 2)' : {'released': '2016-01-19'},
	'Agents of S.H.I.E.L.D. (Season 4)' : {'released': '2016-09-20'},
	'Inhumans (Season 1)' : {'released': '2017-09-29'},
	'Agents of S.H.I.E.L.D. (Season 5)' : {'released': '2017-12-01'},
}


def fetch(name, url):
	filename = 'cache/' + name
	try:
		return open(filename, 'r')
	except FileNotFoundError:
		with urllib.request.urlopen(url) as r:
			with open(filename, 'w') as f:
				f.write(r.read().decode('utf-8'))
			time.sleep(1)
	return open(filename, 'r')

def fetch_wiki_json(title):
	request = {
		'action': 'query',
		'prop': 'revisions', 
		'rvprop': 'content',
		'format': 'json',
		'formatversion': '2',
		'titles': title,
	}
	params = urllib.parse.urlencode(request)
	return fetch(title, WIKI + params)

def parse_wiki_json(r, parser):
	data = json.loads(r.read())
	pages = data['query']['pages']
	for id, page in pages.items():
		parser(page)

def between(content, start, end):
	'''Return the content between two regex matches'''
	start = re.compile(start)
	s = start.search(content)
	if s is None:
		return None

	end = re.compile(end)
	e = end.search(content, s.end(0))
	if e is None:
		return None

	return content[s.end(0):e.start(0)]

def parse_wiki_link(s):
	try:
		# find the last link in s with the greedy '.*'
		link = between(s, r'.*\[\[', r'\]\]')
		if link is None:
			return s

		if '|' in link:
			left, right = link.split('|', 1)
			a = right.rfind('/')
			if a == -1:
				return right

			return right[a + 1:len(right)]

		return link

	except ValueError:
		return s

def isTBA(character):
	return character in('TBA', 'a to-be-confirmed character', 'To-be-confirmed character', 'a to-be-revealed character', '\'\'To be added\'\'')

def isHeading(character):
	return character.startswith('=')

def parse_cast(cast):
	actors = []
	for line in cast.splitlines():
		line = line.lstrip('*')
		if line == '':
			continue

		m = re.match(r'(.+)\s+as\s+(.+)', line)
		if m:
			actor = m.group(1)
			character = m.group(2)
		else:
			actor = character = line

		actor = parse_wiki_link(actor)
		character = parse_wiki_link(character)

		# Filter out matches we don't know
		if isTBA(character):
			continue

		if isHeading(character):
			continue

		if character.lower().startswith(('himself', 'herself', 'Himself', 'Herself')):
			character = actor

		actors.append((character, actor))
	return actors

def parse_tv(page):
	title = page['title']
	content = page['revisions'][0]['*']

	# Find the cast section ==Cast==
	cast = between(content, r'==\s*Cast\s*==\n', r'\n==[^=]')
	if cast is None:
		raise Exception('failed to find cast in ' + title)

	season = 1
	while True:
		seasonCast = between(cast, (r'===\s*Season %d\s*===\n' % season), r'\n(===[^=]|$)')
		if seasonCast is None:
			if season == 1: # The very first season isn't found, so assume a single season TV show
				for character, actor in parse_cast(cast):
					character, actor = fix_character(character, actor)
					characters[character].add((title, season))

			break

		for character, actor in parse_cast(seasonCast):
			character, actor = fix_character(character, actor)
			characters[character].add((title, season))

		season += 1


def fix_character(character, actor):
	if actor == 'Stan Lee':
		character = 'Stan Lee'

	elif character == 'Thor Odinson':
		character = 'Thor'

	elif character == 'Loki Laufeyson':
		character = 'Loki'

	elif character == 'James Rhodes':
		character = 'War Machine'

	elif character == 'Dr. Strange':
		character = 'Doctor Strange'

	# Shield
	elif character == 'Quake':
		character = 'Daisy Johnson'

	elif character == 'Alphonso Mackenzie':
		character = 'Alphonso "Mack" Mackenzie'

	elif character == 'Slingshot':
		character = 'Yo-Yo' # Elena "Yo-Yo" Rodriguez/Slingshot

	# Netflix
	elif character == 'Franklin "Foggy" Nelson':
		character = 'Foggy Nelson'

	return character, actor


def parse_film(page):
	title = page['title']
	content = page['revisions'][0]['*']
	cast = between(content, r'==\s*Cast\s*==\n', r'==')
	if cast is None:
		raise Exception('failed to find cast in ' + title)

	for character, actor in parse_cast(cast):
		character, actor = fix_character(character, actor)
		characters[character].add((title, None))

def tryInt(s):
	try:
		int(s)
		return True
	except:
		return False

def get(d, keys):
	for k in keys:
		if k in d:
			return d[k]
	return None

def set_default(obj):
    if isinstance(obj, SortedSet):
        return list(obj)
    raise TypeError

def filmTitle(film):
	film = film.replace(' (film)', '')
	film = film.replace(' (Netflix series)', '')
	film = film.replace(' (TV series)', '')
	return film

def filmSeasonTitle(film, season):
	film = filmTitle(film)
	if season:
		return film + (' (Season %d)' % season)
	return film

def output_json(corpus, films_index, characters):
	json_films = dict()

	for character, films in characters.items():
		for wiki_title, season in films:
			title = filmTitle(wiki_title)
			long_title = filmSeasonTitle(wiki_title, season)
			if long_title in json_films:
				continue

			json_film = {
		 		'name': long_title,
		 		'wiki': wiki_title,
		 		'characters': [],
		 	}

			if season:
				json_film['series'] = title
				json_film['season'] = season

			# Find the movie in the film_index
			f = next(f for f in films_index if f[NAME_FIELD] == wiki_title)
			if not f:
				raise Exception('failed to find film ' + wiki_title)

			# Adds additional information, such as order, series, etc
			for key, value in f.items():
				key = key.lower()
				if key not in json_film:
					if tryInt(value):
						json_film[key] = int(value)
					else:
						json_film[key] = value

			if long_title in extra:
				json_film.update(extra[long_title])

			json_films[long_title] = json_film

	json_characters = []
	for character, films in characters.items():
		series = defaultdict(int)

		# Which series is this character in
		for name, season in films:
			title = filmSeasonTitle(name, season)
			series[json_films[title]['series']] += 1

		series = sorted(series.items(), key=lambda x: (x[1], x[0]), reverse=True)
		main = series[0][0]

		if corpus == 'film': # TODO Change to 'if has series'
			# If Avengers is #1 make sure there isn't a more specific movie with a equal score
			if main == 'Avengers' and len(series) > 1:
				if series[0][1] == series[1][1]:
					main = series[1][0]

			# There are characters who appeared in more other films, than their own!
			if character == 'Stan Lee':
				main = 'Avengers'
			elif character == 'F.R.I.D.A.Y.':
				main = 'Iron Man'
			elif character == 'Doctor Strange':
				main = 'Doctor Strange'
			elif character in ('Black Panther', 'Ayo', 'T\'Chaka'):
				main = 'Black Panther'
			elif character == 'Vision':
				main = 'Avengers'
			elif character == 'Ant-Man':
				main = 'Ant-Man'

			# Skip characters who don't cross series
			# TODO Filter this cient side
			if len(series) <= 1:
				continue
		else:
			# Skip characters who aren't in more than one season
			if len(films) <= 1:
				continue

		json_characters.append({
			'name': character,
			'films': len(films),   # Number of films, or number of TV seasons.
			'series': len(series), # Number of film series or TV series.
			'mainseries': main,    # The main series they are associated with.
		})
		for (film, season) in films:
			title = filmSeasonTitle(film, season)
			json_films[title]['characters'].append(character)


	# TODO Sort this data, so its easier to diff changes in the output.
	#json_characters = sorted(json_characters, key=lambda character: character['name'])
	#json_films = sorted(json_films.values(), key=lambda film: film['name'])
	json_films = sorted(json_films.values(), key=lambda film: get(film, ['released', 'name']))

	data = {
		'characters': json_characters,
		'films': json_films,
	}

	print(json.dumps(data, default=set_default, indent='\t'))

characters = defaultdict(SortedSet) # Global var

def main():
	if len(sys.argv) < 2:
		print('{0} <csv file>'.format(sys.argv[0]))
		sys.exit(0)

	filename = sys.argv[1]
	films = []
	with open(filename, 'r') as f:
		for row in csv.DictReader(f):
			films.append( row )

	corpus = os.path.splitext(filename)[0]
	if corpus == 'film':
		parser = parse_film
	elif corpus in ('abc', 'netflix'):
		parser = parse_tv
	else:
		raise Exception('Invalid corpus %s' % corpus)

	for film in films:
		with fetch_wiki_json(film[NAME_FIELD]) as page:
			parse_wiki_json(page, parser)

	if corpus == 'film':
		characters['Doctor Strange'].add(('Doctor Strange (film)', None)) # TODO Fix this

		# Ensure Stan Lee is in all the movies
		for film in films:
			characters['Stan Lee'].add((film['Name'], None))

	#print(json.dumps(characters, default=set_default, indent='\t'))
	output_json(corpus, films, characters)

if __name__ == '__main__':
	main()