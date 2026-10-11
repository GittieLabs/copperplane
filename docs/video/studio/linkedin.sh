#!/bin/sh
# Upload files for LinkedIn (CTX-408.8), from the rendered cuts in out/.
#
# For each 4:5 and 1:1 cut: the MP4 with a silent AAC track added, its .srt,
# and its cover as a JPG. Guides describe LinkedIn video as "H.264 with AAC
# audio"; whether it rejects a file with no audio track at all is unverified,
# and a silent track costs nothing. LinkedIn's own help page (for video ads)
# caps a thumbnail at 2 MB, JPG or PNG, matching the video's aspect ratio; this
# fails if a cover is over that.
set -eu
cd "$(dirname "$0")"
mkdir -p out/linkedin
for cut in 15 30 60; do
  for fmt in 4x5 1x1; do
    name="cut-$cut-$fmt"
    [ -f "out/$name.mp4" ] || { echo "missing out/$name.mp4; render it first" >&2; exit 1; }
    ffmpeg -v error -y -i "out/$name.mp4" -f lavfi -i anullsrc=channel_layout=stereo:sample_rate=48000 \
      -c:v copy -c:a aac -b:a 64k -shortest -movflags +faststart "out/linkedin/$name.mp4"
    cp "out/$name.srt" "out/linkedin/$name.srt"
    ffmpeg -v error -y -i "out/$name-cover.png" -q:v 3 "out/linkedin/$name-cover.jpg"
    bytes=$(wc -c < "out/linkedin/$name-cover.jpg")
    [ "$bytes" -le 2097152 ] || { echo "$name cover is $bytes bytes, over LinkedIn's 2 MB" >&2; exit 1; }
    echo "$name: $(ffprobe -v error -show_entries stream=codec_type,codec_name -of csv=p=0 "out/linkedin/$name.mp4" | tr '\n' ' ') cover ${bytes}B"
  done
done
