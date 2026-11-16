Output clips/hpa-raw.mp4
Set Shell "bash"
Set FontSize 24
Set Width 1920
Set Height 1080
Set Padding 30
Set Framerate 12
Set Theme "Catppuccin Mocha"
Set TypingSpeed 40ms
Set WindowBar Colorful
Set WindowBarSize 44
Hide
Type `bash "/Users/migueldamasio/Programming/Insper/Quinto Semestre/Plataformas/video/tapes/hpa-tmux.sh"`
Enter
Sleep 4s
Show
Sleep 6s
Type "WORKERS=16 ./load-test/busybox.sh"
Enter
Sleep 150s
Ctrl+C
Sleep 3s
Type "kubectl get hpa gateway"
Enter
Sleep 380s
