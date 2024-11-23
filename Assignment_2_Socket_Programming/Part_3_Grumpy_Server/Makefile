build:
	g++ -o server server.cpp -lpthread
	g++ -o client client.cpp -lpthread

run: build
	chmod +x run.sh
	@./run.sh
	
server: build
	chmod +x run_server.sh
	@./run_server.sh

client: build
	chmod +x run_client.sh
	@./run_client.sh

run-aloha: build
	chmod +x run.sh
	@./run.sh aloha

clean:
	@find . -type f -name '*.txt' ! -name 'words.txt' -exec rm -f {} +
	@rm -f server client