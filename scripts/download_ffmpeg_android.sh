#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DOWNLOADS="$ROOT/.ffmpeg-downloads"
TARGET_ROOT="$ROOT/bin/android"
mkdir -p "$DOWNLOADS" "$TARGET_ROOT"

download_one() {
  local abi="$1"
  local url="$2"
  local zip_path="$DOWNLOADS/$abi.zip"
  local extract_dir="$DOWNLOADS/$abi"
  local target_dir="$TARGET_ROOT/$abi"

  echo "Downloading $abi..."
  curl -L "$url" -o "$zip_path"
  rm -rf "$extract_dir"
  mkdir -p "$extract_dir" "$target_dir"
  unzip -q -o "$zip_path" -d "$extract_dir"

  local ffmpeg
  local ffprobe
  ffmpeg="$(find "$extract_dir" -type f -name ffmpeg | head -n 1)"
  ffprobe="$(find "$extract_dir" -type f -name ffprobe | head -n 1)"

  if [[ -z "$ffmpeg" || -z "$ffprobe" ]]; then
    echo "Could not find ffmpeg/ffprobe in $zip_path" >&2
    exit 1
  fi

  cp "$ffmpeg" "$target_dir/ffmpeg"
  cp "$ffprobe" "$target_dir/ffprobe"
  cp "$ffmpeg" "$target_dir/ffmpeg.bin"
  cp "$ffprobe" "$target_dir/ffprobe.bin"
  chmod +x "$target_dir/ffmpeg" "$target_dir/ffprobe" "$target_dir/ffmpeg.bin" "$target_dir/ffprobe.bin"

  local lib_dir
  lib_dir="$(find "$extract_dir" -type d -name lib | head -n 1)"
  if [[ -n "$lib_dir" ]]; then
    mkdir -p "$target_dir/lib"
    cp "$lib_dir"/*.so "$target_dir/lib/"
  fi
}

download_one "arm64-v8a" "https://github.com/husen-hn/ffmpeg-android-binary/releases/download/v2.0.0/arm64-v8a.zip"
download_one "armeabi-v7a" "https://github.com/husen-hn/ffmpeg-android-binary/releases/download/v2.0.0/armeabi-v7a.zip"
download_one "x86_64" "https://github.com/husen-hn/ffmpeg-android-binary/releases/download/v2.0.0/x86_64.zip"

echo "Done. Binaries are in bin/android/<abi>/"
