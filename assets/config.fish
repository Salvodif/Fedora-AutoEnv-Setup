if status is-interactive
    # Commands to run in interactive sessions can go here
end

atuin init fish | source
# Set up fzf key bindings
fzf --fish | source
zoxide init --cmd cd fish | source



alias df="dust"
alias du="duf"
alias top="btop"
alias cat="bat"
alias find="fd"
alias ls "eza --icons=always"
alias la "ls -a"
alias ll "ls -l"
alias lla "ll -a"
