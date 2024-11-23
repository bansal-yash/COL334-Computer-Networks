build:
	g++ -o server server.cpp -lpthread
	g++ -o client client.cpp -lpthread
	rm -f time.txt 
	chmod +x run.sh

run: build
	@./run.sh run
	
server: build
	@./run.sh server

client: build
	@./run.sh client

plot: build
	rm -f time.txt
	@./run.sh plot
	python3 plot.py

clean:
	@find . -type f -name '*.txt' ! -name 'words.txt' -exec rm -f {} +
	@rm -f server client
