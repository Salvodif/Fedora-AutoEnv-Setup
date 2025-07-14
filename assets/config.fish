if status is-interactive
    # Commands to run in interactive sessions can go here
end

atuin init fish | source
# Set up fzf key bindings
fzf --fish | source
zoxide init fish | source

alias ls "eza --icons=always"
alias la "ls -a"
alias ll "ls -l"
alias lla "ll -a"
