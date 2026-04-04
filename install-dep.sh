#!/bin/zsh
set -e

mkdir -p dep
cd dep

git clone https://github.com/mctechnology17/zmk-nice-oled.git
git clone https://github.com/GarrettFaucher/zmk-dongle-display-091-oled.git
git clone https://github.com/englmaxi/zmk-dongle-display.git
git clone https://github.com/qwerty22121998/nice-view-anim.git
