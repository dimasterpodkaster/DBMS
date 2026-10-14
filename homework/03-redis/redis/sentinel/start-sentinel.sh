#!/bin/sh
set -eu

config=/data/sentinel.conf
template=/usr/local/etc/redis/sentinel.conf.template

if [ ! -s "$config" ]; then
  cp "$template" "$config"
fi

exec redis-server "$config" --sentinel

