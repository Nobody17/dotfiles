curl -LJO https://github.com/zellij-org/zellij/releases/latest/download/zellij-x86_64-unknown-linux-musl.tar.gz
curl -LJO https://github.com/zellij-org/zellij/releases/latest/download/zellij-x86_64-unknown-linux-musl.sha256sum
if not sha256sum -c zellij-x86_64-unknown-linux-musl.sha256sum
    return 1
end
tar xf zellij-x86_64-unknown-linux-musl.tar.gz
install zellij /usr/local/bin
rm zellij
rm zellij-x86_64-unknown-linux-musl.tar.gz
