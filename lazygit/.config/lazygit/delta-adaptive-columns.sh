#!/bin/bash
# Delta wrapper for lazygit.
# It splits the input into one chunk per file and renders each chunk with delta.
# A created or deleted file gets a single column, because one side would be empty.
# All other files get the side-by-side layout.

base_delta_arguments=(
  --dark
  --paging=never
  --line-numbers
  --hyperlinks
  --hyperlinks-file-link-format="lazygit-edit://{path}:{line}"
)

render_chunk() {
  local chunk_file=$1
  shift
  local delta_arguments=("${base_delta_arguments[@]}")

  if ! grep -q -E '^(new|deleted) file mode ' "$chunk_file"; then
    delta_arguments+=(--side-by-side)
  fi

  delta "${delta_arguments[@]}" "$@" < "$chunk_file"
}

chunk_directory=$(mktemp -d)
trap 'rm -rf "$chunk_directory"' EXIT

# Chunk 0000 holds possible preamble text (for example a commit header).
awk -v chunk_directory="$chunk_directory" '
  BEGIN { chunk_path = chunk_directory "/chunk-0000" }
  /^diff --git / {
    close(chunk_path)
    chunk_number += 1
    chunk_path = sprintf("%s/chunk-%04d", chunk_directory, chunk_number)
  }
  { print > chunk_path }
'

for chunk_file in "$chunk_directory"/chunk-*; do
  [ -e "$chunk_file" ] || continue
  render_chunk "$chunk_file" "$@"
done
