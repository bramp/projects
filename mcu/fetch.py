#!/usr/bin/env python3
#
# TODO
# * Fix the parsing of characters with multiple names. War Machine doesn't appear in Iron Man 1 for this reason.
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

# Fields in the CSV
NAME_FIELD = "Name"
SERIES_FIELD = "Series"
PHASE_FIELD = "Phase"
YEAR_FIELD = "Year"

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

	return fetch(title, 'http://marvel-movies.wikia.com/api.php?' + params)

def parse_wiki_json(r, parser):
	data = json.loads(r.read())
	pages = data['query']['pages']
	for id, page in pages.items():
		parser(page)

def between(content, start, end):
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
	return character in('TBA', 'a to-be-confirmed character', 'To-be-confirmed character', 'a to-be-revealed character')

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

		# Filter out matches we don't want
		if isTBA(character):
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
		seasonCast = between(cast, (r'===\s*Season %d\s*===\n' % season), r'\n===[^=]')
		if seasonCast is None:
			if season == 1: # The very first season isn't found, so assume a single season TV show
				for character, actor in parse_cast(cast):
					characters[character].add((title, season))
			break
		for character, actor in parse_cast(seasonCast):
			characters[character].add((title, season))
		season += 1

	return

	# Repeat this a few times, for different seasons

	cast = between(content, r'=+\s*Main(?: Cast)?\s*=+\n', r'==')
	if cast is None:
		raise Exception('failed to find cast in ' + title)



def parse_film(page):
	title = page['title']
	content = page['revisions'][0]['*']
	cast = between(content, r'==\s*Cast\s*==\n', r'==')
	if cast is None:
		raise Exception('failed to find cast in ' + title)

	for character, actor in parse_cast(cast):
		if actor == 'Stan Lee':
			character = 'Stan Lee'

		elif character == 'Thor Odinson':
			character = 'Thor'

		elif character == 'Loki Laufeyson':
			character = 'Loki'

		elif character == 'James Rhodes':
			character = 'War Machine'

		characters[character].add((title, None))


def set_default(obj):
    if isinstance(obj, SortedSet):
        return list(obj)
    raise TypeError

def filmSeasonTitle(film, season):
	if season:
		return film + (" (season %d)" % season)
	return film

def tryInt(s):
	try:
		int(s)
		return True
	except:
		return False

def output_json(corpus, films_index, characters):
	json_films = dict()

	for character, films in characters.items():
		for film, season in films:
			title = filmSeasonTitle(film, season)
			if title in json_films:
				continue

			json_film = {
		 		'name': title,
		 		'characters': [],
		 	}

			if season:
				json_film['season'] = season

			# Find the movie in the film_index
			f = next(f for f in films_index if f[NAME_FIELD] == film)
			if not f:
				raise Exception('failed to find film ' + title)

			# Adds additional information, such as order, series, etc
			for key, value in f.items():
				if key not in json_film:
					if tryInt(value):
						json_film[key.lower()] = int(value)
					else:
						json_film[key.lower()] = value

			json_films[title] = json_film


	json_characters = []
	for character, films in characters.items():
		series = defaultdict(int)
		if corpus == "film": # TODO Change to "if has series"
			# Which series is this character in
			for name, season in films:
				title = filmSeasonTitle(name, season)
				series[json_films[title]['series']] += 1

			series = sorted(series.items(), key=lambda x: (x[1], x[0]), reverse=True)
			main = series[0][0]

			# If Avengers is #1 make sure there isn't a more specific movie with a equal score
			if main == 'Avengers' and len(series) > 1:
				if series[0][1] == series[1][1]:
					main = series[1][0]

			# HACK There are characters who appeared in more other films, than their own!
			#if character == 'Hulk':
			#	main = 'Hulk'
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
			main = 'TV'

		json_characters.append({
			'name': character,
			'films': len(films),
			'series': len(series),
			'mainseries': main,
		})
		for (film, season) in films:
			title = filmSeasonTitle(film, season)
			json_films[title]['characters'].append(character)

	#json_characters = sorted(json_characters, key=lambda character: character['name'])
	#json_films = sorted(json_films.values(), key=lambda film: film['name'])
	json_films = sorted(json_films.values(), key=lambda film: film['order'])

	data = {
		'characters': json_characters,
		#'films': [json_films[film[NAME_FIELD]] for film in films_index], # Ensure the films are in order
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
	if corpus == "film":
		parser = parse_film
	elif corpus == "tv":
		parser = parse_tv
	else:
		raise Exception('Invalid corpus %s' % corpus)

	for film in films:
		with fetch_wiki_json(film[NAME_FIELD]) as page:
			parse_wiki_json(page, parser)

	if corpus == "film":
		characters['Doctor Strange'].add(("Doctor Strange (film)", None)) # TODO Fix this

		# Ensure Stan Lee is in all the movies
		for film in films:
			characters['Stan Lee'].add((film['Name'], None))

	#print(json.dumps(characters, default=set_default, indent='\t'))
	output_json(corpus, films, characters)

if __name__ == '__main__':
	main()