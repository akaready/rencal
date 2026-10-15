#!/usr/bin/env bash
# Drive a dev build of renCal on Hyprland for screenshots. See ../SKILL.md.
#
#   shots.sh setup [YYYY-MM-DD]     isolated config + mock caldir around that week
#   shots.sh start                  run `pnpm tauri dev` against it (run in background)
#   shots.sh ready [WxH]            wait for the window, float/resize/center it, make it opaque
#   shots.sh shot <name> [title]    capture a window (default "renCal") to $DIR/shots/<name>.png
#   shots.sh key <wtype args...>    plain keys / text, e.g. `key w`, `key -k Escape`, `key lunch`
#   shots.sh combo <mods+key>       modifier shortcut via ydotool, e.g. `combo ctrl+k`, `combo ctrl+comma`
#   shots.sh click <x> <y> [title]  click at window-relative logical coords
#   shots.sh theme <name>           switch theme through the command palette
#   shots.sh cleanup                quit the dev app and stop ydotool if we started it
set -euo pipefail

DIR="${RENCAL_SHOTS_DIR:-${XDG_RUNTIME_DIR:-/tmp}/rencal-shots}"
SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(git -C "$SKILL_DIR" rev-parse --show-toplevel)"

die() {
  echo "$*" >&2
  exit 1
}

# The dev build's pid; the installed renCal (/usr/bin/rencal) may run alongside it.
dev_pid() {
  local pid
  for pid in $(hyprctl clients -j | jq -r '.[] | select(.class == "rencal") | .pid' | sort -u); do
    if [[ "$(readlink "/proc/$pid/exe" 2>/dev/null)" == */target/debug/rencal ]]; then
      echo "$pid"
      return
    fi
  done
  return 1
}

# "x y w h" of a dev window by title.
geometry() {
  local pid
  pid=$(dev_pid) || die "dev renCal window not found; run \`shots.sh start\` first"
  hyprctl clients -j | jq -r --argjson pid "$pid" --arg t "${1:-renCal}" \
    '.[] | select(.pid == $pid and .title == $t) | "\(.at[0]) \(.at[1]) \(.size[0]) \(.size[1])"' | head -1
}

dispatch() {
  hyprctl dispatch "$1" >/dev/null
}

opaque() {
  dispatch "hl.dsp.window.set_prop({ prop = \"opacity\", value = \"1 override\", window = \"$1\" })"
  dispatch "hl.dsp.window.set_prop({ prop = \"opaque\", value = \"1\", window = \"$1\" })"
}

address() {
  hyprctl clients -j | jq -r --argjson pid "$(dev_pid)" --arg t "${1:-renCal}" \
    '.[] | select(.pid == $pid and .title == $t) | .address' | head -1
}

# Focus a window and park the cursor in its empty top-center strip: focus follows
# the mouse and unfocused windows are dimmed, so the cursor must stay inside it.
focus() {
  local x y w h
  read -r x y w h < <(geometry "${1:-renCal}")
  [[ -n "${x:-}" ]] || die "no window titled '${1:-renCal}'"
  dispatch "hl.dsp.focus({ window = \"address:$(address "${1:-renCal}")\" })"
  dispatch "hl.dsp.cursor.move({ x = $((x + w / 2)), y = $((y + 8)) })"
  sleep 0.3
}

ensure_ydotool() {
  if ! systemctl --user is-active -q ydotool; then
    systemctl --user start ydotool
    touch "$DIR/.started-ydotool"
    sleep 0.5
  fi
}

