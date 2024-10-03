#!/usr/bin/env fish

set helix_source_url (curl -s https://api.github.com/repos/helix-editor/helix/releases/latest | grep browser_download_url | grep 'x86_64\.tar\.xz"' | cut -d '"' -f 4)
curl $helix_source_url -LJo helix.tar.xz
mkdir -p helix
tar -xf helix.tar.xz -C helix --strip-components=1
sudo mv helix/hx /usr/local/bin/
mv helix/runtime/ ../helix/.config/helix
