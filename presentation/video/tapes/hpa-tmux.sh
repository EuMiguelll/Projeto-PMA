#!/usr/bin/env bash
# 3 painéis como na página Load Testing: HPA, pods do gateway e gerador de carga
cd "/Users/migueldamasio/Programming/Insper/Quinto Semestre/Plataformas/Projeto-PMA"
T="tmux -f /dev/null -L hpa"
$T kill-server 2>/dev/null
$T new-session -d -s hpa -x 150 -y 40 -e PS1='$ ' bash --norc
$T set -g status off
$T set -g pane-border-status top
$T set -g pane-border-format ' #{pane_title} '
$T set -g pane-border-style 'fg=colour240'
$T set -g pane-active-border-style 'fg=colour114'
$T split-window -v -t hpa -e PS1='$ ' bash --norc
$T split-window -v -t hpa -e PS1='$ ' bash --norc
$T select-pane -t hpa:0.0 -T '1. HPA do gateway (CPU alvo 50%, 1-10 replicas)'
$T select-pane -t hpa:0.1 -T '2. Pods do gateway'
$T select-pane -t hpa:0.2 -T '3. Gerador de carga (busybox do enunciado)'
$T send-keys -t hpa:0.0 'clear; watch -t -n 1 kubectl get hpa gateway' Enter
$T send-keys -t hpa:0.1 'clear; watch -t -n 1 kubectl get pods -l app=gateway' Enter
$T send-keys -t hpa:0.2 'clear' Enter
$T resize-pane -t hpa:0.0 -y 4
$T resize-pane -t hpa:0.1 -y 14
$T select-pane -t hpa:0.2
exec $T attach -t hpa
