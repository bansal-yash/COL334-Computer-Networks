build:
	g++ -o server-fifo server-fifo.cpp -lpthread
	g++ -o server-rr server-rr.cpp -lpthread
	g++ -o client-fifo client-fifo.cpp -lpthread
	g++ -o client-rr client-rr.cpp -lpthread
	g++ -o server-fairness-fifo server-fairness-fifo.cpp -lpthread
	g++ -o client-fairness-fifo client-fairness-fifo.cpp -lpthread
	g++ -o server-fairness-rr server-fairness-rr.cpp -lpthread
	g++ -o client-fairness-rr client-fairness-rr.cpp -lpthread
	rm -f time-fifo.txt 
	rm -f time-rr.txt 
	rm -f fairness.txt
	chmod +x run.sh

run: build
	@./run.sh run

run-fifo: build
	@./run.sh run-fifo

run-rr: build
	@./run.sh run-rr

server-fifo: build
	@./run.sh server-fifo

server-rr: build
	@./run.sh server-rr

client-fifo: build
	@./run.sh client-fifo

client-rr: build
	@./run.sh client-rr

plot: build
	@./run.sh plot
	python3 plot.py

fairness: build
	@./run.sh fairness

clean:
	@find . -type f -name '*.txt' ! -name 'words.txt' -exec rm -f {} +
	@rm -f server-fifo server-rr client-fifo client-rr server-fairness-fifo client-fairness-fifo server-fairness-rr client-fairness-rr
