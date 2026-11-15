#!/usr/bin/env bash
# Teste de carga do enunciado (página Load Testing), adaptado: gera carga DE DENTRO do
# cluster no /info do gateway. Abra 3 terminais (ver load-test/README.md):
#   T1: watch -n 1 kubectl get hpa gateway
#   T2: watch -n 1 kubectl get pods -l app=gateway
#   T3: ./load-test/busybox.sh            (Ctrl+C para parar; o pod é removido)
# Variáveis: TARGET (padrão http://gateway/info), SLEEP (padrão 0.01), WORKERS (padrão 4)
TARGET=${TARGET:-http://gateway/info}
SLEEP=${SLEEP:-0.01}
WORKERS=${WORKERS:-4}
kubectl run -i --tty load-generator --rm --image=busybox:1.28 --restart=Never -- /bin/sh -c \
  "for i in \$(seq $WORKERS); do (while sleep $SLEEP; do wget -q -O- $TARGET >/dev/null; done) & done; wait"
