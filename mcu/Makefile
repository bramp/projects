.PHONY: all clean server

all: film.json netflix.json abc.json

clean:
	rm film.json netflix.json abc.json

cache:
	mkdir cache

server:
	python -m SimpleHTTPServer 8000

film.json: fetch.py film.csv cache
	./fetch.py film.csv | tee film.json

netflix.json: fetch.py netflix.csv cache
	./fetch.py netflix.csv | tee netflix.json

abc.json: fetch.py abc.csv cache
	./fetch.py abc.csv | tee abc.json