keycode() {
  case "$1" in
    ctrl) echo 29 ;; shift) echo 42 ;; alt) echo 56 ;; super) echo 125 ;;
    esc | escape) echo 1 ;; tab) echo 15 ;; enter) echo 28 ;; space) echo 57 ;;
    comma) echo 51 ;; period) echo 52 ;; slash) echo 53 ;;
    up) echo 103 ;; down) echo 108 ;; left) echo 105 ;; right) echo 106 ;;
    [a-z])
      local row="qwertyuiop" mid="asdfghjkl" low="zxcvbnm" i
      for ((i = 0; i < ${#row}; i++)); do [[ ${row:i:1} == "$1" ]] && echo $((16 + i)) && return; done
      for ((i = 0; i < ${#mid}; i++)); do [[ ${mid:i:1} == "$1" ]] && echo $((30 + i)) && return; done
      for ((i = 0; i < ${#low}; i++)); do [[ ${low:i:1} == "$1" ]] && echo $((44 + i)) && return; done
      ;;
    *) die "unknown key: $1" ;;
  esac
}

cmd="${1:-}"
shift || true

case "$cmd" in
  setup)
    command -v caldir >/dev/null || die "caldir CLI not found"
    mkdir -p "$DIR/xdg/caldir" "$DIR/xdg/rencal" "$DIR/shots"
    # Keep fonts and GTK settings identical to the real session.
    for d in fontconfig gtk-3.0 gtk-4.0; do
      [[ -e "$HOME/.config/$d" ]] && ln -sfn "$HOME/.config/$d" "$DIR/xdg/$d"
    done
    printf 'calendar_dir = "%s"\ntime_format = "24h"\ndefault_reminders = []\n' "$DIR/caldir" \
      >"$DIR/xdg/caldir/config.toml"
    cat >"$DIR/xdg/rencal/config.toml" <<'EOF'
notifications_enabled = false
auto_sync_enabled = false
first_day_of_week = "monday"

[theme]
mode = "single"
single = "ren"
light = "ren-light"
dark = "ren"
EOF
    # Installed plugins live in the shared data dir; without a plugins list the
    # Plugins tab shows an error banner.
    if [[ -f "$HOME/.config/rencal/plugins.toml" ]]; then
      cp "$HOME/.config/rencal/plugins.toml" "$DIR/xdg/rencal/plugins.toml"
    else
      echo 'plugins = []' >"$DIR/xdg/rencal/plugins.toml"
    fi
    python3 -I "$SKILL_DIR/mock-caldir.py" "$DIR/caldir" "$@"
    echo "Shots go to $DIR/shots"
    ;;

  start)
    [[ -f "$DIR/xdg/caldir/config.toml" ]] || die "run \`shots.sh setup\` first"
    cd "$REPO"
    XDG_CONFIG_HOME="$DIR/xdg" exec pnpm tauri dev
    ;;

  ready)
    size="${1:-1400x875}"
    for _ in $(seq 1 300); do
      dev_pid >/dev/null && break
      sleep 2
    done
    pid=$(dev_pid) || die "timed out waiting for the dev window"
    w="pid:$pid"
    dispatch "hl.dsp.window.float({ action = \"enable\", window = \"$w\" })"
    dispatch "hl.dsp.window.resize({ x = ${size%x*}, y = ${size#*x}, window = \"$w\" })"
    dispatch "hl.dsp.window.center({ window = \"$w\" })"
    opaque "$w"
    ensure_ydotool
    sleep 1
    focus
    echo "ready: pid $pid, $(geometry)"
    ;;

  shot)
    name="${1:?shot <name> [title]}"
    title="${2:-renCal}"
    read -r x y w h < <(geometry "$title")
    [[ -n "${x:-}" ]] || die "no window titled '$title'"
    # Settings and other secondary windows open translucent too.
    opaque "address:$(address "$title")"
    focus "$title"
    sleep 0.3
    grim -g "$x,$y ${w}x$h" "$DIR/shots/$name.png"
    echo "$DIR/shots/$name.png"
    ;;

  key)
    focus
    wtype "$@"
    sleep 0.8
    ;;

  combo)
    ensure_ydotool
    focus "${2:-renCal}"
    IFS=+ read -ra parts <<<"${1:?combo <mods+key>}"
    down=() up=()
    for p in "${parts[@]}"; do
      c=$(keycode "$p")
      down+=("$c:1")
      up=("$c:0" "${up[@]}")
    done
    ydotool key "${down[@]}" "${up[@]}" >/dev/null
    sleep 1
    ;;

  click)
    ensure_ydotool
    title="${3:-renCal}"
    read -r x y w h < <(geometry "$title")
    [[ -n "${x:-}" ]] || die "no window titled '$title'"
    dispatch "hl.dsp.cursor.move({ x = $((x + $1)), y = $((y + $2)) })"
    sleep 0.2
    ydotool click 0xC0 >/dev/null
    sleep 0.3
    focus "$title"
    sleep 0.6
    ;;

  theme)
    "$0" combo ctrl+k
    wtype theme
    sleep 0.5
    wtype -k Return
    sleep 0.5
    wtype "${1:?theme <name>}"
    sleep 0.5
    wtype -k Return
    sleep 1.5
    ;;

  cleanup)
    if pid=$(dev_pid); then
      kill "$pid"
      echo "stopped dev renCal ($pid)"
    fi
    if [[ -f "$DIR/.started-ydotool" ]]; then
      systemctl --user stop ydotool
      rm "$DIR/.started-ydotool"
      echo "stopped ydotool"
    fi
    ;;

  *)
    sed -n '2,13p' "$0" | sed 's/^# \{0,1\}//'
    exit 1
    ;;
esac
