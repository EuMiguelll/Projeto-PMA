Output clips/bottlenecks.mp4
Set Shell "bash"
Set FontSize 26
Set Width 1920
Set Height 1080
Set Padding 40
Set Theme "Catppuccin Mocha"
Set TypingSpeed 18ms
Set WindowBar Colorful
Set WindowBarSize 44
Hide
Type `source "/Users/migueldamasio/Programming/Insper/Quinto Semestre/Plataformas/video/tapes/demo-env.sh" && clear`
Enter
Sleep 1s
Show
Sleep 500ms
Type "seq 300 | xargs -P 50 -I{} curl -s -o /dev/null -w '%{http_code}\n' localhost:8080/auth/logout | sort | uniq -c"
Enter
Sleep 3s
Type "docker compose exec redis redis-cli --scan"
Enter
Sleep 2.5s
Type "docker compose stop account"
Enter
Sleep 4s
Type "for i in $(seq 8); do login; done"
Enter
Sleep 5s
Type "circuitos"
Enter
Sleep 4s
Type "docker compose start account"
Enter
Sleep 3s
