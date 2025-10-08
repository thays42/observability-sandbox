.PHONY: stack dice-roller shiny-curl-gui all down clean

stack:
	docker compose --project-directory stack up -d 

dice-roller:
	docker compose --project-directory dice-roller up -d

shiny-curl-gui:
	docker compose --project-directory shiny-curl-gui up -d

all: stack dice-roller shiny-curl-gui

down:
	docker compose --project-directory shiny-curl-gui down
	docker compose --project-directory dice-roller down
	docker compose --project-directory stack down

clean: down
	docker volume rm stack_prometheus-data stack_loki-data stack_grafana-data 2>/dev/null || true
