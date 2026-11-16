cd "/Users/migueldamasio/Programming/Insper/Quinto Semestre/Plataformas/Projeto-PMA"
export PS1='\[\e[1;32m\]$ \[\e[0m\]'
login() { curl -s -o /dev/null -w "login -> %{http_code} em %{time_total}s\n" -X POST localhost:8080/auth/login -H 'Content-Type: application/json' -d '{"email":"demo@insper.edu.br","password":"123@321"}'; }
circuitos() { sleep 2; curl -s localhost:9090/api/v1/query --data-urlencode 'query=resilience4j_circuitbreaker_state{state="open"}' | jq -r '.data.result[] | "circuito \(.metric.name): " + (if .value[1]=="1" then "OPEN" else "CLOSED" end)'; }
