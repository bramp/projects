.PHONY: all

all: film.json netflix.json abc.json

clean:
	rm film.json netflix.json abc.json

film.json: fetch.py film.csv
	./fetch.py film.csv | tee film.json

netflix.json: fetch.py netflix.csv
	./fetch.py netflix.csv | tee netflix.json

abc.json: fetch.py abc.csv
	./fetch.py abc.csv | tee abc.json


