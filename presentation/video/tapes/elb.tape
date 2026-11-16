Output clips/elb-smoke.mp4
Set Shell "bash"
Set FontSize 26
Set Width 1920
Set Height 1080
Set Padding 40
Set Theme "Catppuccin Mocha"
Set TypingSpeed 30ms
Set WindowBar Colorful
Set WindowBarSize 44
Hide
Type `cd "/Users/migueldamasio/Programming/Insper/Quinto Semestre/Plataformas/Projeto-PMA" && export PS1='\[\e[1;32m\]$ \[\e[0m\]' && export ELB=http://a0fe1d39fd35640c4b0de61fe105bdb5-64525269.us-east-2.elb.amazonaws.com && clear`
Enter
Sleep 1s
Show
Sleep 500ms
Type "echo $ELB"
Enter
Sleep 1.5s
Type "curl -s $ELB/info | jq"
Enter
Sleep 2.5s
Type "./scripts/smoke-test.sh $ELB"
Enter
Sleep 12s
