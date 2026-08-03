#!/bin/sh
# Publishes a synthetic surveillance-style test stream to MediaMTX at
# rtsp://mediamtx:8554/test_video.
#
# The 24s loop mimics a fixed CCTV scene: a dark courtyard, empty for 8s,
# then a bright "intruder" object crosses the frame for 8s, then empty again.
# Watching Live View you SEE the crossing; the frame-difference motion
# detector fires during it and stays quiet otherwise — a truthful end-to-end
# demo of detection with no physical camera.
set -u

V=/tmp/testvid
mkdir -p "$V"

ENC="-c:v libx264 -preset veryfast -profile:v baseline -pix_fmt yuv420p -g 30 -b:v 1200k"

if [ ! -f "$V/loop.mp4" ]; then
    echo "==> Generating surveillance-style test clip (one-time)"
    # Background: static dark gradient "courtyard". Foreground: light box that
    # enters at t=8s, crosses, and exits by t=16s. Loop total: 24s.
    ffmpeg -y -v error \
        -f lavfi -i "gradients=s=1280x720:c0=0x0c141d:c1=0x1b2836:speed=0.0001:r=15" \
        -f lavfi -i "color=c=0xd8e6f2:s=150x300:r=15" \
        -filter_complex \
        "[1]format=yuva420p,colorchannelmixer=aa=0.95[obj];\
         [0][obj]overlay=x='if(between(t,8,16),(t-8)/8*(W+320)-160,-400)':y=H-360" \
        -t 24 $ENC "$V/loop.mp4"
    echo "==> Test clip ready: $V/loop.mp4"
fi

echo "==> Publishing loop to rtsp://mediamtx:8554/test_video"
while true; do
    ffmpeg -v warning -re -stream_loop -1 -i "$V/loop.mp4" \
        -c copy -f rtsp -rtsp_transport tcp \
        rtsp://mediamtx:8554/test_video || true
    echo "publisher exited; retrying in 3s..."
    sleep 3
done
