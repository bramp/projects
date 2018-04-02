#!/usr/bin/env python3

import urllib.parse
import urllib.request, json 
import csv
import time
import re
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

def fetch_films(films):
	for film in films:
		request = {
			'action': 'query',
			'prop': 'revisions', 
			'rvprop': 'content',
			'format': 'json',
			'formatversion': '2',
			'titles': film[NAME_FIELD],
		}
		params = urllib.parse.urlencode(request)

		r = fetch(film[NAME_FIELD], 'http://marvel-movies.wikia.com/api.php?' + params)
		parse_film_json(r)

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

def parse_film(page):
	title = page['title']
	content = page['revisions'][0]['*']
	cast = between(content, r'==\s*Cast\s*==\n', r'==')
	if cast is None:
		raise Exception('failed to find cast in ' + title)

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
		if character in('a to-be-confirmed character', 'To-be-confirmed character', 'a to-be-revealed character'):
			continue

		if actor == 'Stan Lee':
			character = 'Stan Lee'

		elif character == 'Thor Odinson':
			character = 'Thor'

		elif character == 'Loki Laufeyson':
			character = 'Loki'

		elif character in ('himself', 'herself', 'Himself', 'Herself'):
			character = actor

		characters[character].add(title)

def parse_film_json(r):
	data = json.loads(r.read())
	pages = data['query']['pages']
	for id, page in pages.items():
		parse_film(page)

def set_default(obj):
    if isinstance(obj, SortedSet):
        return list(obj)
    raise TypeError

def output_json(films_index, characters):
	data_films = dict()
	for i, film in enumerate(films_index):
		name = film[NAME_FIELD]
		data_films[name] = {
			'name': name,
			'characters': [],
			'order': i,
			'phase': int(film[PHASE_FIELD]),
			'year': int(film[YEAR_FIELD]),
			'series': film[SERIES_FIELD],
		}

	data_characters = []
	for character, films in characters.items():
		# Skip characters who weren't in many films
		if len(films) <= 1:
			continue

		# Which series is this character in
		series = defaultdict(int)
		for film in films_index:
			if film[NAME_FIELD] in films:
				series[film[SERIES_FIELD]] += 1

		main = max(series.items(), key=operator.itemgetter(1))[0]

		# HACK There are characters who appeared in more other films, than their own!
		if character == 'Hulk':
			main = 'Hulk'
		elif character == 'Black Panther':
			main = 'Black Panther'
		elif character == 'Stan Lee':
			main = 'Avengers'

		# Skip characters who don't cross series
		# TODO Filter this cient side
		if len(series) <= 1:
			continue

		data_characters.append({
			'name': character,
			'films': len(films),
			'series': len(series),
			'mainseries': main,
		})
		for film in films:
			data_films[film]['characters'].append(character)

	#title = title.replace(' (film)', '')

	data = {
		# TODO Change the data format to not need ID
		'characters': data_characters,
		'films': [data_films[film[NAME_FIELD]] for film in films_index], # Ensure the films are in order
	}

	print(json.dumps(data, default=set_default, indent='\t'))

characters = defaultdict(SortedSet) # Global var

if __name__ == '__main__':
	films = []
	with open('films.csv', 'r') as f:
		for row in csv.DictReader(f):
			films.append( row )

	fetch_films(films)

	# Ensure Stan Lee is in all the movies
	for film in films:
		characters['Stan Lee'].add(film['Name'])

	# BUG Ensure Doctor Strange is in his own movie
	characters['Doctor Strange'].add("Doctor Strange (film)")

	#print(json.dumps(characters, default=set_default, indent='\t'))
	output_json(films, characters)

