.PHONY: all

all: film.json netflix.json abc.json

clean:
	rm film.json netflix.json abc.json

cache:
	mkdir cache

film.json: fetch.py film.csv cache
	./fetch.py film.csv | tee film.json

netflix.json: fetch.py netflix.csv cache
	./fetch.py netflix.csv | tee netflix.json

abc.json: fetch.py abc.csv cache
	./fetch.py abc.csv | tee abc.json


